# Macan Finder

Porsche Macan S und GTS im Umkreis von 100 km Luftlinie um Nürnberg. Berücksichtigt werden ausschließlich die Porsche Zentren Amberg, Bamberg, Bayreuth, Nürnberg-Fürth-Erlangen, Regensburg, Ingolstadt und Würzburg; der Radius wird zusätzlich aus dokumentierten Standortkoordinaten geprüft. Die [Webseite](https://warambuffet.github.io/macan-finder/) zeigt geprüfte Angebote, offene Kriterien, den Preisverlauf sowie die hinterlegten Fahrzeit-Richtwerte ab Eckental-Brand. Der [RSS-Feed](https://warambuffet.github.io/macan-finder/feed.xml) enthält ausschließlich erstmals bestätigte Profiltreffer und deren Preisänderungen. Für Benachrichtigungen den Feed in einem RSS-Reader abonnieren.

## Datenstand

Der Workflow baut die Seite täglich um 08:00 Uhr Europe/Berlin sowie nach Änderungen auf dem Hauptzweig. GitHub kann geplante Läufe verzögert starten und in öffentlichen Repositories bei 60 Tagen Inaktivität deaktivieren. Recherche, erfolgreiche Datenprüfung und Seitenbau werden getrennt angezeigt. Die erfolgreiche Veröffentlichung und ihre anschließende öffentliche Prüfung stehen im Deployment- und Laufprotokoll.

Eine automatisierte Porsche-Bestandserhebung ist nicht eingerichtet. Die [Abrufregeln](https://finder.porsche.com/robots.txt) sperren den allgemeinen API-Pfad und mehrere Suchfilter für Bots. Die [Porsche-Rechtshinweise](https://terms.porsche.com/de/de-DE/legal-notice) und die verlinkten [AGB](https://terms.porsche.com/medias/de/de-DE/Terms_and_Conditions.pdf) liefern keine bestätigte Freigabe für den geplanten automatisierten Abruf und die fortlaufende Weiterveröffentlichung. Einzelne Originalinserate ließen sich manuell prüfen. Ein belastbarer, freigegebener Bestandsfeed und ein End-to-End-Test seiner Erfassung sind für die Vollautomatisierung offen.

## Neue Bestandsaufnahme erfassen

1. Ein neues JSON unter `snapshots/` nach dem vorhandenen Beispiel anlegen. Nur nachweisbare Angaben aus offiziellen Porsche-Inseraten übernehmen und den Umfang der Stichprobe unter `scope` angeben. `researched_at` ist der Zeitpunkt der Quellensichtung, `verified_at` der Abschluss der Prüfung. Beide Zeitstempel brauchen eine Zeitzone.
2. `null` bedeutet nicht geprüft. Bei einem vollständig gesichteten Porsche-Inserat gilt: ACC aufgeführt = `true`, nicht aufgeführt = `false`; ein gesonderter Funktionsnachweis ist nicht erforderlich. Ein nicht eingesehenes oder unvollständig geladenes Inserat bleibt `null` und darf nicht als bestätigter Treffer erscheinen. Entscheidend ist die Erstzulassung ab 2022; das Produktionsjahr muss nicht ermittelt werden. `color_group` ist `allowed`, `excluded` oder `null`. Weißnahe oder mehrdeutige Farben bleiben offen. Der Radius nutzt die Händlerkoordinaten und deren geschätzte Genauigkeit in km. Schneidet der Unsicherheitsbereich die 100-km-Grenze, bleibt der Radius offen.
3. Jeder Eintrag braucht das Originalinserat, die offizielle Händlerseite und die Bestandsnummer. Händlerdomain und Bestandsnummer bilden den gemeinsamen Schlüssel für Finder- und Händlerlinks. Bei einem bestätigten Verschwinden `not_found` erfassen. `sold` erfordert eine ausdrückliche Bestätigung. Ein in einer späteren Stichprobe ausgelassenes Angebot behält seinen letzten datierten Status.
4. `python3 -m unittest -v` und `python3 finder.py` ausführen. Die Vorschau liegt unter `_site/index.html`. Nach einem Commit auf `main` baut und veröffentlicht GitHub Actions den validierten Stand.

Die Fahrzeit ab 90542 Eckental-Brand wird als `"drive_time": {"minutes": 65, "source": "https://…", "checked_at": "2026-11-09T10:00:00+01:00"}` erfasst. Minuten, HTTPS-Quellenlink und ein Prüfzeitpunkt mit Zeitzone sind gemeinsam erforderlich. Für die sieben ausgewählten Zentren sind datierte Google-Maps-Richtwerte zentral hinterlegt und werden nicht bei jedem Lauf neu berechnet. Es handelt sich um Momentaufnahmen, nicht um statistische Durchschnittswerte oder Live-Verkehrsvorhersagen. Eine spätere Einzelstichprobe darf einen zentralen Richtwert mit einer neu belegten Fahrzeit überschreiben. Würzburg: Koordinaten der Ladestation am Standort [Porschestraße 2](https://www.goingelectric.de/stromtankstellen/Deutschland/Estenfeld/Porsche-Zentrum-Wuerzburg-Porschestrasse-2/73603/), gerundet mit 1 km Unsicherheit.

Die Werte der ersten Stichprobe stammen aus dem [Finder-Inserat](https://finder.porsche.com/de/de-DE/details/porsche-macan-s-gebraucht-4GW7L5). Die [Händleranschrift](https://aschaffenburg.porsche.de/de/contact) liegt in Aschaffenburg. Die Entfernung wird mit Stadtkoordinaten und einer Unsicherheit von 10 km angenähert.

## 100 Punkte

- **Preis / Marktvergleich (35)**. Mindestens fünf andere innerhalb der letzten sieben Tage erfasste Inserate mit gleicher Variante, gleichem Erstzulassungsjahr und bis zu 10.000 km Laufleistungsdifferenz. Der Median der Angebotspreise ergibt 17,5 Punkte vor Rundung. Je Prozent Preisabweichung kommt ein Punkt hinzu oder fällt weg, begrenzt auf 0 bis 35. Sitze und Sport Chrono werden nicht als Vergleichsmerkmale verwendet.
- **Zustand / Historie (25)**. Manuelle Bewertung mit Begründung anhand belegter Wartung, technischer Prüfung, Reifen, Bremsen und Garantie.
- **Laufleistung / Erstzulassung (30)**. Höchstens 50.000 km sind ein Muss-Kriterium; fehlende Angaben bleiben ungeklärt. Bis zu 22 Punkte linear zwischen 0 und 50.000 km und bis zu 8 Punkte für das Erstzulassungsjahr, abzüglich 2 je Kalenderjahr.
- Sitze und Sport Chrono sind keine Such- oder Bewertungskriterien und werden in der Übersicht nicht angezeigt. Historische Rohdaten bleiben unverändert erhalten.
- **Farbe / Gesamteindruck (10)**. Manuelle Bewertung mit Begründung. Die obigen Rechenregeln sind Arbeitsannahmen und anhand echter Vergleichsfälle zu kalibrieren.

Ein Gesamtscore wird erst bei erfüllten Muss-Kriterien und vollständigen Teilwerten berechnet. Der RSS-Feed setzt erfüllte Muss-Kriterien voraus. Er erzeugt auch bei erneutem Seitenbau keine doppelten Ereignisse.

## Veröffentlichung und Rechte

Unter **Settings → Pages → Source** GitHub Actions auswählen. Der Build liest das Repository. Der Deployment-Job nutzt ausschließlich kurzlebige Berechtigungen für Pages und die Identitätsprüfung. Es gibt keine persönlichen Tokens, Passwörter, Benachrichtigungsadressen oder Repository-Schreibrechte im Workflow. Zum Pausieren den Workflow in GitHub Actions deaktivieren. Die zuletzt veröffentlichte Seite bleibt dabei verfügbar.


