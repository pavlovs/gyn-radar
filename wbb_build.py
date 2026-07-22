# -*- coding: utf-8 -*-
"""Einmal-Crawler: Ärztekammer-Berlin-Verzeichnis der Weiterbildungsbefugten.
Crawlt alle Seiten der Liste, behält aktive Befugnisse für Frauenheilkunde
und Geburtshilfe (inkl. Schwerpunkte) und schreibt wbb.json.

Läuft NICHT im Tagesscan — bei Bedarf manuell neu ausführen."""

import json
import re
import time
import urllib.request
from datetime import date
from html import unescape
from pathlib import Path

BASE = Path(__file__).parent
HOST = "https://www.aerztekammer-berlin.de"
START = (
    "/service-kontakt/verzeichnisse/verzeichnis-der-weiterbildungsbefugten"
    "?tx_vdinterfaces_authoritieslist%5Baction%5D=list"
    "&tx_vdinterfaces_authoritieslist%5Bcontroller%5D=Authority"
    "&cHash=53d8bc30a5f6a66cafa8b312ce86d834"
)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}

ITEM_RE = re.compile(r'<div class="vd-result-list__item[^"]*"', re.I)
PAGE_RE = re.compile(r'href="([^"]*currentPage%5D=(\d+)[^"]*)"')
TAG_RE = re.compile(r"<[^>]+>")
FH_RE = re.compile(r"Frauenheilkunde", re.I)


def fetch(path):
    req = urllib.request.Request(HOST + path.replace("&amp;", "&"), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    m = re.search(rb'charset=["\']?([a-zA-Z0-9-]+)', raw[:2000])
    enc = m.group(1).decode() if m else "utf-8"
    return raw.decode(enc, errors="replace")


def field(block, marker, cls):
    m = re.search(r'<span class="%s">([^<]+)</span>' % cls, block)
    return unescape(m.group(1)).strip() if m else ""


def parse_items(html):
    chunks = ITEM_RE.split(html)[1:]
    # split() mit Capturing wäre schöner; hier: Blöcke enden am nächsten Item
    items = []
    positions = [m.start() for m in ITEM_RE.finditer(html)]
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else pos + 6000
        block = html[pos:end]
        fach_m = re.search(r"<strong>((?:FA|SP)[^<]*)</strong>", block)
        fach = unescape(fach_m.group(1)).strip() if fach_m else ""
        if not FH_RE.search(fach):
            continue
        if "Abgelaufen" in block:
            continue
        name_m = re.search(r"<p><span><strong>([^<]+)</strong></span></p>", block)
        year_m = re.search(r"</strong>\s*</p>\s*<p>(\d{4})</p>", block)
        monate_m = re.search(r"<strong>(\d+\s*Monate?)</strong>", block)
        items.append(
            {
                "fach": fach,
                "name": unescape(name_m.group(1)).strip() if name_m else "",
                "einrichtung": field(block, "", "address__title"),
                "strasse": field(block, "", "address__street"),
                "ort": field(block, "", "address__location"),
                "umfang": monate_m.group(1) if monate_m else "",
                "seit": year_m.group(1) if year_m else "",
            }
        )
    return items


def main():
    # Verzeichnis ist nach Fachrichtung sortiert; Frauenheilkunde liegt um
    # Seite ~150-160. Strategie: per Paginator-Links vorspulen bis TARGET,
    # dann sequenziell lesen, bis nach Treffern 3 Leerseiten kommen.
    TARGET = 140
    links = {1: START}
    seen_pages, results = set(), []
    page, path = 1, START
    hits_started, empty_after_hits = False, 0
    while True:
        if page in seen_pages:
            break
        seen_pages.add(page)
        try:
            html = fetch(path)
        except Exception as e:
            print("[warn] Seite %d nicht ladbar: %s" % (page, e))
            break
        for href, num in PAGE_RE.findall(html):
            links[int(num)] = unescape(href)
        if page < TARGET:
            # Vorspulen: weitester bekannter Sprung Richtung TARGET
            nxt = max(
                (n for n in links if n <= TARGET and n not in seen_pages), default=None
            )
            if nxt is None:
                nxt = min((n for n in links if n not in seen_pages), default=None)
            if nxt is None:
                break
            print("Vorspulen: Seite %d -> %d" % (page, nxt))
            page, path = nxt, links[nxt]
            time.sleep(0.4)
            continue
        found = parse_items(html)
        results.extend(found)
        print(
            "Seite %3d: %2d FH-Treffer (gesamt %d)" % (page, len(found), len(results))
        )
        if found:
            hits_started, empty_after_hits = True, 0
        elif hits_started:
            empty_after_hits += 1
            if empty_after_hits >= 3:
                break
        nxt = page + 1
        if nxt not in links:
            print("[warn] kein Link zu Seite %d — Ende" % nxt)
            break
        page, path = nxt, links[nxt]
        time.sleep(0.4)

    dedup = {(r["name"], r["fach"], r["einrichtung"]): r for r in results}
    out = {
        "stand": date.today().isoformat(),
        "quelle": "aerztekammer-berlin.de, Verzeichnis der Weiterbildungsbefugten",
        "eintraege": sorted(dedup.values(), key=lambda r: r["name"]),
    }
    (BASE / "wbb.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("\n%d aktive Frauenheilkunde-Eintraege -> wbb.json" % len(dedup))


if __name__ == "__main__":
    main()
