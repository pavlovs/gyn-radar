# -*- coding: utf-8 -*-
"""Baut dist/index.html: data.js wird in die Seite inline eingebettet,
damit StatiCrypt EINE Datei verschluesseln kann."""

from pathlib import Path

BASE = Path(__file__).parent
html = (BASE / "index.html").read_text(encoding="utf-8")
data = (BASE / "data.js").read_text(encoding="utf-8")

marker = '<script src="data.js"></script>'
assert marker in html, "data.js-Einbindung nicht gefunden"
html = html.replace(marker, "<script>\n" + data + "</script>")

dist = BASE / "dist"
dist.mkdir(exist_ok=True)
(dist / "index.html").write_text(html, encoding="utf-8")
print("dist/index.html geschrieben (%d KB)" % (len(html) // 1024))
