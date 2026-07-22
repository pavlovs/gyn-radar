# GYN RADAR Berlin

Stellenscan + Bewerbungs-Tracker für die Facharzt-Weiterbildung Gynäkologie & Geburtsmedizin — **nur Berlin**.

## Nutzung (gehostet)

Die Seite wird per GitHub Actions täglich neu gescannt und passwortgeschützt (StatiCrypt/AES) auf GitHub Pages veröffentlicht. Einfach die Pages-URL öffnen, Passwort eingeben (bleibt 90 Tage gespeichert), fertig — funktioniert auch am Handy.

- **Stellen**: gescannt von Ärzteblatt-Stellenmarkt, praktischArzt und direkt von den Karriereportalen Vivantes (52 Seiten), Charité und DRK (Sitemap); nur Assistenzarzt, nur Berlin; „Neu"-Badge für frisch entdeckte Stellen.
- **Push-Alarm**: findet der Tagesscan neue Stellen, geht eine ntfy.sh-Nachricht raus (Topic = Actions-Secret `NTFY_TOPIC`; in der ntfy-App oder unter ntfy.sh/&lt;topic&gt; abonnieren).
- **Karte**: alle Kliniken auf einer OpenStreetMap (Leaflet), Markerfarbe = Bewerbungsstatus.
- **Kliniken**: alle 18 Berliner Häuser mit Gyn/Geburtshilfe, mit Website-/Karriere-/kununu-Links.
- **Nachfassen**: „Beworben" stempelt das Datum; nach 14 Tagen ohne Statuswechsel erscheint ein Nachfassen-Hinweis.
- **Tracker**: Status (Vorbereiten/Beworben/Hospitation/Gespräch/Zusage/Absage) + Notizen pro Klinik. Liegt nur im Browser (localStorage) — nichts davon landet im Repo. Backup-Button im Dashboard.

## Nutzung (lokal)

`scan.bat` doppelklicken — scannt und öffnet das Dashboard. Nur Python 3, keine Abhängigkeiten.

## Strategie-Hinweis

Offene Assistenzarzt-Gyn-Stellen werden in Berlin selten öffentlich ausgeschrieben. Der wirksamste Kanal ist die **Initiativbewerbung an alle Kliniken** im Dashboard — DRK Westend hat dafür eine ständige Online-Ausschreibung. Der Scan ist das Sicherheitsnetz für alles, was doch öffentlich erscheint.

## Dateien

- `scan.py` — Scanner (stdlib only): Jobbörsen abgrasen, Nur-Berlin-Filter (Detailseite muss Berliner PLZ+Adresse enthalten), schreibt `data.js`; `state.json` = First-seen-Datum je Stelle
- `hospitals.json` — kuratierte Klinikliste (Quelle: krankenhaus.de-Geburtskliniken-Verzeichnis + Klinik-Websites, Links verifiziert 21.07.2026)
- `index.html` — Dashboard (single file, kein Framework)
- `build.py` + `.github/workflows/scan.yml` — täglicher CI-Scan, Verschlüsselung, Pages-Deploy; Passwort liegt als Actions-Secret `RADAR_PASSWORD`
