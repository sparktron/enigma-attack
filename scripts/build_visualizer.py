#!/usr/bin/env python3
"""Build visualizer/enigma-visualizer.html from its template and the repo's data.

The page embeds the wheel wirings from :mod:`enigma` and, from
phase1-stecker-calibration-v1, the stecker-climb settings, the scorer with its
published 1941 Army n-gram counts, and the constructed control key and
plaintext.  Nothing is restated by hand, so the page cannot drift from the
pipeline without ``tests/test_visualizer.py`` noticing.

    python3 scripts/build_visualizer.py                # rewrite the committed page
    python3 scripts/build_visualizer.py --fragment X   # body-only copy, for hosts
                                                       # that supply their own <head>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import enigma  # noqa: E402
import phase7  # noqa: E402

VISUALIZER = ROOT / "visualizer"
OUTPUT = VISUALIZER / "enigma-visualizer.html"
CALIBRATION = ROOT / "experiments/phase1-stecker-calibration-v1/config.json"
DEMO_CONTROL = "constructed-army-style-plaintexts"
DEMO_MESSAGE = "CTRL-B1"
ARMY_WHEELS = ("I", "II", "III", "IV", "V")

STANDALONE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
</head>
<body>
"""
STANDALONE_TAIL = "</body>\n</html>\n"


def page_data() -> dict:
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    scorer = calibration["scorer"]
    control = next(c for c in calibration["positive_controls"] if c["id"] == DEMO_CONTROL)
    message = next(m for m in control["messages"] if m["designator"] == DEMO_MESSAGE)
    climb = calibration["climb"]
    if "first_plug" in climb:
        raise ValueError("visualizer/enigma-core.js does not restate climb.first_plug")
    return {
        "rotors": {name: list(enigma.ROTOR_WIRINGS[name]) for name in ARMY_WHEELS},
        "reflector": enigma.REFLECTOR_WIRINGS["B"],
        "scorer": {
            "additive_smoothing": scorer["additive_smoothing"],
            "bigram_weight": scorer["bigram_weight"],
            "trigram_weight": scorer["trigram_weight"],
            "bigram_counts": phase7.load_counts(ROOT / scorer["bigram_counts"], 2),
            "trigram_counts": phase7.load_counts(ROOT / scorer["trigram_counts"], 3),
        },
        "climb": {key: climb[key] for key in ("phases", "max_pairs", "max_passes", "minimum_gain")},
        "demo": {
            "source": f"{calibration['experiment_id']} / {control['id']} / {message['designator']}",
            "rotors": control["key"]["rotor_order"],
            "rings": control["key"]["rings"],
            "plugboard": control["key"]["plugboard"],
            "grundstellung": message["grundstellung"],
            "message_key": message["message_key"],
            "plaintext": message["plaintext"],
        },
    }


def render_fragment() -> str:
    template = (VISUALIZER / "template.html").read_text(encoding="utf-8")
    data = json.dumps(page_data(), separators=(",", ":"), sort_keys=True)
    replacements = {
        "/*@@DATA@@*/": f"const ENIGMA_DATA = {data};",
        "/*@@CORE@@*/": (VISUALIZER / "enigma-core.js").read_text(encoding="utf-8"),
        "/*@@APP@@*/": (VISUALIZER / "app.js").read_text(encoding="utf-8"),
    }
    for marker, text in replacements.items():
        if template.count(marker) != 1:
            raise ValueError(f"template must contain {marker} exactly once")
        template = template.replace(marker, text)
    return template


def render_standalone() -> str:
    return STANDALONE_HEAD + render_fragment() + STANDALONE_TAIL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fragment", type=pathlib.Path, help="also write a body-only copy here")
    args = parser.parse_args(argv)
    OUTPUT.write_text(render_standalone(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    if args.fragment:
        args.fragment.write_text(render_fragment(), encoding="utf-8")
        print(f"wrote {args.fragment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
