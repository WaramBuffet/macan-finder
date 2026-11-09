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
SEARCH = "https://finder.porsche.com/de/de-DE/search/macan?condition=used&model=macan&category=macan-s&category=macan-gts&position=N%C3%BCrnberg%2C49.45435%2C11.07346%2C100&equipment=acc-incl-pas"
RADIUS_KM = 100
ALLOWED_DEALERS = {"amberg", "bamberg", "bayreuth", "nuernberg", "regensburg", "ingolstadt"}
DEALER_DRIVE_MINUTES = {"amberg": 56, "bamberg": 39, "bayreuth": 44, "nuernberg": 19, "regensburg": 72, "ingolstadt": 65}
BERLIN = ZoneInfo("Europe/Berlin")
BOOLEAN_FIELDS = ("accident_free", "acc", "acc_working", "seats18", "chrono")
AVAILABILITY = {
    "listed": "Inseriert", "reserved": "Reserviert", "sold": "Als verkauft bestätigt",
    "not_found": "Nicht mehr auffindbar", "unknown": "Ungeklärt",
}
CHECKS = {
    "registration": "Erstzulassung ab 2022", "color_group": "Außenfarbe weder Rot noch Weiß",
    "distance": "Im Umkreis von 100 km", "accident_free": "Unfallfrei",
    "acc": "ACC laut Inserat vorhanden",
}
WEIGHTS = {
    "Preis / Marktvergleich": 30, "Zustand / Historie": 25,
    "Laufleistung / Erstzulassung": 20, "18-Wege-Sportsitze": 10,
    "Sport Chrono": 5, "Farbe / Gesamteindruck": 10,
}


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
    if not car["dealer"].startswith("Porsche Zentrum ") or not re.fullmatch(r"[A-Za-z0-9-]{1,40}", car["stock"]):
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
    for field, low, high in (("production_year", 2014, year), ("price", 1, 9999999),
                             ("km", 0, 999999), ("warranty_months", 0, 120),
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
    nlat, nlon = map(math.radians, (49.4521, 11.0767))
    hav = math.sin((lat - nlat) / 2)**2 + math.cos(lat) * math.cos(nlat) * math.sin((lon - nlon) / 2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1, hav)))


def assess(car):
    checks = {field: car.get(field) for field in ("accident_free", "acc")}
    for key, limit in ():
        value = car.get(key)
        checks[key] = None if value is None else value <= limit
    registration = car.get("registration")
    checks["registration"] = None if registration is None else int(registration[:4]) >= 2022
    color = car.get("color_group")
    checks["color_group"] = None if color is None else color == "allowed"
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
    if car.get("price") is None or car.get("km") is None:
        return "Offen"
    for name, price, km in (("A", 80000, 50000), ("B", 90000, 60000), ("C", 95000, 65000)):
        if car["price"] <= price and car["km"] <= km:
            return name
    return "Außerhalb"


def score(car, peers, as_of):
    if assess(car)[0] != "Bestätigter Profiltreffer":
        return None, {}
    candidates = [
        peer["price"] for peer in peers
        if peer["key"] != car["key"] and peer["availability"] == "listed"
        and as_of - moment(peer["researched_at"]) <= timedelta(days=7)
        and peer["model"] == car["model"] and peer.get("registration")
        and peer["registration"][:4] == car["registration"][:4]
        and peer.get("price") is not None and peer.get("km") is not None
        and abs(peer["km"] - car["km"]) <= 10000
        and car.get("seats18") is not None and car.get("chrono") is not None
        and all(peer.get(field) == car[field] for field in ("seats18", "chrono"))
    ]
    market = None
    if len(candidates) >= 5:
        market = round(max(0, min(30, 15 + 100 * (1 - car["price"] / median(candidates)))))
    mileage = max(0, round(12 * (1 - car["km"] / 65000)))
    age = as_of.astimezone(BERLIN).year - int(car["registration"][:4])
    points = {
        "Preis / Marktvergleich": market,
        "Zustand / Historie": car.get("condition_points"),
        "Laufleistung / Erstzulassung": mileage + max(0, 8 - 2 * age),
        "18-Wege-Sportsitze": None if car.get("seats18") is None else 10 * car["seats18"],
        "Sport Chrono": None if car.get("chrono") is None else 5 * car["chrono"],
        "Farbe / Gesamteindruck": car.get("impression_points"),
    }
    return (None if None in points.values() else sum(points.values())), points


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


def card(car, observations, result, now):
    state, checks = assess(car)
    total, points = result
    km = distance(car)
    values = [
        ("Preis", number(car.get("price"), " €")), ("Laufleistung", number(car.get("km"), " km")),
        ("Erstzulassung", car.get("registration") or "Ungeklärt"),
        ("Außenfarbe", car.get("color") or "Ungeklärt"),
        ("Luftlinie", "Ungeklärt" if km is None else
         f"ca. {round(km)} km (±{car['coordinate_accuracy_km']} km)"),
        ("Garantie", number(car.get("warranty_months"), " Monate")),
        ("18-Wege-Sportsitze", status(car.get("seats18"))), ("Sport Chrono", status(car.get("chrono"))),
    ]
    details = "".join(f"<div><dt>{escape(label)}</dt><dd>{escape(str(value))}</dd></div>"
                      for label, value in values)
    criteria = "".join(f"<li>{label} · {status(checks[field])}</li>" for field, label in CHECKS.items())
    points_html = "".join(
        f"<li>{escape(label)} · {'Offen' if value is None else f'{value}/{WEIGHTS[label]}'}"
        f"{escape(' · ' + car[notes]) if notes and car.get(notes) else ''}</li>"
        for label, value in points.items()
        for notes in [{"Zustand / Historie": "condition_note",
                       "Farbe / Gesamteindruck": "impression_note"}.get(label)]
    )
    prices = "".join(
        f"<li>{display_time(entry['researched_at'])} · {number(entry.get('price'), ' €')} · "
        f"{AVAILABILITY[entry['availability']]}</li>" for entry in reversed(observations)
    )
    freshness = " · älter als 48 Stunden" if now - moment(car["researched_at"]) > timedelta(hours=48) else ""
    label = "Score offen" if total is None else f"{total}/100 Punkte"
    route = "https://www.google.com/maps/dir/?" + urlencode({
        "api": "1", "origin": "Brand, 90542 Eckental, Deutschland",
        "destination": car["dealer"], "travelmode": "driving"})
    dealer_id = (urlsplit(car["dealer_url"]).hostname or "").split(".")[0]
    minutes = DEALER_DRIVE_MINUTES.get(dealer_id)
    drive = car.get("drive_time") or ({"minutes": minutes, "source": route, "checked_at": "2026-11-09T22:00:00+01:00"} if minutes else None)
    if drive:
        minutes = drive["minutes"]
        duration = f"{minutes // 60} Std. {minutes % 60:02d} Min." if minutes >= 60 else f"{minutes} Min."
        drive_label = (f'ca. {duration} · <a href="{escape(drive["source"], quote=True)}">Quelle</a>'
                       f' · {"Stand " + display_time(drive["checked_at"])}')
    else:
        drive_label = '<a href="{}">Fahrzeit in Routenplanung ansehen ↗</a>'.format(escape(route, quote=True))
    return f"""
    <article id="{escape(car['key'])}">
      <p class="eyebrow">{escape(state)} · Suchbereich {tier(car)} · {label}</p>
      <h3>Porsche Macan {car['model']}</h3>
      <p><a href="{escape(car['dealer_url'])}">{escape(car['dealer'])}</a> · Fahrzeit ab Eckental-Brand: {drive_label} · <a href="{escape(route, quote=True)}">Route ansehen ↗</a> · Bestand {escape(car['stock'])}</p>
      <dl>{details}</dl>
      <p class="muted">Status bei letzter Sichtung: {AVAILABILITY[car['availability']]}{freshness}<br>
      Erstfund {display_time(observations[0]['researched_at'])} · Letzte Sichtung {display_time(car['researched_at'])}</p>
      <p><a href="{escape(car['url'])}">Originalinserat öffnen ↗</a></p>
      <details><summary>Muss-Kriterien und Bewertung</summary><ul>{criteria}</ul>
      {f'<ul>{points_html}</ul>' if points_html else '<p>Bewertung nach Bestätigung aller Muss-Kriterien.</p>'}</details>
      <details><summary>Preis- und Statusverlauf</summary><ol>{prices}</ol></details>
    </article>"""


def status(value):
    return {True: "Bestätigt", False: "Verneint", None: "Ungeklärt"}[value]


def build(paths, output, build_id, now):
    snapshots, history, events = load_history(paths, now)
    latest = [entries[-1] for entries in history.values()]
    confirmed, pending, archived = [], [], []
    for car in latest:
        if urlsplit(car["dealer_url"]).hostname.split(".")[0] not in ALLOWED_DEALERS or assess(car)[1]["distance"] is not True:
            continue
        state, _ = assess(car)
        result = score(car, latest, now)
        group = {"Bestätigter Profiltreffer": confirmed, "Prüfbedürftig": pending}.get(state, archived)
        group.append((car, result))
    groups = []
    for name, entries in (("Bestätigte Profiltreffer", confirmed), ("Prüfbedürftige Inserate", pending),
                          ("Archiv und ausgeschlossene Angebote", archived)):
        entries.sort(key=lambda row: (-(row[1][0] if row[1][0] is not None else -1),
                                      row[0].get("price") or math.inf))
        cards = "".join(card(car, history[car["key"]], result, now) for car, result in entries)
        groups.append(f"<section><h2>{name} · {len(entries)}</h2>{cards or '<p>Keine Einträge im erfassten Bestand.</p>'}</section>")
    last = snapshots[-1] if snapshots else None
    research = display_time(last["researched_at"]) if last else "Kein Datenstand"
    verified = display_time(last["verified_at"]) if last else "Kein Datenstand"
    scope = escape(last["scope"]) if last else "Keine Stichprobe vorhanden"
    scoring = " · ".join(f"{escape(name)} {weight}" for name, weight in WEIGHTS.items())
    page = f"""<!doctype html>
<html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Macan Finder · Nürnberg</title>
<link rel="alternate" type="application/rss+xml" title="Macan Finder" href="feed.xml">
<link rel="stylesheet" href="style.css">
<main>
<header><p class="eyebrow">Gebrauchtwagen · Offizielle Porsche-Zentren</p><h1>Macan Finder</h1>
<p>Porsche Macan S und GTS · 100 km Luftlinie um Nürnberg</p></header>
<section class="notice" aria-label="Datenstand">
<strong>Manuell geprüfter Datenstand</strong>
<p>Der tägliche Seitenlauf verarbeitet die hinterlegten Stichproben. Ein automatischer Porsche-Abruf ist nicht eingerichtet. Die erfassten Inserate sind eine Stichprobe.</p>
<dl><div><dt>Recherche</dt><dd>{research}</dd></div><div><dt>Letzte erfolgreiche Prüfung</dt><dd>{verified}</dd></div>
<div><dt>Seite gebaut</dt><dd>{display_time(now.isoformat())}</dd></div>
<div><dt>Veröffentlichung</dt><dd><a href="{REPO}/deployments">GitHub-Protokoll</a></dd></div></dl>
<p>{scope}</p>
<p><a href="{escape(SEARCH)}">Porsche Finder öffnen ↗</a> · <a href="feed.xml">RSS für relevante Änderungen</a></p></section>
{''.join(groups)}
<section><h2>Suchprofil und Bewertung</h2>
<p>Erstzulassung ab 2022, unfallfrei, keine roten oder weißen Fahrzeuge, ACC laut Inserat. Erwünscht sind 18-Wege-Sportsitze und Sport Chrono.</p>
<p>A bis 80.000 € und 50.000 km · B bis 90.000 € und 60.000 km · C bis 95.000 € und 65.000 km.</p>
<p>100 Punkte · {scoring}. Bei fehlenden Nachweisen bleibt der jeweilige Teilwert und gegebenenfalls der Gesamtscore offen.</p>
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


