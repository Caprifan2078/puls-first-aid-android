#!/usr/bin/env python3
from pathlib import Path
import json

assets = Path(__file__).resolve().parents[1] / "app/src/main/assets"
assert (assets / "index.html").stat().st_size > 300_000, "index.html missing or truncated"
G = json.loads((assets / "topics_v6.json").read_text("utf-8"))
M = json.loads((assets / "medicines_v6.json").read_text("utf-8"))
E = json.loads((assets / "emergency_v7_2.json").read_text("utf-8"))
assert len(G) >= 212, len(G)
assert len(M) >= 131, len(M)
assert len(E) >= 37, len(E)
assert len({g["id"] for g in G}) == len(G)
assert len({m["id"] for m in M}) == len(M)
missing = []
for g in G:
    for lang in ("ru", "en"):
        assert g.get(lang, {}).get("title")
        for directory, ext in [("illustrations", "jpg"), ("clips", "mp4")]:
            p = assets / "media" / directory / (g["id"] + "_" + lang + "." + ext)
            if not p.is_file() or p.stat().st_size < 500:
                missing.append(str(p))
for m in M:
    for lang in ("ru", "en"):
        assert m.get(lang, {}).get("title")
    p = assets / "media/medicines" / (m["id"] + ".jpg")
    if not p.is_file() or p.stat().st_size < 500:
        missing.append(str(p))
assert not missing, "\n".join(missing[:20])
print("OK", len(G), "topics", len(M), "medicines", len(E), "emergency cases")
