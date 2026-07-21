# -*- coding: utf-8 -*-
"""GYN RADAR Berlin — scans job boards for Gyn postings IN BERLIN
and writes data.js for index.html.

Stdlib only. Run:  python scan.py
"""

import json
import re
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Berliner Adresse (PLZ + "Berlin") auf der Stellen-Detailseite
BERLIN_RE = re.compile(r"\d{5}\s+Berlin\b")
TYPE_PATTERNS = [
    ("Assistenzarzt", re.compile(r"assistenz|weiterbildung", re.I)),
    ("Oberarzt", re.compile(r"oberarzt|oberärzt", re.I)),
    ("Facharzt", re.compile(r"facharzt|fachärzt", re.I)),
    ("Famulatur", re.compile(r"famulatur", re.I)),
    ("PJ", re.compile(r"praktisches jahr|\bpj\b", re.I)),
]


def fetch(url, timeout=15):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "de"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace"), r.status


class LinkCollector(HTMLParser):
    """Collects (href, text) for every <a>."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._buf = []

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = re.sub(r"\s+", " ", " ".join(self._buf)).strip()
            self.links.append((self._href, text))
            self._href = None


def anchors(html):
    p = LinkCollector()
    p.feed(html)
    return p.links


def classify(title):
    for label, pat in TYPE_PATTERNS:
        if pat.search(title):
            return label
    return "Sonstige"


def absolutize(href, base):
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")


def scan_aerzteblatt():
    """Ärzteblatt-Stellenmarkt: Assistenzarzt Frauenheilkunde, bundesweit (Berlin selten -> alles zeigen)."""
    url = (
        "https://aerztestellen.aerzteblatt.de/de/stellen/"
        "assistenzarzt-arzt-weiterbildung/frauenheilkunde-und-geburtshilfe-uebersicht"
    )
    html, _ = fetch(url)
    jobs = []
    for href, text in anchors(html):
        if "/stelle/" in href and len(text) > 15:
            jobs.append(
                {
                    "source": "Ärzteblatt-Stellenmarkt",
                    "title": text,
                    "url": absolutize(href, "https://aerztestellen.aerzteblatt.de"),
                    "type": classify(text),
                }
            )
    return jobs


def scan_praktischarzt():
    """praktischArzt: alle Gyn-Angebote im Raum Berlin (inkl. Famulatur/PJ)."""
    url = "https://www.praktischarzt.de/gynaekologie-geburtshilfe/berlin/"
    html, _ = fetch(url)
    jobs = []
    for href, text in anchors(html):
        if "/job/" in href and len(text) > 15:
            jobs.append(
                {
                    "source": "praktischArzt (Berlin)",
                    "title": text,
                    "url": absolutize(href, "https://www.praktischarzt.de"),
                    "type": classify(text),
                }
            )
    return jobs


# DRK-Jobportal ist eine JS-SPA (keine statischen Links) — nicht scannbar
# ohne Browser; DRK-Stellen tauchen auf praktischArzt/Ärzteblatt auf.
SCANNERS = [scan_aerzteblatt, scan_praktischarzt]


def is_berlin(job):
    """Nur-Berlin-Filter: Titel nennt Berlin, sonst muss die Detailseite
    eine Berliner Adresse (PLZ + Berlin) enthalten."""
    if "berlin" in job["title"].lower():
        return True
    try:
        html, _ = fetch(job["url"], timeout=12)
        time.sleep(0.4)
        return bool(BERLIN_RE.search(html))
    except Exception:
        # Detailseite nicht lesbar -> im Zweifel behalten, wenn die Quelle
        # schon regional auf Berlin gefiltert ist
        return job["source"].endswith("(Berlin)")


def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        key = j["url"]
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


def main():
    today = date.today().isoformat()
    state_file = BASE / "state.json"
    state = (
        json.loads(state_file.read_text(encoding="utf-8"))
        if state_file.exists()
        else {"first_seen": {}}
    )

    jobs, errors = [], []
    for scanner in SCANNERS:
        try:
            found = scanner()
            jobs.extend(found)
            print("[ok]   %-28s %d Treffer" % (scanner.__name__, len(found)))
        except Exception as e:
            errors.append("%s: %s" % (scanner.__name__, e))
            print("[FAIL] %-28s %s" % (scanner.__name__, e))
    jobs = dedupe(jobs)
    before = len(jobs)
    jobs = [j for j in jobs if is_berlin(j)]
    print("[filter] nur Berlin: %d von %d behalten" % (len(jobs), before))

    for j in jobs:
        j["first_seen"] = state["first_seen"].setdefault(j["url"], today)
        j["is_new"] = j["first_seen"] == today

    hospitals = json.loads((BASE / "hospitals.json").read_text(encoding="utf-8"))

    data = {
        "scanned_at": today,
        "jobs": jobs,
        "errors": errors,
        "hospitals": hospitals,
    }
    (BASE / "data.js").write_text(
        "window.RADAR = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("\n%d Stellen -> data.js geschrieben. index.html oeffnen." % len(jobs))


if __name__ == "__main__":
    main()
