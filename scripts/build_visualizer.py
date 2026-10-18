#!/usr/bin/env python3
"""Build visualizer/enigma-visualizer.html from its template and the repo's data.

The page embeds the wheel wirings from :mod:`enigma` and, from
phase1-stecker-calibration-v1, the stecker-climb settings, the scorer with its
published 1941 Army n-gram counts, and the constructed control key and
plaintext.  The numbers its prose quotes, from the climb limits to the recorded
results of the IC-rank, climb-power and indicator-sweep experiments, fill the
template's ``{{name}}`` slots from the same configs and artifacts.  Nothing is
restated by hand, so the page cannot drift from the pipeline without
``tests/test_visualizer.py`` noticing.

    python3 scripts/build_visualizer.py                # rewrite the committed page
    python3 scripts/build_visualizer.py --fragment X   # body-only copy, for hosts
                                                       # that supply their own <head>
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import enigma  # noqa: E402
import phase7  # noqa: E402
from stecker_scoring import index_of_coincidence  # noqa: E402
from stecker_traffic import normalize_plaintext  # noqa: E402

VISUALIZER = ROOT / "visualizer"
OUTPUT = VISUALIZER / "enigma-visualizer.html"
CALIBRATION = ROOT / "experiments/phase1-stecker-calibration-v1/config.json"
IC_RANK = ROOT / "artifacts/phase1-ic-rank-v1.json"
CLIMB_POWER = ROOT / "artifacts/phase1-fkqlz-length-calibration-v1.json"
INDICATOR_SWEEP = ROOT / "artifacts/phase1-indicator-sweep-v1.json"
DEMO_CONTROL = "constructed-army-style-plaintexts"
DEMO_MESSAGE = "CTRL-B1"
ARMY_WHEELS = ("I", "II", "III", "IV", "V")
SLOT = re.compile(r"\{\{(\w+)\}\}")

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
            "experiment_id": calibration["experiment_id"],
            "designator": message["designator"],
            "rotors": control["key"]["rotor_order"],
            "rings": control["key"]["rings"],
            "plugboard": control["key"]["plugboard"],
            "grundstellung": message["grundstellung"],
            "message_key": message["message_key"],
            "plaintext": message["plaintext"],
        },
    }


def _cell(cells: list[dict], **match) -> dict:
    return next(c for c in cells if all(c[key] == value for key, value in match.items()))


def measured(letters: int, pairs: int) -> dict:
    """The recorded results the page quotes, at the demo's length and plug count."""
    ic_rank = json.loads(IC_RANK.read_text(encoding="utf-8"))
    ranking = ic_rank["result"]["ic_rank_calibration"]
    ranked = _cell(ranking["cells"], length=letters, stecker_pairs=pairs)
    power = json.loads(CLIMB_POWER.read_text(encoding="utf-8"))
    recovered = _cell(power["result"]["climb_capability_calibration"]["cells"], length=letters, stecker_pairs=pairs)
    power_config = json.loads((ROOT / power["configuration"]["path"]).read_text(encoding="utf-8"))
    plaintext = normalize_plaintext(power_config["climb_capability_calibration"]["plaintext"], letters)
    sweep = json.loads(INDICATOR_SWEEP.read_text(encoding="utf-8"))
    return {
        "ic_rank": {
            "experiment_id": ic_rank["experiment_id"],
            "ranked_population": ranking["ranked_population"],
            "retained": ranking["retained"],
            "draws": ranked["draws"],
            "retention": ranked["mean_retention_probability"],
        },
        "climb_power": {
            "experiment_id": power["experiment_id"],
            "draws": recovered["draws"],
            "recovered": recovered["plaintexts_recovered_exactly"],
            "plaintext_ic": index_of_coincidence([plaintext.count(c) for c in enigma.A], len(plaintext)),
        },
        "indicator_sweep": {
            "experiment_id": sweep["experiment_id"],
            "daily_keys": sweep["result"]["evaluated_daily_keys"],
        },
    }


def prose(data: dict, facts: dict) -> dict[str, str]:
    """Text for each ``{{name}}`` slot in the template."""
    demo = data["demo"]
    ic_rank = facts["ic_rank"]
    climb_power = facts["climb_power"]
    return {
        "calibration_id": demo["experiment_id"],
        "demo_message": demo["designator"],
        "demo_letters": f"{len(demo['plaintext']):,}",
        "demo_pairs": str(len(demo["plugboard"].split())),
        "max_pairs": str(data["climb"]["max_pairs"]),
        "max_passes": str(data["climb"]["max_passes"]),
        "ranked_population": f"{ic_rank['ranked_population']:,}",
        "ic_rank_id": ic_rank["experiment_id"],
        "ic_rank_retained": f"{ic_rank['retained']:,}",
        "ic_rank_draws": str(ic_rank["draws"]),
        "ic_rank_retention": f"{100 * ic_rank['retention']:.0f}%",
        "climb_power_id": climb_power["experiment_id"],
        "climb_power_draws": str(climb_power["draws"]),
        "climb_power_recovered": str(climb_power["recovered"]),
        "climb_power_plaintext_ic": f"{climb_power['plaintext_ic']:.3f}",
        "indicator_sweep_id": facts["indicator_sweep"]["experiment_id"],
        "indicator_sweep_keys": f"{facts['indicator_sweep']['daily_keys']:,}",
    }


def render_fragment() -> str:
    data = page_data()
    demo = data["demo"]
    slots = prose(data, measured(len(demo["plaintext"]), len(demo["plugboard"].split())))
    template = (VISUALIZER / "template.html").read_text(encoding="utf-8")
    unused = set(slots) - set(SLOT.findall(template))
    if unused:
        raise ValueError(f"template has no slot for {sorted(unused)}")

    def fill(match: re.Match) -> str:
        if match.group(1) not in slots:
            raise ValueError(f"template slot {match.group(0)} has no value")
        return html.escape(slots[match.group(1)])

    # Slots first, so nothing in the embedded scripts can be mistaken for one.
    template = SLOT.sub(fill, template)
    data_json = json.dumps(data, separators=(",", ":"), sort_keys=True)
    replacements = {
        "/*@@DATA@@*/": f"const ENIGMA_DATA = {data_json};",
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
