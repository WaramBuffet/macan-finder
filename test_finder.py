import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from finder import DEALERS, assess, build, dealer_distance, load_history, mileage_tier, score, tier, validate_vehicle

SEED = Path(__file__).parent / "snapshots" / "2026-11-08.json"
CAR = json.loads(SEED.read_text())["vehicles"][0]
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


class FinderTests(unittest.TestCase):
    def setUp(self):
        self.car = {**CAR, "production_year": None, "acc_working": None,
                    "dealer_coordinates": [49.4521, 11.0767], "coordinate_accuracy_km": 1, "dealer": "Porsche Zentrum Bamberg", "dealer_url": "https://bamberg.porsche.de/de/contact", "price": 70000, "owners": 1, "generation_iii": True, "rear_camera": True}

    def test_must_criteria_and_thresholds(self):
        self.assertEqual(assess(self.car)[0], "Bestätigter Profiltreffer")
        for field, bad in (("acc", False), ("accident_free", False), ("generation_iii", False), ("rear_camera", False), ("price", 85001), ("km", 65001), ("owners", 3), ("color", "Pythongrün")):
            self.assertEqual(assess({**self.car, field: bad})[0], "Ausgeschlossen", field)
        for field in ("acc", "generation_iii", "rear_camera", "price", "km", "owners", "color"):
            self.assertEqual(assess({**self.car, field: None})[0], "Prüfbedürftig", field)
        self.assertEqual(assess({**self.car, "price": 85000, "km": 65000, "owners": 2})[0], "Bestätigter Profiltreffer")
        self.assertEqual(tier({**self.car, "price": 65000}), "Wunschbereich")
        self.assertEqual(mileage_tier({**self.car, "km": 50001}), "Grenzbereich")
        self.assertEqual(assess({**self.car, "acc_working": False})[0], "Bestätigter Profiltreffer")

    def test_unknown_distance_and_porsche_domains(self):
        self.assertIsNone(assess({**self.car, "dealer_coordinates": None})[1]["distance"])
        self.assertFalse(assess({**self.car, "dealer_coordinates": [53.55, 10.0]})[1]["distance"])
        self.assertIsNone(assess({**self.car, "dealer_coordinates": [51.25, 11.0767], "coordinate_accuracy_km": 10})[1]["distance"])
        self.assertTrue(assess({**self.car, "dealer_coordinates": [50.0, 11.0767], "coordinate_accuracy_km": 10})[1]["distance"])
        with self.assertRaises(ValueError):
            validate_vehicle({**CAR, "url": "https://finder.porsche.com.example.org/de/de-DE/details/x"}, 2026)
        with self.assertRaises(ValueError):
            validate_vehicle({**CAR, "acc": "false"}, 2026)

    def test_scoring_wishes_keep_unknown_separate(self):
        car = {**self.car, "km": 50000, "price": 65000, "surround_view": True, "privacy_glass": None, "badge_removed": False}
        result, breakdown = score(car, [], NOW)
        self.assertEqual(result, 4)
        self.assertIsNone(breakdown["Privacyverglasung"])
        self.assertFalse(breakdown["Modellbezeichnung entfallen"])
        self.assertEqual(score({**car, "seats18": True, "chrono": True}, [], NOW), (result, breakdown))
        self.assertEqual(score({**car, "rear_camera": None}, [], NOW), (None, {}))

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
                     self.snapshot(root, 12, [{**self.car, "price": 75000}]),
                     self.snapshot(root, 13, [{**self.car, "price": 75000, "availability": "not_found"}])]
            _, history, events = load_history(paths, NOW)
            self.assertEqual(len(history["bamberg-5321"]), 5)
            self.assertEqual([event[0] for event in events], ["new", "price"])
            self.assertEqual(events[1][2], 70000)
            build(paths, root / "site", "test", NOW)
            feed = ET.parse(root / "site/feed.xml")
            self.assertEqual(len(feed.findall("./channel/item")), 2)
            page = (root / "site/index.html").read_text()
            self.assertIn("Nicht mehr auffindbar", page)
            self.assertIn("75.000 €", page)
            self.assertNotIn("18-Wege", page)
            self.assertNotIn("Sport Chrono", page)

    def test_seed_build_has_no_alert_and_keeps_unknown_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build([SEED], output, "test", NOW)
            page = (output / "index.html").read_text()
            self.assertIn("Bestätigte Profiltreffer · 0", page)
            self.assertIn("Porsche Zentrum Aschaffenburg", page)
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

    def test_unknown_acc_is_not_displayed_but_remains_required(self):
        car = {**self.car, "acc": None, "availability": "listed"}
        self.assertEqual(assess(car)[0], "Prüfbedürftig")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build([self.snapshot(root, 9, [car])], root / "site", "test", NOW)
            page = (root / "site/index.html").read_text()
            self.assertNotIn("ACC laut Inserat vorhanden · Ungeklärt", page)
            self.assertIn("Prüfbedürftige Inserate · 1", page)

    def test_only_selected_dealers_are_inside_radius_and_listed(self):
        self.assertTrue({"amberg", "bamberg", "bayreuth", "nuernberg", "regensburg", "ingolstadt", "wuerzburg", "aschaffenburg", "heilbronn", "schwaebisch-gmuend", "augsburg", "erfurt", "olympiapark"} <= set(DEALERS))
        self.assertTrue(all(dealer_distance(value["coordinates"]) <= 200 for value in DEALERS.values()))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build([SEED], output, "test", NOW)
            page = (output / "index.html").read_text()
            for value in DEALERS.values():
                self.assertIn(value["name"].replace("&", "&amp;"), page)
                if value["drive_minutes"] is not None:
                    self.assertIn(f'ca. {value["drive_minutes"]} Min.' if value["drive_minutes"] < 60
                                  else f'ca. {value["drive_minutes"] // 60} Std. {value["drive_minutes"] % 60:02d} Min.', page)
                else:
                    self.assertIn("Nicht verlässlich ermittelt", page)

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


