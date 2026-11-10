import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from finder import DEALERS, assess, build, dealer_distance, load_history, score, tier, validate_vehicle

SEED = Path(__file__).parent / "snapshots" / "2026-11-08.json"
CAR = json.loads(SEED.read_text())["vehicles"][0]
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


class FinderTests(unittest.TestCase):
    def setUp(self):
        self.car = {**CAR, "production_year": None, "acc_working": None,
                    "dealer_coordinates": [49.4521, 11.0767], "coordinate_accuracy_km": 1, "dealer": "Porsche Zentrum Bamberg", "dealer_url": "https://bamberg.porsche.de/de/contact"}

    def test_must_criteria_and_thresholds(self):
        self.assertEqual(assess(CAR)[0], "Ausgeschlossen")
        self.assertEqual(assess(self.car)[0], "Bestätigter Profiltreffer")
        self.assertEqual(assess({**self.car, "acc": False, "acc_working": None})[0], "Ausgeschlossen")
        self.assertEqual(assess({**self.car, "accident_free": False})[0], "Ausgeschlossen")
        self.assertEqual(assess({**self.car, "color_group": "excluded"})[0], "Ausgeschlossen")
        self.assertEqual(assess({**self.car, "registration": "2021-12"})[0], "Ausgeschlossen")
        self.assertEqual(assess({**self.car, "registration": None})[0], "Prüfbedürftig")
        self.assertEqual(assess({**self.car, "acc": None, "acc_working": None})[0], "Prüfbedürftig")
        self.assertEqual(assess({**self.car, "acc": True, "acc_working": None})[0], "Bestätigter Profiltreffer")
        self.assertEqual(assess({**self.car, "acc": True, "acc_working": False})[0], "Bestätigter Profiltreffer")
        boundary = {**self.car, "price": 95000, "km": 50000}
        self.assertEqual(assess(boundary)[0], "Bestätigter Profiltreffer")
        self.assertEqual(tier(boundary), "C")
        self.assertEqual(assess({**boundary, "km": 50001})[0], "Ausgeschlossen")
        self.assertEqual(assess({**boundary, "km": None})[0], "Prüfbedürftig")
        self.assertEqual(tier({**self.car, "price": 80000, "km": 50000}), "A")
        self.assertEqual(tier(self.car), "B")

    def test_unknown_distance_and_porsche_domains(self):
        self.assertIsNone(assess({**self.car, "dealer_coordinates": None})[1]["distance"])
        self.assertFalse(assess({**self.car, "dealer_coordinates": [53.55, 10.0]})[1]["distance"])
        self.assertIsNone(assess({**self.car, "dealer_coordinates": [50.35, 11.0767], "coordinate_accuracy_km": 10})[1]["distance"])
        self.assertTrue(assess({**self.car, "dealer_coordinates": [50.0, 11.0767], "coordinate_accuracy_km": 10})[1]["distance"])
        with self.assertRaises(ValueError):
            validate_vehicle({**CAR, "url": "https://finder.porsche.com.example.org/de/de-DE/details/x"}, 2026)
        with self.assertRaises(ValueError):
            validate_vehicle({**CAR, "acc": "false"}, 2026)

    def test_scoring_requires_real_comparables(self):
        car = {**self.car, "key": "a", "researched_at": NOW.isoformat(), "condition_points": 20,
               "impression_points": 7}
        peers = [{**car, "key": str(i)} for i in range(5)]
        self.assertEqual(score({**CAR, "acc": None}, [], NOW), (None, {}))
        self.assertIsNone(score(car, peers[:4], NOW)[0])
        result, breakdown = score(car, peers, NOW)
        self.assertEqual(breakdown["Preis / Marktvergleich"], 18)
        self.assertNotIn("18-Wege-Sportsitze", breakdown)
        self.assertNotIn("Sport Chrono", breakdown)
        self.assertEqual(score({**car, "seats18": None, "chrono": None}, peers, NOW), (result, breakdown))
        self.assertEqual(result, sum(breakdown.values()))

    def snapshot(self, root, day, vehicles):
        stamp = f"2026-11-{day:02d}T08:00:00+01:00"
        path = root / f"{day}.json"
        path.write_text(json.dumps({"researched_at": stamp, "verified_at": stamp,
                                    "scope": "Teststichprobe", "vehicles": vehicles}))
        return path

    def test_history_and_rss_include_only_relevant_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [self.snapshot(root, 8, [{**self.car, "acc": None}]), self.snapshot(root, 9, [self.car]),
                     self.snapshot(root, 10, [self.car]), self.snapshot(root, 11, []),
                     self.snapshot(root, 12, [{**self.car, "price": 83900}]),
                     self.snapshot(root, 13, [{**self.car, "price": 83900, "availability": "not_found"}])]
            _, history, events = load_history(paths, NOW)
            self.assertEqual(len(history["bamberg-5321"]), 5)
            self.assertEqual([event[0] for event in events], ["new", "price"])
            self.assertEqual(events[1][2], 85890)
            build(paths, root / "site", "test", NOW)
            feed = ET.parse(root / "site/feed.xml")
            self.assertEqual(len(feed.findall("./channel/item")), 2)
            page = (root / "site/index.html").read_text()
            self.assertIn("Nicht mehr auffindbar", page)
            self.assertIn("83.900 €", page)
            self.assertNotIn("18-Wege", page)
            self.assertNotIn("Sport Chrono", page)

    def test_seed_build_has_no_alert_and_keeps_unknown_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build([SEED], output, "test", NOW)
            page = (output / "index.html").read_text()
            self.assertIn("Bestätigte Profiltreffer · 0", page)
            self.assertNotIn("Porsche Zentrum Aschaffenburg", page)
            self.assertNotIn("85.890 €", page)
            self.assertEqual(len(ET.parse(output / "feed.xml").findall("./channel/item")), 0)
            self.assertEqual((output / "build.txt").read_text().strip(), "test")

    def test_drive_time_is_sourced_and_rendered(self):
        drive = {"minutes": 65, "source": "https://example.org/route", "checked_at": "2026-11-09T10:00:00+01:00"}
        validate_vehicle({**self.car, "drive_time": drive}, 2026)
        with self.assertRaises(ValueError):
            validate_vehicle({**self.car, "drive_time": {"minutes": 65}}, 2026)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build([self.snapshot(root, 9, [{**self.car, "drive_time": drive}])], root / "site", "test", NOW)
            page = (root / "site/index.html").read_text()
            self.assertIn("Fahrzeit ab Eckental-Brand: ca. 1 Std. 05 Min.", page)
            self.assertIn("https://example.org/route", page)

    def test_only_selected_dealers_are_inside_radius_and_listed(self):
        self.assertEqual(set(DEALERS), {"amberg", "bamberg", "bayreuth", "nuernberg", "regensburg", "ingolstadt", "wuerzburg"})
        self.assertTrue(all(dealer_distance(value["coordinates"]) <= 100 for value in DEALERS.values()))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build([SEED], output, "test", NOW)
            page = (output / "index.html").read_text()
            for value in DEALERS.values():
                self.assertIn(value["name"], page)
                self.assertIn(f'ca. {value["drive_minutes"]} Min.' if value["drive_minutes"] < 60
                              else f'ca. {value["drive_minutes"] // 60} Std. {value["drive_minutes"] % 60:02d} Min.', page)

    def test_duplicate_or_invalid_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.snapshot(root, 8, [CAR, CAR])
            with self.assertRaisesRegex(ValueError, "Doppelter"):
                load_history([path], NOW)
            future = self.snapshot(root, 15, [CAR])
            with self.assertRaises(ValueError):
                load_history([future], NOW)


if __name__ == "__main__":
    unittest.main()


