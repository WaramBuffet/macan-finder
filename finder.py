"""Build the Macan Finder from reviewed, dated Porsche observations."""
import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from statistics import median
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SITE = "https://warambuffet.github.io/macan-finder/"
REPO = "https://github.com/WaramBuffet/macan-finder"
SEARCH = "https://finder.porsche.com/de/de-DE/search/macan?condition=used&model=macan&category=macan-s&category=macan-gts&maximum-price=85000&maximum-mileage=65000&minimum-registration-date=2022&position=N%C3%BCrnberg%2C49.45435%2C11.07346%2C200&equipment=acc-incl-pas"
RADIUS_KM = 200
NUREMBERG = (49.45435, 11.07346)
DEALERS = {
    "chemnitz": {"name": "Porsche Zentrum Chemnitz", "url": "https://chemnitz.porsche.de/de/contact", "coordinates": (50.8054821, 12.857103), "drive_minutes": 125, "drive_checked_at": "10.11.2026, 19:17 MEZ"},
    "amberg": {"name": "Porsche Zentrum Amberg", "url": "https://amberg.porsche.de/de/contact",
               "coordinates": (49.4355, 11.8888), "drive_minutes": 56},
    "bamberg": {"name": "Porsche Zentrum Bamberg", "url": "https://bamberg.porsche.de/de/contact",
                "coordinates": (49.911371, 10.903194), "drive_minutes": 39},
    "bayreuth": {"name": "Porsche Zentrum Bayreuth", "url": "https://bayreuth.porsche.de/de/contact",
                 "coordinates": (49.909245, 11.606718), "drive_minutes": 44},
    "nuernberg": {"name": "Porsche Zentrum Nürnberg-Fürth-Erlangen", "url": "https://nuernberg.porsche.de/de/contact",
                  "coordinates": (49.485290, 11.058936), "drive_minutes": 19},
    "regensburg": {"name": "Porsche Zentrum Regensburg", "url": "https://regensburg.porsche.de/de/contact",
                   "coordinates": (48.99359, 12.10424), "drive_minutes": 72},
    "ingolstadt": {"name": "Porsche Zentrum Ingolstadt", "url": "https://ingolstadt.porsche.de/de/contact",
                   "coordinates": (48.748902, 11.460769), "drive_minutes": 65},
    "wuerzburg": {"name": "Porsche Zentrum Würzburg", "url": "https://wuerzburg.porsche.de/de/contact",
                  "coordinates": (49.840217, 10.009811), "drive_minutes": 63},
    "aschaffenburg": {"name": "Porsche Zentrum Aschaffenburg", "url": "https://aschaffenburg.porsche.de/de/contact", "coordinates": (49.9651, 9.1728), "drive_minutes": 109, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "heilbronn": {"name": "Porsche Zentrum Heilbronn", "url": "https://heilbronn.porsche.de/de/contact", "coordinates": (49.1213, 9.2231), "drive_minutes": 120, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "schwaebisch-gmuend": {"name": "Porsche Zentrum Schwäbisch Gmünd", "url": "https://schwaebisch-gmuend.porsche.de/de/contact", "coordinates": (48.7915, 9.7721), "drive_minutes": 120, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "darmstadt": {"name": "Porsche Zentrum Darmstadt", "url": "https://darmstadt.porsche.de/de/contact", "coordinates": (49.8630131, 8.6296094), "drive_minutes": 141, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "frankfurt": {"name": "Porsche Zentrum Frankfurt", "url": "https://frankfurt.porsche.de/de/contact", "coordinates": (50.1160256, 8.7273209), "drive_minutes": 124, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "altoetting": {"name": "Porsche Zentrum Altötting", "url": "https://altoetting.porsche.de/de/contact", "coordinates": (48.2540839, 12.6898666), "drive_minutes": 151, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "bad-homburg": {"name": "Porsche Zentrum Bad Homburg/Oberursel", "url": "https://bad-homburg.porsche.de/de/contact", "coordinates": (50.2076565, 8.5972372), "drive_minutes": 136, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "reutlingen": {"name": "Porsche Zentrum Reutlingen", "url": "https://reutlingen.porsche.de/de/contact", "coordinates": (48.4968209, 9.1533474), "drive_minutes": 172, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "mannheim": {"name": "Porsche Zentrum Mannheim", "url": "https://mannheim.porsche.de/de/contact", "coordinates": (49.4503362, 8.5664627), "drive_minutes": 151, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "ulm": {"name": "Porsche Zentrum Ulm-Neu-Ulm", "url": "https://ulm.porsche.de/de/contact", "coordinates": (48.3667333, 9.9576207), "drive_minutes": 133, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "stuttgart-filderstadt": {"name": "Porsche Zentrum Stuttgart Filderstadt", "url": "https://stuttgart-filderstadt.porsche.de/de/contact", "coordinates": (48.6822562, 9.210313), "drive_minutes": 154, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "rosenheim": {"name": "Porsche Zentrum Rosenheim", "url": "https://rosenheim.porsche.de/de/contact", "coordinates": (47.8162565, 12.1202333), "drive_minutes": 147, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "frankfurt-west-approved": {"name": "Porsche Approved & Service Zentrum Frankfurt West", "url": "https://frankfurt-west-approved.porsche.de/de/contact", "coordinates": (50.1273392, 8.5810083), "drive_minutes": 133, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "augsburg": {"name": "Porsche Zentrum Augsburg", "url": "https://augsburg.porsche.de/de/contact", "coordinates": (48.4083, 10.8721), "drive_minutes": 110, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "landshut": {"name": "Porsche Zentrum Landshut", "url": "https://landshut.porsche.de/de/contact", "coordinates": (48.567968, 12.155927), "drive_minutes": 102, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "goeppingen": {"name": "Porsche Zentrum Göppingen", "url": "https://goeppingen.porsche.de/de/contact", "coordinates": (48.694249, 9.666462), "drive_minutes": 144, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "niederbayern": {"name": "Porsche Zentrum Niederbayern/Plattling", "url": "https://niederbayern.porsche.de/de/contact", "coordinates": (48.787209, 12.849583), "drive_minutes": 114, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "erfurt": {"name": "Porsche Zentrum Erfurt", "url": "https://erfurt.porsche.de/de/contact", "coordinates": (50.973949, 11.061862), "drive_minutes": 141, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "fulda": {"name": "Porsche Zentrum Fulda", "url": "https://fulda.porsche.de/de/contact", "coordinates": (50.53427, 9.68252), "drive_minutes": 123, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "olympiapark": {"name": "Porsche Zentrum Olympiapark", "url": "https://olympiapark.porsche.de/de/contact", "coordinates": (48.1874, 11.5360), "drive_minutes": 108, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "muenchen": {"name": "Porsche Zentrum München", "url": "https://muenchen.porsche.de/de/contact", "coordinates": (48.1290, 11.5911), "drive_minutes": 115, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "muenchen-sued": {"name": "Porsche Zentrum München Süd", "url": "https://muenchen-sued.porsche.de/de/contact", "coordinates": (48.093802, 11.503821), "drive_minutes": 126, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "5seen": {"name": "Porsche Zentrum 5 Seen", "url": "https://5seen.porsche.de/de/contact", "coordinates": (48.1014, 11.3084), "drive_minutes": 116, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "stuttgart": {"name": "Porsche Zentrum Stuttgart", "url": "https://stuttgart.porsche.de/de/contact", "coordinates": (48.810827, 9.181280), "drive_minutes": 138, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "boeblingen": {"name": "Porsche Zentrum Böblingen", "url": "https://boeblingen.porsche.de/de/contact", "coordinates": (48.690139, 9.005312), "drive_minutes": 149, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
    "pforzheim": {"name": "Porsche Zentrum Pforzheim", "url": "https://pforzheim.porsche.de/de/contact", "coordinates": (48.910721, 8.719793), "drive_minutes": 158, "drive_checked_at": "10.11.2026, 18:40–18:54 MEZ"},
}
ALLOWED_DEALERS = set(DEALERS)
DEALER_DRIVE_MINUTES = {key: value["drive_minutes"] for key, value in DEALERS.items()}
DEALER_DRIVE_CHECKED_AT = "2026-11-09T22:00:00+01:00"
BERLIN = ZoneInfo("Europe/Berlin")
BOOLEAN_FIELDS = ("accident_free", "acc", "acc_working", "seats18", "chrono", "generation_iii", "rear_camera", "surround_view", "privacy_glass", "badge_removed")
AVAILABILITY = {
    "listed": "Inseriert", "reserved": "Reserviert", "sold": "Als verkauft bestätigt",
    "not_found": "Nicht mehr auffindbar", "unknown": "Ungeklärt",
}
CHECKS = {
    "registration": "Erstzulassung ab 2022", "color_group": "Außenfarbe Schwarz, Grau, Silber, Blau oder Kreide",
    "distance": "Im Umkreis von 200 km", "generation_iii": "Macan III ab Modellpflege 2021",
    "accident_free": "Unfallfrei", "acc": "ACC laut Inserat vorhanden",
    "km": "Höchstens 65.000 km", "price": "Höchstens 85.000 €",
    "owners": "Höchstens zwei Vorbesitzer", "rear_camera": "Rückfahrkamera vorhanden",
}
WEIGHTS = {}



def moment(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Zeitstempel ohne Zeitzone")
    return result


def display_time(value):
    return moment(value).astimezone(BERLIN).strftime("%d.%m.%Y, %H:%M %Z")


def official_url(value, dealer=False):
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.scheme != "https" or parts.netloc != host or parts.query or parts.fragment:
        raise ValueError("Erwartet: kanonischer HTTPS-Porsche-Link")
    if dealer:
        valid = bool(re.fullmatch(r"[a-z0-9-]+\.porsche\.de", host) and parts.path.startswith("/de/"))
    else:
        valid = (
            host == "finder.porsche.com" and parts.path.startswith("/de/de-DE/details/")
            or bool(re.fullmatch(r"[a-z0-9-]+\.porsche\.de", host)
                    and parts.path.startswith("/de/inventory/porsche/"))
        )
    if not valid:
        raise ValueError(f"Unzulässige Quelle: {host}")
    return host


def bounded(value, low, high, label):
    if value is not None and (type(value) is not int or not low <= value <= high):
        raise ValueError(f"Ungültiger Wert für {label}")


def validate_vehicle(car, year):
    dealer = official_url(car["dealer_url"], dealer=True)
    source = official_url(car["url"])
    if source not in ("finder.porsche.com", dealer):
        raise ValueError("Inserat und Porsche-Zentrum passen nicht zusammen")
    if not (car["dealer"].startswith("Porsche Zentrum ") or car["dealer"] == "Porsche Approved & Service Zentrum Frankfurt West") or not re.fullmatch(r"[A-Za-z0-9-]{1,40}", car["stock"]):
        raise ValueError("Porsche-Zentrum oder Bestandsnummer fehlt")
    if car["model"] not in ("S", "GTS") or car["availability"] not in AVAILABILITY:
        raise ValueError("Unbekanntes Modell oder Verfügbarkeit")
    if car.get("color_group") not in (None, "allowed", "excluded"):
        raise ValueError("Unbekannte Farbgruppe")
    if car.get("color_group") is not None and not car.get("color"):
        raise ValueError("Farbgruppe ohne Farbangabe")
    for field in BOOLEAN_FIELDS:
        if car.get(field) is not None and type(car[field]) is not bool:
            raise ValueError(f"{field} muss true, false oder null sein")
    if car.get("acc_working") is True and car.get("acc") is not True:
        raise ValueError("Bestätigte ACC-Funktion setzt bestätigtes ACC voraus")
    photo = car.get("photo_url")
    if photo is not None:
        parsed_photo = urlsplit(photo)
        if (parsed_photo.scheme != "https" or parsed_photo.hostname not in
                ("images.finder.porsche.com", "s.images.finder.porsche.com")
                or parsed_photo.username is not None or parsed_photo.password is not None):
            raise ValueError("Fahrzeugfoto muss von der offiziellen Porsche-Bildquelle stammen")
    for field, low, high in (("production_year", 2014, year), ("price", 1, 9999999),
                             ("km", 0, 999999), ("owners", 0, 99), ("warranty_months", 0, 120),
                             ("condition_points", 0, 25), ("impression_points", 0, 10)):
        bounded(car.get(field), low, high, field)
    for field in ("condition", "impression"):
        if car.get(f"{field}_points") is not None and not car.get(f"{field}_note"):
            raise ValueError(f"Begründung für {field} fehlt")
    travel = car.get("drive_time")
    if travel is not None:
        if not isinstance(travel, dict):
            raise ValueError("Fahrzeit muss eine Quellenangabe enthalten")
        bounded(travel.get("minutes"), 1, 1440, "Fahrzeit")
        source = urlsplit(travel.get("source", ""))
        if (travel.get("minutes") is None or source.scheme != "https" or not source.hostname
                or source.username is not None or source.password is not None or not travel.get("checked_at")):
            raise ValueError("Fahrzeit braucht Minuten, HTTPS-Quelle und Prüfzeitpunkt")
        moment(travel["checked_at"])
    registration = car.get("registration")
    if registration is not None:
        if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", registration):
            raise ValueError("Erstzulassung muss JJJJ-MM sein")
        if not (car.get("production_year") or 2014) <= int(registration[:4]) <= year:
            raise ValueError("Erstzulassung passt zeitlich nicht")
    coords = car.get("dealer_coordinates")
    accuracy = car.get("coordinate_accuracy_km")
    if coords is not None:
        if (len(coords) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in coords)
                or not -90 <= coords[0] <= 90 or not -180 <= coords[1] <= 180
                or accuracy is None):
            raise ValueError("Standort oder Genauigkeit ungültig")
        bounded(accuracy, 0, 50, "coordinate_accuracy_km")
    return f"{dealer.split('.')[0]}-{car['stock'].lower()}"


def distance(car):
    if car.get("dealer_coordinates") is None:
        return None
    lat, lon = map(math.radians, car["dealer_coordinates"])
    nlat, nlon = map(math.radians, NUREMBERG)
    hav = math.sin((lat - nlat) / 2)**2 + math.cos(lat) * math.cos(nlat) * math.sin((lon - nlon) / 2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1, hav)))


def dealer_distance(coordinates):
    lat, lon = map(math.radians, coordinates)
    nlat, nlon = map(math.radians, NUREMBERG)
    hav = math.sin((lat - nlat) / 2)**2 + math.cos(lat) * math.cos(nlat) * math.sin((lon - nlon) / 2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1, hav)))


def route_url(destination):
    return "https://www.google.com/maps/dir/?" + urlencode({
        "api": "1", "origin": "Brand, 90542 Eckental, Deutschland",
        "destination": destination, "travelmode": "driving"})


def dealer_overview():
    rows = []
    for dealer in DEALERS.values():
        km = dealer_distance(dealer["coordinates"])
        minutes = dealer["drive_minutes"]
        duration = (f"ca. {minutes // 60} Std. {minutes % 60:02d} Min." if minutes >= 60 else f"ca. {minutes} Min.") if minutes is not None else "Nicht verlässlich ermittelt"
        source_note = f' · Abfrage {dealer.get("drive_checked_at", "09.11.2026")}' if minutes is not None else " · Routenplaner"
        rows.append(
            f'<tr><td><a href="{escape(dealer["url"], quote=True)}">{escape(dealer["name"])}</a></td>'
            f'<td>ca. {km:.1f} km</td><td>{duration}</td>'
            f'<td><a href="{escape(route_url(dealer["name"]), quote=True)}">Google Maps</a>{source_note}</td></tr>'
        )
    return ("<section><h2>Berücksichtigte Porsche Zentren</h2>"
            "<p>Die Luftlinie ist aus den dokumentierten Standortkoordinaten berechnet. Die Fahrzeiten sind dauerhaft "
            "hinterlegte Richtwerte aus datierten Google-Maps-Abfragen, keine Live- oder statistischen Durchschnittswerte. Fehlende Werte sind noch nicht verlässlich belegt; die Standortliste ist eine Teilrecherche.</p>"
            "<table><thead><tr><th>Zentrum</th><th>Luftlinie ab Nürnberg</th><th>Fahrzeit ab Eckental-Brand</th>"
            "<th>Quelle</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></section>")


def assess(car):
    checks = {field: car.get(field) for field in ("accident_free", "acc", "generation_iii", "rear_camera")}
    for field, maximum in (("km", 65000), ("price", 85000), ("owners", 2)):
        checks[field] = None if car.get(field) is None else car[field] <= maximum
    registration = car.get("registration")
    checks["registration"] = None if registration is None else int(registration[:4]) >= 2022
    color = (car.get("color") or "").lower()
    if not color:
        checks["color_group"] = None
    elif car.get("color_group") == "excluded" or any(x in color for x in ("weiß", "weiss", "rot", "grün", "gruen")):
        checks["color_group"] = False
    elif any(x in color for x in ("schwarz", "grau", "silber", "blau", "kreide")):
        checks["color_group"] = True
    else:
        checks["color_group"] = None
    km = distance(car)
    checks["distance"] = None
    if km is not None:
        margin = car["coordinate_accuracy_km"]
        if km + margin <= RADIUS_KM:
            checks["distance"] = True
        elif km - margin > RADIUS_KM:
            checks["distance"] = False
    if False in checks.values():
        state = "Ausgeschlossen"
    elif car["availability"] != "listed":
        state = AVAILABILITY[car["availability"]]
    elif None in checks.values():
        state = "Prüfbedürftig"
    else:
        state = "Bestätigter Profiltreffer"
    return state, checks


def tier(car):
    price = car.get("price")
    return "Offen" if price is None else "Wunschbereich" if price <= 65000 else "Grenzbereich" if price <= 85000 else "Ausgeschlossen"


def mileage_tier(car):
    km = car.get("km")
    return "Offen" if km is None else "Wunschbereich" if km <= 50000 else "Grenzbereich" if km <= 65000 else "Ausgeschlossen"


def score(car, peers, as_of):
    if assess(car)[0] != "Bestätigter Profiltreffer":
        return None, {}
    points = {
        "Bis 50.000 km": None if car.get("km") is None else car["km"] <= 50000,
        "Bis 65.000 €": None if car.get("price") is None else car["price"] <= 65000,
        "Ein Vorbesitzer": None if car.get("owners") is None else car["owners"] <= 1,
        "Surround View": car.get("surround_view"),
        "Privacyverglasung": car.get("privacy_glass"),
        "Modellbezeichnung entfallen": car.get("badge_removed"),
    }
    return sum(value is True for value in points.values()), points


def load_history(paths, now):
    snapshots = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    snapshots.sort(key=lambda item: moment(item["researched_at"]))
    history, events = {}, []
    previous_time = None
    for item in snapshots:
        researched, verified = moment(item["researched_at"]), moment(item["verified_at"])
        if (not researched <= verified <= now or previous_time is not None and researched <= previous_time
                or not item["scope"].strip() or not isinstance(item["vehicles"], list)):
            raise ValueError("Stichprobe ohne gültigen Zeitraum oder Umfang")
        previous_time = researched
        seen = set()
        for source in item["vehicles"]:
            key = validate_vehicle(source, researched.astimezone(BERLIN).year)
            if key in seen:
                raise ValueError(f"Doppelter Datensatz in Stichprobe: {key}")
            seen.add(key)
            car = {**source, "key": key, "researched_at": item["researched_at"],
                   "verified_at": item["verified_at"]}
            observations = history.setdefault(key, [])
            if observations and observations[-1]["model"] != car["model"]:
                raise ValueError(f"Bestandsnummer möglicherweise wiederverwendet: {key}")
            last_match = next((entry for entry in reversed(observations)
                               if assess(entry)[0] == "Bestätigter Profiltreffer"), None)
            if assess(car)[0] == "Bestätigter Profiltreffer":
                if last_match is None:
                    events.append(("new", car, None))
                elif last_match["price"] != car["price"]:
                    events.append(("price", car, last_match["price"]))
            observations.append(car)
    return snapshots, history, events


def number(value, unit=""):
    return "Ungeklärt" if value is None else f"{value:,}".replace(",", ".") + unit


def rss(output, events):
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    for tag, value in (("title", "Macan Finder – Änderungen"), ("link", SITE),
                       ("description", "Neue bestätigte Profiltreffer und deren Preisänderungen.")):
        ET.SubElement(channel, tag).text = value
    for kind, car, old in reversed(events):
        item = ET.SubElement(channel, "item")
        title = "Neuer Profiltreffer" if kind == "new" else f"Preisänderung von {number(old, ' €')}"
        ET.SubElement(item, "title").text = f"{title} · Macan {car['model']} · {number(car['price'], ' €')}"
        ET.SubElement(item, "link").text = SITE + "#" + car["key"]
        ET.SubElement(item, "description").text = f"{car['dealer']} · {car['url']}"
        ET.SubElement(item, "guid", isPermaLink="false").text = f"{SITE}{car['key']}/{car['researched_at']}/{kind}"
        ET.SubElement(item, "pubDate").text = format_datetime(moment(car["verified_at"]))
    ET.ElementTree(root).write(output / "feed.xml", encoding="utf-8", xml_declaration=True)


def card(car, observations, result, now, previous_sighting=False, prominent=False):
    state, checks = assess(car)
    if previous_sighting:
        state = "Frühere Sichtung – aktuell ungeprüft"
    total, points = result
    km = distance(car)
    availability = AVAILABILITY[car["availability"]]
    if car.get("availability_note"):
        availability += " · " + car["availability_note"]
    values = [
        ("Preis", number(car.get("price"), " €")), ("Laufleistung", number(car.get("km"), " km")),
        ("Angebotsstatus", availability),
        ("Erstzulassung", car.get("registration") or "Ungeklärt"),
        ("Außenfarbe", car.get("color") or "Ungeklärt"),
        ("Luftlinie", "Ungeklärt" if km is None else
         f"ca. {round(km)} km (±{car['coordinate_accuracy_km']} km)"),
        ("Garantie", number(car.get("warranty_months"), " Monate")),
    ]
    details = "".join(f"<div><dt>{escape(label)}</dt><dd>{escape(str(value))}</dd></div>"
                      for label, value in values)
    criteria = "".join(f"<li>{label} · {status(checks[field])}</li>" for field, label in CHECKS.items()
                       if field != "acc" or checks[field] is not None)
    points_html = "".join(f"<li>{escape(label)} · {status(value)}</li>" for label, value in points.items())
    prices = "".join(
        f"<li>{display_time(entry['researched_at'])} · {number(entry.get('price'), ' €')} · "
        f"{AVAILABILITY[entry['availability']]}</li>" for entry in reversed(observations)
    )
    freshness = " · älter als 48 Stunden" if now - moment(car["researched_at"]) > timedelta(hours=48) else ""
    label = "Bewertung offen" if total is None else f"{total} von 6 Wünschen erfüllt · {sum(v is None for v in points.values())} offen"
    route = route_url(car["dealer"])
    dealer_id = (urlsplit(car["dealer_url"]).hostname or "").split(".")[0]
    photo = car.get("photo_url")
    photo_html = (f'<a class="vehicle-photo" href="{escape(car["url"], quote=True)}" aria-label="Originalinserat: Porsche Macan {escape(car["model"])} öffnen">'
                  f'<img src="{escape(photo, quote=True)}" alt="Porsche Macan {escape(car["model"])} in {escape(car.get("color") or "unbekannter Farbe")}, Foto aus dem Inserat" loading="lazy"></a>') if prominent and photo else ""
    confirmation = ('<div class="confirmed-banner"><span class="confirmed-check" aria-hidden="true">✓</span>'
                    '<span><strong>Alle Muss-Kriterien erfüllt</strong><small>Einzeln am Porsche-Originalinserat geprüft</small></span></div>') if prominent else ""
    minutes = DEALER_DRIVE_MINUTES.get(dealer_id)
    fixed_drive = not car.get("drive_time") and minutes is not None
    drive = car.get("drive_time") or ({"minutes": minutes, "source": route, "checked_at": DEALER_DRIVE_CHECKED_AT} if minutes else None)
    if drive:
        minutes = drive["minutes"]
        duration = f"{minutes // 60} Std. {minutes % 60:02d} Min." if minutes >= 60 else f"{minutes} Min."
        drive_label = (f'ca. {duration} · <a href="{escape(drive["source"], quote=True)}">Quelle</a>'
                       f' · {"Google Maps, Abfrage " + DEALERS[dealer_id].get("drive_checked_at", "09.11.2026") if fixed_drive else "Stand " + display_time(drive["checked_at"])}')
    else:
        drive_label = '<a href="{}">Fahrzeit in Routenplanung ansehen ↗</a>'.format(escape(route, quote=True))
    classes = "vehicle-card confirmed-card" if prominent else "vehicle-card"
    return f"""
    <article class="{classes}" id="{escape(car['key'])}">
      {photo_html}
      <div class="vehicle-content">
      {confirmation}
      <p class="eyebrow">{escape(state)} · Preisbereich {tier(car)} · Kilometerbereich {mileage_tier(car)} · {label}</p>
      <h3>Porsche Macan {car['model']}</h3>
      <p><a href="{escape(car['dealer_url'])}">{escape(car['dealer'])}</a> · Fahrzeit ab Eckental-Brand: {drive_label} · <a href="{escape(route, quote=True)}">Route ansehen ↗</a> · Bestand {escape(car['stock'])}</p>
      <dl>{details}</dl>
      <p class="muted">Status bei letzter Sichtung: {AVAILABILITY[car['availability']]}{escape(' · ' + car.get('availability_note', '')) if car.get('availability_note') else ''}{freshness}<br>
      Erstfund {display_time(observations[0]['researched_at'])} · Letzte Sichtung {display_time(car['researched_at'])}</p>
      <p><a href="{escape(car['url'])}">Originalinserat öffnen ↗</a></p>
      <details><summary>Muss-Kriterien und Bewertung</summary><ul>{criteria}</ul>
      {f'<ul>{points_html}</ul>' if points_html else '<p>Bewertung nach Bestätigung aller Muss-Kriterien.</p>'}</details>
      <details><summary>Preis- und Statusverlauf</summary><ol>{prices}</ol></details>
      </div>
    </article>"""


def status(value):
    return {True: "Bestätigt", False: "Verneint", None: "Ungeklärt"}[value]


def build(paths, output, build_id, now):
    snapshots, history, events = load_history(paths, now)
    latest = [entries[-1] for entries in history.values()]
    latest_research = snapshots[-1]["researched_at"] if snapshots else None
    confirmed, pending, archived = [], [], []
    for car in latest:
        if urlsplit(car["dealer_url"]).hostname.split(".")[0] not in ALLOWED_DEALERS or assess(car)[1]["distance"] is not True:
            continue
        state, _ = assess(car)
        result = score(car, latest, now)
        previous_sighting = (car["researched_at"] != latest_research or now - moment(car["researched_at"]) > timedelta(hours=48)) and car["availability"] == "listed"
        group = pending if previous_sighting and state == "Bestätigter Profiltreffer" else {"Bestätigter Profiltreffer": confirmed, "Prüfbedürftig": pending}.get(state, archived)
        group.append((car, result))
    groups = []
    for name, entries in (("Bestätigte Profiltreffer", confirmed), ("Prüfbedürftige Inserate", pending),
                          ("Archiv und ausgeschlossene Angebote", archived)):
        entries.sort(key=lambda row: (-(row[1][0] if row[1][0] is not None else -1),
                                      row[0].get("price") or math.inf))
        cards = "".join(card(car, history[car["key"]], result, now,
                             (car["researched_at"] != latest_research or now - moment(car["researched_at"]) > timedelta(hours=48)) and car["availability"] == "listed",
                             prominent=name == "Bestätigte Profiltreffer")
                        for car, result in entries)
        section_class = ' class="confirmed-results"' if name == "Bestätigte Profiltreffer" else ""
        groups.append(f"<section{section_class}><h2>{name} · {len(entries)}</h2>{cards or '<p>Keine Einträge im erfassten Bestand.</p>'}</section>")
    last = snapshots[-1] if snapshots else None
    research = display_time(last["researched_at"]) if last else "Kein Datenstand"
    verified = display_time(last["verified_at"]) if last else "Kein Datenstand"
    scope = escape(last["scope"]) if last else "Keine Stichprobe vorhanden"
    research_logs = sorted((ROOT / "research").glob("*.md"))
    research_link = (f'<p><a href="{REPO}/blob/main/research/{escape(research_logs[-1].name, quote=True)}">'
                     'Aktuelles Rechercheprotokoll ↗</a></p>') if research_logs else ""
    page = f"""<!doctype html>
<html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Macan Finder · Nürnberg</title>
<link rel="alternate" type="application/rss+xml" title="Macan Finder" href="feed.xml">
<link rel="stylesheet" href="style.css">
<main>
<header><p class="eyebrow">Gebrauchtwagen · Offizielle Porsche-Zentren</p><h1>Macan Finder</h1>
<p>Porsche Macan S und GTS · 200 km Luftlinie um Nürnberg</p></header>
<section class="notice" aria-label="Datenstand">
<strong>Manuell geprüfter Datenstand</strong>
<p>Der Seitenlauf verarbeitet die hinterlegten, manuell geprüften Erhebungen. Ein automatischer Porsche-Abruf ist nicht eingerichtet. Ob eine Erhebung vollständig oder eine Teilstichprobe ist, steht jeweils ausdrücklich im Rechercheumfang.</p>
<dl><div><dt>Recherche</dt><dd>{research}</dd></div><div><dt>Letzte erfolgreiche Prüfung</dt><dd>{verified}</dd></div>
<div><dt>Seite gebaut</dt><dd>{display_time(now.isoformat())}</dd></div>
<div><dt>Veröffentlichung</dt><dd><a href="{REPO}/deployments">GitHub-Protokoll</a></dd></div></dl>
<p>{scope}</p>
{research_link}
<p><a href="{escape(SEARCH)}">Porsche Finder öffnen ↗</a> · <a href="feed.xml">RSS für relevante Änderungen</a></p></section>
{dealer_overview()}
{''.join(groups)}
<section><h2>Suchprofil und Bewertung</h2>
<p>Muss: Macan III (Modellpflege ab 2021), Erstzulassung ab 2022, unfallfrei, Schwarz, Grau, Silber, Blau oder Kreide, ACC laut Inserat, Rückfahrkamera, höchstens zwei Vorbesitzer, 65.000 km und 85.000 €. Eine zusätzliche ACC-Funktionsprüfung ist nicht erforderlich.</p>
<p>Wünsche: bis 50.000 km, bis 65.000 €, ein Vorbesitzer, Surround View, Privacyverglasung und entfallene Modellbezeichnung. Alle sechs Wünsche zählen gleich; unbekannte Angaben werden als offen ausgewiesen.</p>
<p>Ein als nicht mehr auffindbar dokumentiertes Inserat bleibt in der Historie. Preisangaben sind Angebotspreise zum Sichtungszeitpunkt.</p></section>
<footer><a href="{REPO}">Projekt auf GitHub</a></footer>
</main></html>
"""
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / "style.css").write_bytes((ROOT / "style.css").read_bytes())
    (output / "build.txt").write_text(build_id + "\n", encoding="utf-8")
    rss(output, events)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    parser.add_argument("--build-id", default="local")
    args = parser.parse_args()
    build(sorted((ROOT / "snapshots").glob("*.json")), args.output, args.build_id, datetime.now(timezone.utc))
