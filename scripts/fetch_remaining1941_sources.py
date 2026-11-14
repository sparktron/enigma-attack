#!/usr/bin/env python3
"""Fetch immutable primary-source snapshots; offline analysis never fetches again."""
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.cryptocellar.org/bgac/"
PAGES = [
    "1941-msg-list-unbroken.html", "1941-msg-list.html", "g-army-messages.html",
    "g-army-july-1941.html", "e-keys-jun-oct-1941.html", "e-keys-july-1941.html",
    "the-awtzk-znlzt-breaks.html", "the-fmngi-break.html",
]
SCANS = [
    "22061941-003", "28061941-053", "03071941-087", "05071941-100",
    "09071941-138", "09071941-140", "11071941-187", "11071941-189",
    "20071941-242", "31071941-285",
]


def main():
    root = ROOT / "data/remaining-1941/sources"
    root.mkdir(parents=True, exist_ok=True)
    if (root / "manifest.json").exists():
        raise SystemExit("Snapshot exists; use a new dated directory to refresh it.")
    manifest = []
    for rel in PAGES + [f"spruch/{x}-in.pdf" for x in SCANS]:
        raw = urllib.request.urlopen(BASE + rel, timeout=60).read()
        path = root / rel.replace("/", "_")
        path.write_bytes(raw)
        manifest.append(dict(url=BASE + rel, path=str(path.relative_to(ROOT)),
                             sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                             retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
