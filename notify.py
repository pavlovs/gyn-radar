# -*- coding: utf-8 -*-
"""Push-Benachrichtigung via ntfy.sh, wenn der Scan NEUE Stellen gefunden hat.
Topic kommt aus der Umgebungsvariable NTFY_TOPIC (Actions-Secret). Ohne Topic: no-op."""

import json
import os
import re
import urllib.request
from pathlib import Path

topic = os.environ.get("NTFY_TOPIC", "").strip()
if not topic:
    print("[notify] kein NTFY_TOPIC gesetzt — übersprungen")
    raise SystemExit(0)

raw = (Path(__file__).parent / "data.js").read_text(encoding="utf-8")
data = json.loads(re.sub(r"^window\.RADAR\s*=\s*", "", raw.strip()).rstrip(";"))
new = [j for j in data.get("jobs", []) if j.get("is_new")]
if not new:
    print("[notify] nichts Neues")
    raise SystemExit(0)

lines = ["%s (%s)" % (j["title"][:80], j["source"]) for j in new[:5]]
body = "\n".join(lines)
req = urllib.request.Request(
    "https://ntfy.sh/" + topic,
    data=body.encode("utf-8"),
    headers={
        "Title": "GYN RADAR: %d neue Stelle(n) in Berlin" % len(new),
        "Click": "https://pavlovs.github.io/gyn-radar/",
        "Tags": "hospital",
    },
)
with urllib.request.urlopen(req, timeout=15) as r:
    print("[notify] gesendet (%d neu, HTTP %d)" % (len(new), r.status))
