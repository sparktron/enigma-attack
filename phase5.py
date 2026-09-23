"""Phase 5 ciphertext-only model triage for alternative cipher families.

This module does not identify a cipher from a short ciphertext.  It measures a
small set of transparent structural signals, calibrates them against a uniform
random null with deterministic Monte Carlo trials, and routes each message to
the next family-specific experiment.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import pathlib
import random
from typing import Any, Mapping, Sequence

from phase1 import load_corpus


ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CORPUS = ROOT / "corpus.json"
DEFAULT_CATALOG = ROOT / "cipher-families.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "phase5-model-triage.json"
DEFAULT_UNIGRAM_SOURCE = ROOT / "data" / "phase7" / "BigramFrequency1941.txt"
DEFAULT_CONTROL_PLAINTEXTS = ROOT / "data" / "phase5" / "army-plaintext-controls.json"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
RANDOM_IC = 1.0 / len(ALPHABET)

# An absent letter is reported whenever the reference makes its total absence
# improbable.  This threshold only decides what is worth printing; the gate
# itself closes on null-calibrated p-values, never on a raw probability.
ABSENCE_REPORT_THRESHOLD = 0.05

# Dirichlet concentration for the per-message letter distribution in the null.
# Lower means more between-message variation and a more permissive gate.  This
# value was chosen so that every known true transposition in the calibration set
# clears alpha with roughly an order of magnitude to spare, which makes the gate
# deliberately reluctant to exclude.  The consequence is asymmetric and
# intended: an exclusion means something, a non-exclusion means very little.
UNIGRAM_NULL_CONCENTRATION = 200.0


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_text(text: str) -> str:
    text = text.upper()
    invalid = sorted(set(text) - set(ALPHABET) - {"?"})
    if invalid:
        raise ValueError(f"ciphertext contains invalid characters: {invalid}")
    return text


def index_of_coincidence(text: str) -> float:
    known = [character for character in _validated_text(text) if character != "?"]
    if len(known) < 2:
        return 0.0
    counts = collections.Counter(known)
    numerator = sum(count * (count - 1) for count in counts.values())
    return numerator / (len(known) * (len(known) - 1))


def uniform_chi_square(text: str) -> float:
    known = [character for character in _validated_text(text) if character != "?"]
    if not known:
        return 0.0
    expected = len(known) / len(ALPHABET)
    counts = collections.Counter(known)
    return sum(
        (counts[character] - expected) ** 2 / expected for character in ALPHABET
    )


def entropy_bits(text: str) -> float:
    known = [character for character in _validated_text(text) if character != "?"]
    if not known:
        return 0.0
    counts = collections.Counter(known)
    return -sum(
        (count / len(known)) * math.log2(count / len(known))
        for count in counts.values()
    )


def load_army_unigrams(
    path: pathlib.Path = DEFAULT_UNIGRAM_SOURCE,
) -> dict[str, Any]:
    """Derive 1941 Army plaintext unigram frequencies from published bigram counts.

    The published file is a bigram count table over raw German Army decrypts.
    Averaging the first-position and second-position marginals recovers the
    unigram distribution up to the first and last letter of each source message,
    which is negligible at this corpus size.  Deriving rather than shipping a
    second copy keeps one source of truth for the published counts.
    """
    first: collections.Counter[str] = collections.Counter()
    second: collections.Counter[str] = collections.Counter()
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        bigram, raw_count = fields
        if len(bigram) != 2 or not set(bigram) <= set(ALPHABET):
            continue
        count = int(raw_count)
        first[bigram[0]] += count
        second[bigram[1]] += count
        total += count
    if total <= 0:
        raise ValueError(f"{path}: no usable bigram counts")
    marginal = {letter: (first[letter] + second[letter]) / 2 for letter in ALPHABET}
    mass = sum(marginal.values())
    probabilities = {letter: marginal[letter] / mass for letter in ALPHABET}
    absent = sorted(letter for letter in ALPHABET if probabilities[letter] <= 0.0)
    if absent:
        raise ValueError(
            f"{path}: reference distribution has zero mass for {absent}; "
            "a conservation test cannot use a reference that excludes letters"
        )
    return {
        "source": str(path),
        "source_sha256": _sha256(path),
        "bigram_count_total": total,
        "derivation": (
            "mean of first-position and second-position marginals of the "
            "published 1941 Army bigram count table, renormalized over A-Z"
        ),
        "probabilities": probabilities,
    }


def load_conservation_controls(
    path: pathlib.Path = DEFAULT_CONTROL_PLAINTEXTS,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    plaintexts = payload.get("plaintexts")
    if not isinstance(plaintexts, list) or not plaintexts:
        raise ValueError(f"{path}: control file must contain a non-empty plaintexts list")
    for entry in plaintexts:
        text = str(entry["raw"])
        invalid = sorted(set(text) - set(ALPHABET))
        if invalid:
            raise ValueError(f"{path}: {entry['id']} contains {invalid}")
    return payload


def calibrate_conservation_gate(
    unigram_reference: Mapping[str, Any],
    controls: Mapping[str, Any],
    *,
    simulations: int,
    seed: int,
    alpha: float,
    concentration: float = UNIGRAM_NULL_CONCENTRATION,
) -> dict[str, Any]:
    """Require the gate to pass known true transpositions before it may exclude.

    Each control plaintext is shuffled, which is exactly a transposition and so
    preserves its letters.  A gate that calls any of these incompatible with
    Army plaintext monograms is measuring something other than conservation,
    and the caller must not act on its exclusions.
    """
    shuffle_seed = int(controls.get("shuffle_seed", seed))
    results: list[dict[str, Any]] = []
    for entry in controls["plaintexts"]:
        identifier = str(entry["id"])
        letters = list(str(entry["raw"]))
        random.Random(_trial_seed(shuffle_seed, identifier)).shuffle(letters)
        analysis = analyze_ciphertext(
            "".join(letters),
            simulations=simulations,
            seed=seed,
            label=f"control:{identifier}",
            alpha=alpha,
            unigram_reference=unigram_reference,
            concentration=concentration,
        )
        conservation = analysis["plaintext_conservation"]
        p_values = conservation["p_values"]
        results.append(
            {
                "id": identifier,
                "length": len(letters),
                "transformation": "uniform shuffle, a true transposition of the plaintext",
                "chi_square_per_letter": conservation["observed_chi_square_per_letter"],
                "p_values": dict(p_values),
                "minimum_p_value": min(float(value) for value in p_values.values()),
                "compatible": bool(
                    conservation["gate"]["plaintext_unigram_compatible"]
                ),
            }
        )
    failures = [item["id"] for item in results if not item["compatible"]]
    margin = min((float(item["minimum_p_value"]) for item in results), default=0.0)
    return {
        "source": controls.get("source"),
        "control_count": len(results),
        "alpha": alpha,
        "concentration": concentration,
        "controls": results,
        "failures": failures,
        "worst_control_p_value": margin,
        "margin_over_alpha": margin / alpha if alpha else 0.0,
        "calibrated": not failures,
        "effect_if_uncalibrated": (
            "Exclusions are recorded but not applied; every message keeps the "
            "route it would have had without the gate."
        ),
    }


def reference_chi_square(text: str, probabilities: Mapping[str, float]) -> float:
    """Chi-square distance of observed monograms from a reference distribution."""
    known = [character for character in _validated_text(text) if character != "?"]
    if not known:
        return 0.0
    counts = collections.Counter(known)
    statistic = 0.0
    for letter in ALPHABET:
        expected = probabilities[letter] * len(known)
        statistic += (counts[letter] - expected) ** 2 / expected
    return statistic


def absent_letter_report(
    text: str, probabilities: Mapping[str, float]
) -> dict[str, Any]:
    """Score letters that are wholly absent against a reference distribution.

    A transposition cannot create or destroy a letter, so a letter that the
    reference makes common but the ciphertext never uses is direct evidence
    against any frequency-preserving cipher over that reference plaintext.
    This argument needs no distributional approximation.
    """
    known = [character for character in _validated_text(text) if character != "?"]
    length = len(known)
    present = set(known)
    entries: list[dict[str, Any]] = []
    for letter in ALPHABET:
        if letter in present:
            continue
        probability = (1.0 - probabilities[letter]) ** length
        if probability <= ABSENCE_REPORT_THRESHOLD:
            entries.append(
                {
                    "letter": letter,
                    "reference_frequency": probabilities[letter],
                    "absence_probability": probability,
                }
            )
    entries.sort(key=lambda item: float(item["absence_probability"]))
    return {
        "length_known": length,
        "absent_letters": sorted(set(ALPHABET) - present),
        "improbable_absences": entries,
        "absence_surprisal": absence_surprisal(text, probabilities),
    }


def absence_surprisal(text: str, probabilities: Mapping[str, float]) -> float:
    """Total surprisal, in nats, of every letter the text never uses.

    The raw joint probability of the absences is not a usable statistic on its
    own: a short message is absent many letters for no reason beyond its
    length, so the product shrinks with length whether or not anything is
    anomalous.  Summing the surprisal gives a scalar that a length-matched null
    can calibrate, which is how the gate actually uses it.
    """
    known = [character for character in _validated_text(text) if character != "?"]
    present = set(known)
    return -sum(
        len(known) * math.log(1.0 - probabilities[letter])
        for letter in ALPHABET
        if letter not in present
    )


def _dirichlet_weights(
    probabilities: Mapping[str, float], concentration: float, rng: random.Random
) -> list[float]:
    """Draw one message's letter distribution around the reference.

    Real messages differ from the pooled corpus by more than sampling noise:
    each one has its own subject, place names and numerals.  Drawing the
    per-message distribution from a Dirichlet centred on the reference puts
    that between-message variation into the null, so the gate does not mistake
    an ordinary message's idiosyncrasy for a departure from plaintext.
    """
    draws = [
        rng.gammavariate(max(concentration * probabilities[letter], 1e-9), 1.0)
        for letter in ALPHABET
    ]
    mass = sum(draws)
    if mass <= 0.0:
        return [probabilities[letter] for letter in ALPHABET]
    return [draw / mass for draw in draws]


def _reference_trial(
    length: int,
    probabilities: Mapping[str, float],
    concentration: float,
    rng: random.Random,
) -> str:
    weights = _dirichlet_weights(probabilities, concentration, rng)
    return "".join(rng.choices(list(ALPHABET), weights=weights, k=length))


def repeated_ngram_pairs(text: str, width: int = 3) -> int:
    text = _validated_text(text)
    if width < 1:
        raise ValueError("ngram width must be positive")
    counts = collections.Counter(
        text[index : index + width]
        for index in range(len(text) - width + 1)
        if "?" not in text[index : index + width]
    )
    return sum(count * (count - 1) // 2 for count in counts.values())


def lag_profile(text: str, max_lag: int = 30) -> list[dict[str, float | int]]:
    text = _validated_text(text)
    profile: list[dict[str, float | int]] = []
    for lag in range(1, min(max_lag, len(text) - 1) + 1):
        pairs = [
            (left, right)
            for left, right in zip(text[:-lag], text[lag:])
            if left != "?" and right != "?"
        ]
        eligible = len(pairs)
        matches = sum(left == right for left, right in pairs)
        expected = eligible * RANDOM_IC
        variance = eligible * RANDOM_IC * (1.0 - RANDOM_IC)
        z_score = (matches - expected) / math.sqrt(variance) if variance else 0.0
        profile.append(
            {
                "lag": lag,
                "eligible_pairs": eligible,
                "matches": matches,
                "rate": matches / eligible if eligible else 0.0,
                "z_score": z_score,
            }
        )
    return profile


def periodic_ic_profile(
    text: str, max_period: int = 20
) -> list[dict[str, float | int]]:
    text = _validated_text(text)
    profile: list[dict[str, float | int]] = []
    for period in range(2, min(max_period, len(text) // 2) + 1):
        numerator = 0
        denominator = 0
        for residue in range(period):
            column = [
                text[index]
                for index in range(residue, len(text), period)
                if text[index] != "?"
            ]
            counts = collections.Counter(column)
            numerator += sum(count * (count - 1) for count in counts.values())
            denominator += len(column) * (len(column) - 1)
        value = numerator / denominator if denominator else 0.0
        profile.append(
            {
                "period": period,
                "pooled_within_column_ic": value,
                "lift_over_global_ic": value - index_of_coincidence(text),
            }
        )
    return profile


def _feature_vector(text: str, max_period: int, max_lag: int) -> dict[str, Any]:
    lags = lag_profile(text, max_lag=max_lag)
    periods = periodic_ic_profile(text, max_period=max_period)
    best_lag = max(lags, key=lambda item: float(item["z_score"]), default=None)
    best_period = max(
        periods,
        key=lambda item: float(item["pooled_within_column_ic"]),
        default=None,
    )
    return {
        "index_of_coincidence": index_of_coincidence(text),
        "uniform_chi_square": uniform_chi_square(text),
        "entropy_bits": entropy_bits(text),
        "trigram_repeat_pairs": repeated_ngram_pairs(text, 3),
        "best_lag": best_lag,
        "best_period": best_period,
    }


def _trial_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _uniform_trial(template: str, rng: random.Random) -> str:
    return "".join(
        "?" if character == "?" else rng.choice(ALPHABET) for character in template
    )


def _permutation_trial(template: str, rng: random.Random) -> str:
    """Shuffle known letters while leaving unknown source positions fixed."""
    known = [character for character in template if character != "?"]
    rng.shuffle(known)
    iterator = iter(known)
    return "".join(
        "?" if character == "?" else next(iterator) for character in template
    )


def _upper_tail(observed: float, null_values: Sequence[float]) -> float:
    exceedances = sum(value >= observed for value in null_values)
    return (exceedances + 1) / (len(null_values) + 1)


def analyze_ciphertext(
    text: str,
    *,
    simulations: int = 4000,
    seed: int = 20260921,
    label: str = "message",
    max_period: int = 20,
    max_lag: int = 30,
    alpha: float = 0.01,
    unigram_reference: Mapping[str, Any] | None = None,
    concentration: float = UNIGRAM_NULL_CONCENTRATION,
) -> dict[str, Any]:
    if simulations < 1:
        raise ValueError("simulations must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")
    if unigram_reference is None:
        unigram_reference = load_army_unigrams()
    text = _validated_text(text)
    observed = _feature_vector(text, max_period=max_period, max_lag=max_lag)
    uniform_seed = _trial_seed(seed, f"{label}:uniform")
    permutation_seed = _trial_seed(seed, f"{label}:permutation")
    reference_seed = _trial_seed(seed, f"{label}:reference")
    uniform_rng = random.Random(uniform_seed)
    permutation_rng = random.Random(permutation_seed)
    reference_rng = random.Random(reference_seed)
    uniform_trials = [_uniform_trial(text, uniform_rng) for _ in range(simulations)]
    permutation_vectors = [
        _feature_vector(
            _permutation_trial(text, permutation_rng),
            max_period=max_period,
            max_lag=max_lag,
        )
        for _ in range(simulations)
    ]

    observed_lag_z = (
        float(observed["best_lag"]["z_score"]) if observed["best_lag"] else 0.0
    )
    observed_period_ic = (
        float(observed["best_period"]["pooled_within_column_ic"])
        if observed["best_period"]
        else 0.0
    )
    uniform_p_values = {
        "ic_upper": _upper_tail(
            float(observed["index_of_coincidence"]),
            [index_of_coincidence(trial) for trial in uniform_trials],
        ),
        "chi_square_upper": _upper_tail(
            float(observed["uniform_chi_square"]),
            [uniform_chi_square(trial) for trial in uniform_trials],
        ),
    }
    conditional_p_values = {
        "trigram_repeats_upper": _upper_tail(
            float(observed["trigram_repeat_pairs"]),
            [
                float(vector["trigram_repeat_pairs"])
                for vector in permutation_vectors
            ],
        ),
        "max_lag_upper": _upper_tail(
            observed_lag_z,
            [
                float(vector["best_lag"]["z_score"])
                if vector["best_lag"]
                else 0.0
                for vector in permutation_vectors
            ],
        ),
        "max_periodic_ic_upper": _upper_tail(
            observed_period_ic,
            [
                float(vector["best_period"]["pooled_within_column_ic"])
                if vector["best_period"]
                else 0.0
                for vector in permutation_vectors
            ],
        ),
    }
    probabilities = unigram_reference["probabilities"]
    known_length = sum(character != "?" for character in text)
    observed_reference_chi_square = reference_chi_square(text, probabilities)
    observed_absence_surprisal = absence_surprisal(text, probabilities)
    null_chi_square: list[float] = []
    null_absence: list[float] = []
    for _ in range(simulations):
        trial = _reference_trial(
            known_length, probabilities, concentration, reference_rng
        )
        null_chi_square.append(reference_chi_square(trial, probabilities))
        null_absence.append(absence_surprisal(trial, probabilities))
    absences = absent_letter_report(text, probabilities)
    conservation_p_values = {
        "reference_chi_square_upper": _upper_tail(
            observed_reference_chi_square, null_chi_square
        ),
        "absence_surprisal_upper": _upper_tail(
            observed_absence_surprisal, null_absence
        ),
    }
    # Both tests interrogate the same invariant: a transposition permutes the
    # plaintext letters and cannot change how many of each there are.  They fail
    # in different ways, so either one closing the gate is enough -- the fit test
    # catches a wrong shape, the absence test catches a missing letter that no
    # amount of reordering could have removed.
    unigram_fit_compatible = conservation_p_values["reference_chi_square_upper"] > alpha
    absence_compatible = conservation_p_values["absence_surprisal_upper"] > alpha
    plaintext_unigram_compatible = unigram_fit_compatible and absence_compatible

    best_period = observed["best_period"]
    periodic_lift = (
        float(best_period["lift_over_global_ic"]) if best_period else 0.0
    )
    ic_elevated = (
        observed["index_of_coincidence"] > RANDOM_IC
        and uniform_p_values["ic_upper"] <= alpha
    )
    signals = {
        "ic_elevated": ic_elevated,
        "plaintext_unigram_compatible": plaintext_unigram_compatible,
        # Conservation gate: elevated IC says the ciphertext is not flat.  It
        # does not say the concentrated letters are plaintext letters.  A
        # frequency-preserving cipher requires both.
        "frequency_preserving": ic_elevated and plaintext_unigram_compatible,
        "periodic_structure": (
            conditional_p_values["max_periodic_ic_upper"] <= alpha
            and periodic_lift >= 0.006
        ),
        "repeated_blocks": (
            observed["trigram_repeat_pairs"] > 0
            and conditional_p_values["trigram_repeats_upper"] <= alpha
        ),
        "lag_structure": conditional_p_values["max_lag_upper"] <= alpha,
    }
    # A flat Enigma-like ciphertext is legitimately incompatible with plaintext
    # unigrams, so `plaintext_unigram_compatible` must not count against
    # uniform-random compatibility.  `ic_elevated` must, and on its own: when
    # the gate closes, `frequency_preserving` goes false while the departure
    # from uniform that raised it stays real and still needs a home.
    structural_signals = (
        "ic_elevated",
        "frequency_preserving",
        "periodic_structure",
        "repeated_blocks",
        "lag_structure",
    )
    signals["uniform_random_compatible"] = not any(
        signals[name] for name in structural_signals
    )
    return {
        "length_total": len(text),
        "length_known": sum(character != "?" for character in text),
        "unknown_positions": [
            index for index, character in enumerate(text) if character == "?"
        ],
        "statistics": observed,
        "uniform_null": {
            "alphabet_size": len(ALPHABET),
            "expected_ic": RANDOM_IC,
            "simulations": simulations,
            "seed": uniform_seed,
            "tests": ["index_of_coincidence", "uniform_chi_square"],
            "p_values": uniform_p_values,
        },
        "conditional_permutation_null": {
            "condition": "exact observed known-letter multiset",
            "unknown_positions_preserved": True,
            "simulations": simulations,
            "seed": permutation_seed,
            "multiple_scan_note": (
                "Lag and period p-values compare the observed maximum with each "
                "trial maximum, accounting for the configured scan range."
            ),
            "tests": [
                "trigram_repeat_pairs",
                "maximum_lag_coincidence_z_score",
                "maximum_pooled_within_column_ic",
            ],
            "p_values": conditional_p_values,
        },
        "plaintext_conservation": {
            "invariant": (
                "A transposition permutes plaintext letters and cannot change "
                "the multiset of letters, so a frequency-preserving cipher over "
                "German Army plaintext must show Army plaintext monograms."
            ),
            "reference": {
                key: value
                for key, value in unigram_reference.items()
                if key != "probabilities"
            },
            "reference_probabilities": probabilities,
            "observed_chi_square": observed_reference_chi_square,
            "observed_chi_square_per_letter": (
                observed_reference_chi_square / known_length if known_length else 0.0
            ),
            "observed_absence_surprisal": observed_absence_surprisal,
            "null": {
                "condition": (
                    "per-message letter distribution drawn from a Dirichlet "
                    "centred on the reference, then letters drawn from it"
                ),
                "concentration": concentration,
                "simulations": simulations,
                "seed": reference_seed,
            },
            "p_values": conservation_p_values,
            "absences": absences,
            "gate": {
                "unigram_fit_compatible": unigram_fit_compatible,
                "absence_compatible": absence_compatible,
                "plaintext_unigram_compatible": plaintext_unigram_compatible,
                "effect": (
                    "When this gate is closed, frequency-preserving families are "
                    "excluded by conservation and no transposition search is "
                    "justified for this message against this reference."
                ),
            },
            "limits": [
                "The gate excludes a transposition of German Army plaintext, not "
                "a transposition of an already-substituted or encoded layer.",
                "The null draws letters independently within a message; real "
                "plaintext is autocorrelated, so the null understates clustering.",
                "The Dirichlet concentration was chosen so known true "
                "transpositions pass with margin, which biases the gate toward "
                "not excluding. Non-exclusion is therefore weak evidence.",
                "The reference is derived from published counts whose source "
                "messages are not enumerated.",
            ],
        },
        "alpha": alpha,
        "signals": signals,
    }


def load_family_catalog(path: pathlib.Path = DEFAULT_CATALOG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    families = payload.get("families")
    sources = payload.get("sources")
    if not isinstance(families, list) or not families:
        raise ValueError("family catalog must contain a non-empty families list")
    if not isinstance(sources, list) or not sources:
        raise ValueError("family catalog must contain a non-empty sources list")
    source_ids = {source["id"] for source in sources}
    family_ids: set[str] = set()
    valid_signatures = {"frequency_preserving", "periodic", "repeated_blocks", "randomizing"}
    for family in families:
        family_id = family["id"]
        if family_id in family_ids:
            raise ValueError(f"duplicate family id: {family_id}")
        family_ids.add(family_id)
        if family["screening_signature"] not in valid_signatures:
            raise ValueError(f"{family_id}: invalid screening signature")
        missing = sorted(set(family["source_ids"]) - source_ids)
        if missing:
            raise ValueError(f"{family_id}: unknown source ids {missing}")
    return payload


def assess_families(
    analysis: Mapping[str, Any], catalog: Mapping[str, Any]
) -> list[dict[str, Any]]:
    signals = analysis["signals"]
    assessments: list[dict[str, Any]] = []
    for family in catalog["families"]:
        signature = family["screening_signature"]
        if signature == "frequency_preserving":
            if signals[signature]:
                status = "supported_for_follow_up"
            elif not signals["plaintext_unigram_compatible"]:
                status = "excluded_by_conservation"
            else:
                status = "not_supported"
        elif signature == "periodic":
            status = "supported_for_follow_up" if signals["periodic_structure"] else "not_supported"
        elif signature == "repeated_blocks":
            status = "supported_for_follow_up" if signals["repeated_blocks"] else "inconclusive"
        else:
            status = (
                "ciphertext_only_compatible"
                if signals["uniform_random_compatible"]
                else "structural_tension"
            )
        assessments.append(
            {
                "family_id": family["id"],
                "label": family["label"],
                "screening_signature": signature,
                "status": status,
                "historical_prior": family["historical_prior"],
                "source_ids": family["source_ids"],
                "limits": family["limits"],
            }
        )
    status_rank = {
        "supported_for_follow_up": 0,
        "ciphertext_only_compatible": 1,
        "inconclusive": 2,
        "structural_tension": 3,
        "not_supported": 4,
        # An exclusion is the strongest statement this phase can make, so it
        # sorts last: it is the one family that needs no further work.
        "excluded_by_conservation": 5,
    }
    return sorted(assessments, key=lambda item: (status_rank[item["status"]], item["family_id"]))


def apply_conservation_gate(analysis: dict[str, Any], active: bool) -> dict[str, Any]:
    """Enable or suspend the gate's effect on an already-computed analysis.

    The conservation measurements are always recorded.  Only their effect on
    routing is conditional, so a suspended gate leaves a complete, auditable
    record of what it would have concluded had it been calibrated.
    """
    signals = analysis["signals"]
    analysis["plaintext_conservation"]["gate"]["applied"] = active
    if active:
        return analysis
    signals["plaintext_unigram_compatible"] = True
    signals["frequency_preserving"] = signals["ic_elevated"]
    signals["uniform_random_compatible"] = not any(
        signals[name]
        for name in (
            "ic_elevated",
            "frequency_preserving",
            "periodic_structure",
            "repeated_blocks",
            "lag_structure",
        )
    )
    return analysis


def route_message(signals: Mapping[str, bool]) -> str:
    if signals["frequency_preserving"]:
        return "frequency_preserving_manual"
    if signals["ic_elevated"] and not signals["plaintext_unigram_compatible"]:
        # Concentrated, but not on plaintext letters.  Something maps plaintext
        # symbols to a different alphabet before or instead of any reordering,
        # which rules the frequency-preserving branch out rather than in.
        return "non_plaintext_alphabet_substitution"
    if signals["periodic_structure"]:
        return "periodic_polyalphabetic"
    if signals["repeated_blocks"] or signals["lag_structure"]:
        return "code_superencipherment_or_retransmission"
    return "randomizing_machine_or_combiner"


def _cohort_monogram(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    text = "".join(str(record["ciphertext"]) for record in records)
    return {
        "message_count": len(records),
        "known_letters": sum(character != "?" for character in text),
        "index_of_coincidence": index_of_coincidence(text),
        "uniform_chi_square": uniform_chi_square(text),
        "entropy_bits": entropy_bits(text),
        "scope_note": "Only pooled monographic statistics are valid across independently keyed messages.",
    }


def build_artifact(args: argparse.Namespace) -> dict[str, Any]:
    catalog = load_family_catalog(args.catalog)
    unigram_reference = load_army_unigrams(args.unigram_source)
    controls = load_conservation_controls(args.control_plaintexts)
    calibration = calibrate_conservation_gate(
        unigram_reference,
        controls,
        simulations=args.simulations,
        seed=args.seed,
        alpha=args.alpha,
        concentration=args.concentration,
    )
    gate_active = bool(calibration["calibrated"])
    validated = {message.designator: message for message in load_corpus(args.corpus)}
    corpus_payload = json.loads(args.corpus.read_text(encoding="utf-8"))
    records = corpus_payload["messages"]
    analyses: list[dict[str, Any]] = []
    for record in records:
        designator = record["designator"]
        message = validated[designator]
        analysis = analyze_ciphertext(
            message.ciphertext,
            simulations=args.simulations,
            seed=args.seed,
            label=designator,
            max_period=args.max_period,
            max_lag=args.max_lag,
            alpha=args.alpha,
            unigram_reference=unigram_reference,
            concentration=args.concentration,
        )
        analysis = apply_conservation_gate(analysis, gate_active)
        route = route_message(analysis["signals"])
        analyses.append(
            {
                "designator": designator,
                "date": record["date"],
                "current_status": record.get("current_status", "unknown"),
                "analysis": analysis,
                "route": route,
                "family_assessments": assess_families(analysis, catalog),
            }
        )

    routes = collections.Counter(item["route"] for item in analyses)
    current_unbroken = [
        record
        for record in records
        if str(record.get("current_status", "")).startswith("unbroken_as_of_")
    ]
    route_priority = {
        "frequency_preserving_manual": 0,
        "non_plaintext_alphabet_substitution": 1,
        "periodic_polyalphabetic": 2,
        "code_superencipherment_or_retransmission": 3,
        "randomizing_machine_or_combiner": 4,
    }
    priority = sorted(
        analyses,
        key=lambda item: (route_priority[item["route"]], item["designator"]),
    )
    # Two different facts, routinely confused.  A flat Enigma-like ciphertext is
    # also incompatible with plaintext monograms, so the family exclusion is
    # broad and mostly unsurprising.  What matters for planning is the narrower
    # set: messages the old IC-only rule would have sent to a transposition
    # search and the gate now diverts.
    family_excluded = sorted(
        item["designator"]
        for item in analyses
        if not item["analysis"]["signals"]["plaintext_unigram_compatible"]
    )
    routing_changed = sorted(
        item["designator"]
        for item in analyses
        if not item["analysis"]["signals"]["plaintext_unigram_compatible"]
        and item["analysis"]["signals"]["ic_elevated"]
    )
    return {
        "schema": "enigma-attack.phase5-model-triage/v3",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": {
            "corpus": str(args.corpus),
            "corpus_sha256": _sha256(args.corpus),
            "catalog": str(args.catalog),
            "catalog_sha256": _sha256(args.catalog),
            "unigram_reference": str(args.unigram_source),
            "unigram_reference_sha256": _sha256(args.unigram_source),
            "control_plaintexts": str(args.control_plaintexts),
            "control_plaintexts_sha256": _sha256(args.control_plaintexts),
            "runner_sha256": _sha256(pathlib.Path(__file__)),
        },
        "conservation_gate_calibration": calibration,
        "research_boundary": {
            "question": catalog["question"],
            "research_date": catalog["research_date"],
            "sources": catalog["sources"],
            "fact": (
                "The catalog records documented cipher families and cryptanalytic "
                "properties from its cited sources."
            ),
            "inference": (
                "Per-message structural signals can route follow-up experiments but "
                "cannot identify a named cipher system."
            ),
            "speculation": (
                "Any mapping from one Batch C message to a non-Enigma family remains "
                "speculative until a key, plaintext, or archival procedure is found."
            ),
        },
        "method": {
            "nulls": {
                "monographic": (
                    "independent uniform A-Z symbols with source unknown positions preserved"
                ),
                "structural": (
                    "frequency-preserving permutations of each observed ciphertext "
                    "with source unknown positions preserved"
                ),
                "conservation": (
                    "independent draws from 1941 Army plaintext unigram "
                    "frequencies at the observed known length"
                ),
            },
            "simulations_per_message": args.simulations,
            "base_seed": args.seed,
            "alpha": args.alpha,
            "max_period": args.max_period,
            "max_lag": args.max_lag,
            "tests": [
                "index of coincidence",
                "chi-square distance from uniform monograms",
                "repeated trigram pair count",
                "maximum lag coincidence z-score",
                "maximum pooled within-column IC over candidate periods",
                "chi-square distance from 1941 Army plaintext monograms",
                "joint improbability of wholly absent reference-common letters",
            ],
            "conservation_gate": {
                "rationale": (
                    "Elevated IC measures concentration, not which letters are "
                    "concentrated. Routing to a frequency-preserving family on IC "
                    "alone sent Phases 6 and 7 at a hypothesis that letter "
                    "conservation already excluded."
                ),
                "rule": (
                    "frequency_preserving requires ic_elevated and "
                    "plaintext_unigram_compatible. The second fails when either "
                    "the reference chi-square or the absence-surprisal "
                    "upper-tail p-value is at or below alpha."
                ),
                "status_when_closed": "excluded_by_conservation",
                "calibrated": gate_active,
                "positive_control_requirement": (
                    "Every known Army plaintext in the control set, shuffled into "
                    "a true transposition, must be found compatible. Otherwise "
                    "the gate is recorded but not applied."
                ),
            },
            "warning": (
                "Statuses other than excluded_by_conservation are diagnostic "
                "routing labels, not posterior probabilities. An exclusion is a "
                "claim about the reference plaintext only: it rules out a "
                "frequency-preserving cipher over German Army plaintext, not one "
                "applied to an already-substituted or encoded layer."
            ),
        },
        "cohorts": {
            "all_messages": _cohort_monogram(records),
            "currently_listed_unbroken": _cohort_monogram(current_unbroken),
        },
        "messages": analyses,
        "model_selection": {
            "route_counts": dict(sorted(routes.items())),
            "heterogeneous_routes": len(routes) > 1,
            "priority_order": [item["designator"] for item in priority],
        },
        "decision": {
            "accepted_break": False,
            "status": "phase5_structural_triage_complete",
            "next_experiment": (
                f"Run a family-specific, held-out-validated experiment for {priority[0]['designator']} "
                f"on route {priority[0]['route']}."
            ),
            "conservation_exclusions": {
                "gate_applied": gate_active,
                "frequency_preserving_family_excluded": family_excluded,
                "routing_changed_by_gate": routing_changed,
                "note": (
                    "A flat ciphertext is incompatible with plaintext monograms "
                    "too, so the family exclusion covers Enigma-like messages "
                    "that were never routed to a transposition search. Only "
                    "routing_changed_by_gate reflects work the gate prevents."
                ),
            },
            "negative_claim": (
                "Frequency-preserving ciphers over German Army plaintext are "
                f"excluded by letter conservation for {family_excluded}; of "
                f"those, {routing_changed} had the elevated index of coincidence "
                "that would otherwise have justified a transposition search. "
                "No other family is excluded; short ciphertexts and diagnostic "
                "null tests do not exclude the rest."
            )
            if family_excluded
            else "None; short ciphertexts and diagnostic null tests do not exclude any family.",
            "unresolved": [
                "QTXMA is concentrated but not on plaintext letters, and this phase does not identify what maps plaintext onto its 22-letter alphabet.",
                "Original five-letter grouping and typography may contain model-selection evidence absent from normalized ciphertext.",
                "QTXMA and SZAEJ are absent from the current three-message unbroken list, but their disposition is not documented in the corpus sources.",
                "Random-like ciphertext cannot distinguish Enigma, cipher teleprinter, and strong superencipherment without traffic metadata or cribs.",
            ],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=pathlib.Path, default=DEFAULT_CORPUS)
    parser.add_argument("--catalog", type=pathlib.Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--unigram-source",
        type=pathlib.Path,
        default=DEFAULT_UNIGRAM_SOURCE,
        help="published bigram count table the plaintext unigram reference is derived from",
    )
    parser.add_argument(
        "--control-plaintexts",
        type=pathlib.Path,
        default=DEFAULT_CONTROL_PLAINTEXTS,
        help="known Army plaintexts used as conservation-gate positive controls",
    )
    parser.add_argument(
        "--concentration",
        type=float,
        default=UNIGRAM_NULL_CONCENTRATION,
        help="Dirichlet concentration for between-message variation in the conservation null",
    )
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--simulations", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--max-period", type=int, default=20)
    parser.add_argument("--max-lag", type=int, default=30)
    parser.add_argument("--alpha", type=float, default=0.01)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_period < 2:
        raise SystemExit("--max-period must be at least 2")
    if args.max_lag < 1:
        raise SystemExit("--max-lag must be positive")
    artifact = build_artifact(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} "
        f"({len(artifact['messages'])} messages, {args.simulations} null trials each)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
