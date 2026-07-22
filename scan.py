# -*- coding: utf-8 -*-
"""GYN RADAR Berlin — scans job boards for Gyn postings IN BERLIN
and writes data.js for index.html.

Stdlib only. Run:  python scan.py
"""

import json
import os
import re
import time
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


GYN_RE = re.compile(r"gyn|geburt|frauenheil", re.I)
# Nicht-ärztliche Rollen, die in Gyn-Slugs auftauchen (Pflege etc.)
EXCLUDE_RE = re.compile(
    r"pfleg|hebamme|entbindung|mfa|fachangestellt|sekret|leitung|psycholog|sozial",
    re.I,
)
TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.I)


def detail_title(url, fallback):
    """Echten Stellentitel von der Detailseite holen (nur fuer wenige Treffer)."""
    try:
        html, _ = fetch(url, timeout=12)
        time.sleep(0.3)
        m = TITLE_RE.search(html)
        if m:
            from html import unescape

            t = re.sub(r"\s+", " ", unescape(m.group(1))).strip()
            return (
                re.sub(r"\s*[|–-]\s*(Vivantes|Charité|DRK|Karriere).*$", "", t)
                or fallback
            )
    except (OSError, http.client.HTTPException):
        pass
    return fallback


def slug_title(href):
    slug = href.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"-+[0-9]+$", "", slug)
    return slug.replace("--", " ").replace("-", " ").strip()


def scan_drk():
    """DRK Kliniken Berlin: Stellen aus der sitemap.xml (Portal selbst ist JS)."""
    xml, _ = fetch("https://jobs.drk-kliniken-berlin.de/sitemap.xml")
    jobs = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        slug = loc.rsplit("/", 1)[-1]
        if (
            "/stellenangebote/" in loc
            and GYN_RE.search(slug)
            and not EXCLUDE_RE.search(slug)
        ):
            jobs.append(
                {
                    "source": "DRK Kliniken Berlin",
                    "title": slug_title(loc),
                    "url": loc,
                    "type": classify(slug),
                    "berlin_ok": True,
                }
            )
    return jobs


def scan_vivantes():
    """Vivantes-Karriereportal: /jobs/ Seiten crawlen, Gyn-Slugs filtern.
    Alle Vivantes-Standorte liegen in Berlin."""
    base = "https://karriere.vivantes.de"
    first, _ = fetch(base + "/jobs/")
    pages = [int(n) for n in re.findall(r"/jobs/page/(\d+)/", first)]
    last = min(max(pages) if pages else 1, 80)
    seen, jobs = set(), []
    for page in range(1, last + 1):
        html = first if page == 1 else None
        if html is None:
            try:
                html, _ = fetch("%s/jobs/page/%d/" % (base, page))
                time.sleep(0.2)
            except (OSError, http.client.HTTPException):
                continue
        for href in re.findall(r'href="(/stellenangebote/detail/[^"]+)"', html):
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            if href in seen or not GYN_RE.search(slug) or EXCLUDE_RE.search(slug):
                continue
            seen.add(href)
            url = base + href
            jobs.append(
                {
                    "source": "Vivantes",
                    "title": detail_title(url, slug_title(href)),
                    "url": url,
                    "type": classify(slug),
                    "berlin_ok": True,
                }
            )
    return jobs


def scan_charite():
    """Charité-Karriereportal: serverseitig gerenderte Stellenliste."""
    base = "https://karriere.charite.de"
    html, _ = fetch(base + "/stellenangebote")
    jobs = []
    for href, text in anchors(html):
        if "/stellenangebote/detail/" not in href:
            continue
        probe = text + " " + href
        if GYN_RE.search(probe) and not EXCLUDE_RE.search(probe):
            url = absolutize(href, base)
            jobs.append(
                {
                    "source": "Charité",
                    "title": text
                    if len(text) > 15
                    else detail_title(url, text or href),
                    "url": url,
                    "type": classify(probe),
                    "berlin_ok": True,
                }
            )
    return jobs


SCANNERS = [scan_aerzteblatt, scan_praktischarzt, scan_drk, scan_vivantes, scan_charite]


def is_berlin(job):
    """Nur-Berlin-Filter: Die Detailseite muss eine Berliner Adresse
    (PLZ + Berlin) enthalten — ein "Berlin" im Titel reicht nicht.
    Nicht verifizierbar (Detailseite 2x nicht lesbar) -> verwerfen;
    der naechste Tagesscan holt es nach."""
    for attempt in (1, 2):
        try:
            html, _ = fetch(job["url"], timeout=12)
            time.sleep(0.4)
            return bool(BERLIN_RE.search(html))
        except (OSError, http.client.HTTPException) as e:
            if attempt == 2:
                print(
                    "[warn] Detailseite nicht lesbar, verworfen: %s (%s)"
                    % (job["url"], e)
                )
                return False
            time.sleep(1.5)


def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        key = j["url"]
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


def write_atomic(path, text):
    """Temp schreiben, dann atomar ersetzen — nie das Original zerstoeren."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_state(state_file):
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(state.get("first_seen"), dict):
            raise ValueError("first_seen fehlt/kein dict")
        return state
    except FileNotFoundError:
        return {"first_seen": {}}
    except Exception as e:
        print("[warn] state.json unbrauchbar (%s) — starte mit leerem Zustand" % e)
        return {"first_seen": {}}


def main():
    today = date.today().isoformat()
    state_file = BASE / "state.json"
    state = load_state(state_file)

    health = state.setdefault("source_health", {})
    jobs, errors = [], []
    for scanner in SCANNERS:
        name = scanner.__name__.replace("scan_", "")
        try:
            found = scanner()
            jobs.extend(found)
            health[name] = {"last_ok": today, "count": len(found)}
            print("[ok]   %-28s %d Treffer" % (scanner.__name__, len(found)))
        except Exception as e:
            errors.append("%s: %s" % (scanner.__name__, e))
            health.setdefault(name, {})["error"] = today
            print("[FAIL] %-28s %s" % (scanner.__name__, e))
    jobs = dedupe(jobs)
    before = len(jobs)
    # Nur Assistenzarzt/Weiterbildung — Famulatur/PJ/Facharzt/Oberarzt sind irrelevant
    jobs = [j for j in jobs if j["type"] == "Assistenzarzt"]
    print("[filter] nur Assistenzarzt: %d von %d behalten" % (len(jobs), before))
    before = len(jobs)
    jobs = [j for j in jobs if j.pop("berlin_ok", False) or is_berlin(j)]
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
        "source_health": health,
    }
    write_atomic(
        BASE / "data.js",
        "window.RADAR = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
    )
    write_atomic(state_file, json.dumps(state, ensure_ascii=False, indent=1))
    print("\n%d Stellen -> data.js geschrieben. index.html oeffnen." % len(jobs))


if __name__ == "__main__":
    main()
