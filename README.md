# Macan Finder

Porsche Macan S und GTS im Umkreis von 100 km Luftlinie um Nürnberg. Die [Webseite](https://warambuffet.github.io/macan-finder/) zeigt geprüfte Angebote, offene Kriterien und den Preisverlauf. Der [RSS-Feed](https://warambuffet.github.io/macan-finder/feed.xml) enthält ausschließlich erstmals bestätigte Profiltreffer und deren Preisänderungen. Für Benachrichtigungen den Feed in einem RSS-Reader abonnieren.

## Datenstand

Der Workflow baut die Seite täglich um 08:00 Uhr Europe/Berlin sowie nach Änderungen auf dem Hauptzweig. GitHub kann geplante Läufe verzögert starten und in öffentlichen Repositories bei 60 Tagen Inaktivität deaktivieren. Recherche, erfolgreiche Datenprüfung und Seitenbau werden getrennt angezeigt. Die erfolgreiche Veröffentlichung und ihre anschließende öffentliche Prüfung stehen im Deployment- und Laufprotokoll.

Eine automatisierte Porsche-Bestandserhebung ist nicht eingerichtet. Die [Abrufregeln](https://finder.porsche.com/robots.txt) sperren den allgemeinen API-Pfad und mehrere Suchfilter für Bots. Die [Porsche-Rechtshinweise](https://terms.porsche.com/de/de-DE/legal-notice) und die verlinkten [AGB](https://terms.porsche.com/medias/de/de-DE/Terms_and_Conditions.pdf) liefern keine bestätigte Freigabe für den geplanten automatisierten Abruf und die fortlaufende Weiterveröffentlichung. Einzelne Originalinserate ließen sich manuell prüfen. Ein belastbarer, freigegebener Bestandsfeed und ein End-to-End-Test seiner Erfassung sind für die Vollautomatisierung offen.

## Neue Bestandsaufnahme erfassen

1. Ein neues JSON unter `snapshots/` nach dem vorhandenen Beispiel anlegen. Nur nachweisbare Angaben aus offiziellen Porsche-Inseraten übernehmen und den Umfang der Stichprobe unter `scope` angeben. `researched_at` ist der Zeitpunkt der Quellensichtung, `verified_at` der Abschluss der Prüfung. Beide Zeitstempel brauchen eine Zeitzone.
2. `null` bedeutet ungeklärt. ACC muss im Inserat angegeben sein; ein gesonderter Funktionsnachweis ist nicht erforderlich. Entscheidend ist die Erstzulassung ab 2022; das Produktionsjahr muss nicht ermittelt werden. `color_group` ist `allowed`, `excluded` oder `null`. Weißnahe oder mehrdeutige Farben bleiben offen. Der Radius nutzt die Händlerkoordinaten und deren geschätzte Genauigkeit in km. Schneidet der Unsicherheitsbereich die 100-km-Grenze, bleibt der Radius offen.
3. Jeder Eintrag braucht das Originalinserat, die offizielle Händlerseite und die Bestandsnummer. Händlerdomain und Bestandsnummer bilden den gemeinsamen Schlüssel für Finder- und Händlerlinks. Bei einem bestätigten Verschwinden `not_found` erfassen. `sold` erfordert eine ausdrückliche Bestätigung. Ein in einer späteren Stichprobe ausgelassenes Angebot behält seinen letzten datierten Status.
4. `python3 -m unittest -v` und `python3 finder.py` ausführen. Die Vorschau liegt unter `_site/index.html`. Nach einem Commit auf `main` baut und veröffentlicht GitHub Actions den validierten Stand.

Die optionale Fahrzeit ab 90542 Eckental-Brand wird als `"drive_time": {"minutes": 65, "source": "https://…", "checked_at": "2026-11-09T10:00:00+01:00"}` erfasst. Minuten, HTTPS-Quellenlink und ein Prüfzeitpunkt mit Zeitzone sind gemeinsam erforderlich. Nur aus einer geeigneten Routenberechnung übernehmen; die Beispielzahl ist kein tatsächlicher Fahrtwert. Ohne Nachweis zeigt die Übersicht „noch nicht ermittelt“ und einen Link zur Routenplanung. Die Werte sind keine Live-Verkehrsvorhersage.

Die Werte der ersten Stichprobe stammen aus dem [Finder-Inserat](https://finder.porsche.com/de/de-DE/details/porsche-macan-s-gebraucht-4GW7L5). Die [Händleranschrift](https://aschaffenburg.porsche.de/de/contact) liegt in Aschaffenburg. Die Entfernung wird mit Stadtkoordinaten und einer Unsicherheit von 10 km angenähert.

## 100 Punkte

- **Preis / Marktvergleich (30)**. Mindestens fünf andere innerhalb der letzten sieben Tage erfasste Inserate mit gleicher Variante, gleichem Erstzulassungsjahr, gleich bestätigten Ausstattungsmerkmalen für Sitze und Sport Chrono und bis zu 10.000 km Laufleistungsdifferenz. Der Median der Angebotspreise ergibt 15 Punkte. Je Prozent Preisabweichung kommt ein Punkt hinzu oder fällt weg, begrenzt auf 0 bis 30.
- **Zustand / Historie (25)**. Manuelle Bewertung mit Begründung anhand belegter Wartung, technischer Prüfung, Reifen, Bremsen und Garantie.
- **Laufleistung / Erstzulassung (20)**. Bis zu 12 Punkte linear zwischen 0 und 65.000 km. Bis zu 8 Punkte für das Erstzulassungsjahr, abzüglich 2 je Kalenderjahr.
- **18-Wege-Sportsitze (10) und Sport Chrono (5)**. Volle Punkte für bestätigte Ausstattung, null Punkte bei belegtem Fehlen, sonst offen.
- **Farbe / Gesamteindruck (10)**. Manuelle Bewertung mit Begründung. Die obigen Rechenregeln sind Arbeitsannahmen und anhand echter Vergleichsfälle zu kalibrieren.

Ein Gesamtscore wird erst bei erfüllten Muss-Kriterien und vollständigen Teilwerten berechnet. Der RSS-Feed setzt erfüllte Muss-Kriterien voraus. Er erzeugt auch bei erneutem Seitenbau keine doppelten Ereignisse.

## Veröffentlichung und Rechte

Unter **Settings → Pages → Source** GitHub Actions auswählen. Der Build liest das Repository. Der Deployment-Job nutzt ausschließlich kurzlebige Berechtigungen für Pages und die Identitätsprüfung. Es gibt keine persönlichen Tokens, Passwörter, Benachrichtigungsadressen oder Repository-Schreibrechte im Workflow. Zum Pausieren den Workflow in GitHub Actions deaktivieren. Die zuletzt veröffentlichte Seite bleibt dabei verfügbar.


