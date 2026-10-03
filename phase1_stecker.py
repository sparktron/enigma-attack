#!/usr/bin/env python3
"""Phase 1 standard-Enigma sweeps and the stecker hill-climb.

``phase1.py`` established the Army indicator procedure and emitted a scope
certificate, but its committed certificate covers 120 daily keys with fixed
plugboards, so the standard-Enigma baseline has effectively never been run.
This module supplies the missing machinery and, more importantly, measures what
it can and cannot do before pointing it at the corpus.

Two formulations of the same attack are implemented, because they behave
completely differently and only one of them works:

``indicator_coupled``
    The formulation ``phase1.py`` uses.  The clear Grundstellung deciphers the
    message key, which fixes the body start position, so a daily key is just
    (wheel order, ring setting): 60 x 26^3 = 1,054,560 per date, which is
    exhaustively searchable.  The plugboard, however, sits inside the indicator
    machine as well as the body machine, so a wrong plugboard yields a wrong
    message key and therefore a body that is pure noise.  The score is a
    discontinuous function of the stecker and a hill-climb has nothing to
    follow.

``body_direct``
    The formulation Gillogly and Ostwald/Weierud use.  The body start position
    is searched instead of derived, so the plugboard's effect on the plaintext
    is smooth and local and the hill-climb works.  The indicator is then an
    independent confirmation rather than a search input.  The price is that the
    search space gains the start position.

Every number this module reports about the corpus is gated behind preflight
checks and preregistered known-key controls that must be recovered exactly; a
failed control makes zero target-search calls.

Method reference: Weierud and Sullivan, *Breaking German Army Ciphers*,
https://cryptocellar.org/pubs/mcts.pdf.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import platform
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Any

import enigma_fast
from provenance import code_version, sha256_file
from resources import resolve_output, resource_root
from stecker_calibration import run_calibration
from stecker_climb import indicator_coupled_climb
from stecker_controls import confirm_against_date, evaluate_positive_control, run_preflight
from stecker_scoring import FastNgramScorer
from stecker_sweeps import (
    body_direct_sweep,
    indicator_ic_sweep,
    resolve_axis,
    ring_space,
    rotor_order_space,
)
from stecker_traffic import INDICATOR_ORDERINGS, Traffic, traffic_from_corpus

ROOT = resource_root()
DEFAULT_CONFIG = ROOT / "experiments/phase1-stecker-calibration-v1/config.json"
CONFIG_SCHEMA = "enigma-attack.phase1-stecker-config/v1"
RESULT_SCHEMA = "enigma-attack.phase1-stecker-result/v1"


def resolve_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else ROOT / path


def resolve_config(value: str) -> pathlib.Path:
    """A relative ``--config`` is the caller's file if it exists, else a shipped one.

    In a checkout the two coincide when run from the repository root.  An
    installed command has its preregistered configurations under the share
    directory, and a caller's own configuration in the working directory.
    """

    path = pathlib.Path(value)
    return (path if path.is_file() else resolve_path(value)).resolve()


def describe_path(path: pathlib.Path) -> str:
    """Repo-relative when the path is inside the checkout, absolute otherwise.

    ``--config`` accepts any readable path, so a configuration outside the
    checkout is legitimate.  Recording it with ``relative_to`` would raise, and
    the record is assembled after the experiment, so the failure would land
    after a run that can take hours and leave no artifact at all.
    """

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def run_indicator_sweep(
    config: Mapping[str, Any],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    traffic: Sequence[Traffic],
) -> dict[str, Any]:
    rotor_orders = rotor_order_space(
        config["machine"]["rotor_orders"], config["machine"]["wheel_set"]
    )
    rings = ring_space(config["machine"]["ring_settings"])
    keep = int(config["sweep"]["keep"])
    climb_limit = int(config["sweep"]["climb_limit"])
    arms: list[dict[str, Any]] = []
    for ordering in config["indicator_orderings"]:
        started = time.monotonic()
        survivors, evaluated = indicator_ic_sweep(
            traffic, ordering, rotor_orders, rings, reflector, keep
        )
        sweep_seconds = time.monotonic() - started
        started = time.monotonic()
        climbed: list[dict[str, Any]] = []
        for candidate in survivors[:climb_limit]:
            outcome, plaintexts, keys = indicator_coupled_climb(
                traffic,
                ordering,
                candidate.rotor_order,
                candidate.rings,
                scorer,
                reflector,
                config["climb"],
            )
            climbed.append(
                {
                    "rotor_order_left_to_right": list(candidate.rotor_order),
                    "rings": candidate.rings_text(),
                    "index_of_coincidence": round(candidate.statistic, 9),
                    "score_per_letter": round(outcome.score_per_letter, 9),
                    "plugboard": enigma_fast.plugboard_pairs(outcome.plugboard),
                    "message_keys": keys,
                    "plaintext_prefixes": [text[:60] for text in plaintexts],
                }
            )
        climbed.sort(
            key=lambda row: (
                -row["score_per_letter"],
                row["rotor_order_left_to_right"],
                row["rings"],
            )
        )
        arms.append(
            {
                "indicator_ordering": ordering,
                "evaluated_daily_keys": evaluated,
                "sweep_seconds": round(sweep_seconds, 3),
                "climb_seconds": round(time.monotonic() - started, 3),
                "retained": len(survivors),
                "climbed": len(climbed),
                "top_index_of_coincidence": [
                    round(candidate.statistic, 9) for candidate in survivors[:10]
                ],
                "best_by_index_of_coincidence": {
                    "rotor_order_left_to_right": list(survivors[0].rotor_order),
                    "rings": survivors[0].rings_text(),
                    "index_of_coincidence": round(survivors[0].statistic, 9),
                    "message_keys": [
                        "".join(chr(65 + v) for v in key)
                        for key in survivors[0].message_keys
                    ],
                },
                "best_after_climb": climbed[0] if climbed else None,
            }
        )
    return {
        "formulation": "indicator_coupled",
        "space_is_complete": (
            len(rotor_orders) == 60
            and len(rings) == 17576
            and len(config["indicator_orderings"]) == 2
        ),
        "arms": arms,
        "evaluated_daily_keys": sum(arm["evaluated_daily_keys"] for arm in arms),
    }


def run_body_direct_sweep(
    config: Mapping[str, Any],
    scorer: FastNgramScorer,
    reflector: Sequence[int],
    traffic: Sequence[Traffic],
    jobs: int,
) -> dict[str, Any]:
    settings = config["body_direct_sweep"]
    by_designator = {message.designator: message for message in traffic}
    message = by_designator[settings["message"]]
    rotor_orders = rotor_order_space(
        config["machine"]["rotor_orders"], config["machine"]["wheel_set"]
    )
    rings = tuple(ord(letter) - 65 for letter in settings["rings"].upper())
    start_space = [
        (left, middle, right)
        for left in resolve_axis(settings["start_left"])
        for middle in resolve_axis(settings["start_middle"])
        for right in resolve_axis(settings["start_right"])
    ]
    started = time.monotonic()
    ranked, evaluated, distribution = body_direct_sweep(
        message,
        rotor_orders,
        rings,
        start_space,
        config["scorer"],
        reflector,
        config["climb"],
        int(settings["keep"]),
        jobs,
    )
    elapsed = time.monotonic() - started

    # Independent amplifier for the retained candidates.  The sweep climbs one
    # message; a candidate that is actually the daily key must also decipher the
    # other two messages of the date once its plugboard is fed back through the
    # clear indicator, which the sweep never used.  A wrong candidate gains
    # nothing from the extra letters, so the pooled score separates a real hit
    # from the best of the slice's noise far more sharply than the single-message
    # score can.
    #
    # The confirmation recovers the ring setting rather than reusing the held
    # one.  The sweep absorbs the left and middle rings into the start position
    # it searches, so the held value describes the parameterization and not the
    # daily key, and the indicator's fixed clear Grundstellung does not share
    # that freedom.  Deciphering the indicator under the held rings would test
    # the wrong key and could dismiss a genuine hit.
    for candidate in ranked:
        candidate["indicator_confirmation"] = confirm_against_date(
            traffic,
            candidate.pop("_plugboard"),
            candidate["rotor_order_left_to_right"],
            rings,
            scorer,
            reflector,
            config["indicator_orderings"],
            swept_message=message,
            swept_start=tuple(
                ord(letter) - 65 for letter in candidate["start_position"]
            ),
        )
    confirmation_scores = [
        candidate["indicator_confirmation"]["best_pooled_score_per_letter"]
        for candidate in ranked
    ]

    # Coverage is stated against the space that actually has to be searched,
    # not against the slice that was chosen, so the number cannot flatter the
    # run by redefining the denominator.
    relevant = 60 * 26**4
    return {
        "formulation": "body_direct",
        "message": message.designator,
        "message_length": len(message.body),
        "rings_held_at": settings["rings"].upper(),
        "rotor_orders": len(rotor_orders),
        "start_positions": len(start_space),
        "evaluated_settings": evaluated,
        "seconds": round(elapsed, 3),
        "seconds_per_setting": round(elapsed / max(evaluated, 1), 6),
        "jobs": jobs,
        "score_distribution_over_slice": distribution,
        "indicator_confirmation": {
            "best_pooled_score_per_letter": max(confirmation_scores),
            "mean_pooled_score_per_letter": round(
                statistics.fmean(confirmation_scores), 9
            ),
            "candidates_with_a_compatible_ring_setting": sum(
                1
                for candidate in ranked
                if candidate["indicator_confirmation"]["compatible_ring_settings"]
            ),
            "ring_recovery": (
                "The sweep absorbs the left and middle ring settings into the "
                "start position it searches, so the held AAA is the "
                "parameterization and not a claim about the daily key. The "
                "clear Grundstellung the indicator uses does not share that "
                "freedom, so for each candidate every left and middle ring "
                "setting that reproduces the swept body through the indicator "
                "is scored and the best is reported. The right-hand ring is "
                "fixed because it moves the turnover inside the message, which "
                "is what the declared slice holds."
            ),
            "method": (
                "For each retained candidate the recovered plugboard and a "
                "recovered ring setting are used with the clear indicator to "
                "derive all three message keys, and the whole date is scored. "
                "The sweep itself "
                "never reads the indicator, so this is an independent check."
            ),
        },
        "coverage": {
            "searched_settings": evaluated,
            "reducible_space_settings": relevant,
            "reducible_space_definition": (
                "60 wheel orders x 26^4, the parameters a message this short can "
                "distinguish: the left and middle wheel offsets, and the right "
                "wheel's offset and absolute position. It assumes the left wheel "
                "does not step during the message, which holds for about "
                "three quarters of start positions at this length."
            ),
            "fraction_searched": round(evaluated / relevant, 9),
            "measured_wall_seconds_per_setting_at_this_parallelism": round(
                elapsed / max(evaluated, 1), 6
            ),
            "jobs_used": jobs,
            "projected_wall_hours_for_reducible_space_at_this_parallelism": round(
                relevant * (elapsed / max(evaluated, 1)) / 3600, 1
            ),
            "projected_core_hours_for_reducible_space": round(
                # Wall-clock-per-setting already reflects ``jobs`` workers
                # sharing the run, so recovering true core-hours multiplies
                # back by the worker count rather than dividing by it. An
                # earlier version of this field named itself "core-hours"
                # while actually reporting wall-clock hours at this
                # parallelism, understating the true cost by the worker count.
                relevant * (elapsed / max(evaluated, 1)) * max(jobs, 1) / 3600,
                1,
            ),
        },
        "top_candidates": ranked,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_experiment(
    config: Mapping[str, Any],
    config_path: pathlib.Path,
    argv: Sequence[str],
    jobs: int,
) -> dict[str, Any]:
    started_at = dt.datetime.now(dt.timezone.utc)
    started_clock = time.monotonic()
    # Recorded before the run: a sweep can take hours, and the checkout state
    # worth recording is the one it started from, not whatever it was edited
    # into meanwhile.
    version = code_version()
    corpus_path = resolve_path(config["corpus"])
    scorer = FastNgramScorer(config["scorer"])
    reflector = enigma_fast.reflector_table(config["machine"]["reflector"])

    preflight = run_preflight(config, scorer)
    controls: list[dict[str, Any]] = []
    controls_passed = False
    if preflight["passed"]:
        for spec in config["positive_controls"]:
            controls.append(evaluate_positive_control(spec, config, scorer, reflector))
        controls_passed = bool(controls) and all(row["passed"] for row in controls)

    mode = config["mode"]
    body: dict[str, Any] | None = None
    if not preflight["passed"]:
        status = "blocked_by_preflight"
    elif not controls_passed:
        status = "blocked_by_positive_control"
    else:
        status = "complete"
        if mode == "calibration":
            body = run_calibration(config, scorer, reflector)
        else:
            traffic = traffic_from_corpus(
                corpus_path, config["target"]["date"], config["target"]["messages"]
            )
            if mode == "indicator_sweep":
                body = run_indicator_sweep(config, scorer, reflector, traffic)
            elif mode == "body_direct_sweep":
                body = run_body_direct_sweep(config, scorer, reflector, traffic, jobs)
            else:
                raise ValueError(f"unsupported mode: {mode!r}")

    return {
        "schema": RESULT_SCHEMA,
        "experiment_id": config["experiment_id"],
        "mode": mode,
        "status": status,
        "accepted_break": False,
        "hypothesis": config["hypothesis"],
        "refuted_by": config["refuted_by"],
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": time.monotonic() - started_clock,
        "configuration": {
            "path": describe_path(config_path),
            "sha256": sha256_file(config_path),
            "arguments": list(argv),
        },
        "code": version,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "inputs": {
            "corpus_sha256": sha256_file(corpus_path),
            "bigram_counts_sha256": sha256_file(
                resolve_path(config["scorer"]["bigram_counts"])
            ),
            "trigram_counts_sha256": sha256_file(
                resolve_path(config["scorer"]["trigram_counts"])
            ),
        },
        "preflight": preflight,
        "positive_controls": {
            "evaluated": controls,
            "passed": controls_passed,
            "gate": (
                "A failed control makes zero target-search calls, so a target "
                "number can never come from a pipeline that cannot recover a key "
                "it was handed."
            ),
        },
        "result": body,
        "limitations": config["limitations"],
    }


def load_config(path: pathlib.Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"unsupported configuration schema: {config.get('schema')!r}")
    if config["mode"] not in {"calibration", "indicator_sweep", "body_direct_sweep"}:
        raise ValueError(f"unsupported mode: {config['mode']!r}")
    for ordering in config.get("indicator_orderings", []):
        if ordering not in INDICATOR_ORDERINGS:
            raise ValueError(f"unknown indicator ordering: {ordering!r}")
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="worker processes for the body-direct sweep; results are merged in "
        "input order, so the artifact does not depend on this value",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config_path = resolve_config(arguments.config)
    config = load_config(config_path)
    result = run_experiment(
        config, config_path, sys.argv[1:] if argv is None else argv, max(1, arguments.jobs)
    )
    output = resolve_output(arguments.output or config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output} mode={result['mode']} status={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
