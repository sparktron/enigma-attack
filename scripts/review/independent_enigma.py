#!/usr/bin/env python3
"""Independent re-derivation of the simulator and of the sweep-space coverage claim.

Exploratory measurement from docs/code-review-2026-10-11.md (R-1, R-2).  It is
not a preregistered experiment and writes no artifact under ``artifacts/``.

The Enigma below was written from the published description of the machine and
shares no code with ``enigma.py`` or ``enigma_fast.py``.  Part 1 compares it with
``enigma.EnigmaMachine``, ``enigma_fast.crypt_indices`` and the table path
(``position_permutations`` plus ``decrypt_with_tables``) on two published
vectors, the double-stepping sequence, and random keys of up to 700 letters,
which cross wheel notches and double-step.  Part 2 checks the claim in
``stecker_space.rule_key_coverage``: two settings decipher identically under
every plugboard exactly when their per-letter wheel-offset trajectories match,
so for random true keys it builds the settings ``RingRule`` generates for the
key's reachable start and counts how often one of them matches.

Review results (seed 20261011 for part 1, seed 7 for part 2):
    part 1: 3000/3000 random keys agree across all four implementations
    part 2, 600 keys each:   past-notch  97: 0.818  107: 0.798  167: 0.722
                             complete    97: 1.000  107: 1.000  167: 1.000
            (rule_key_coverage claims 0.820 / 0.805 / 0.716 and 1.0 throughout;
             the differences are sampling error at 600 keys, about +/-0.02)
"""

from __future__ import annotations

import argparse
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import enigma  # noqa: E402
import enigma_fast as ef  # noqa: E402
import stecker_space as ss  # noqa: E402

ABC = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
WHEELS = {
    "I": ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II": ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV": ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V": ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
}
UKW_B = "YRUHQSLDPXNGOKMIEBFZCWVJAT"


def through_wheel(letter: str, wiring: str, position: int, ring: int, inverse: bool) -> str:
    shift = (position - ring) % 26
    if not inverse:
        return ABC[(ABC.index(wiring[(ABC.index(letter) + shift) % 26]) - shift) % 26]
    contact = ABC[(ABC.index(letter) + shift) % 26]
    return ABC[(wiring.index(contact) - shift) % 26]


def independent_crypt(order, rings: str, start: str, plugboard: str, text: str) -> str:
    positions = [ABC.index(x) for x in start]
    ring_values = [ABC.index(x) for x in rings]
    plugs: dict[str, str] = {}
    for pair in plugboard.split():
        plugs[pair[0]], plugs[pair[1]] = pair[1], pair[0]
    out = []
    for letter in text:
        middle_on_notch = ABC[positions[1]] in WHEELS[order[1]][1]
        right_on_notch = ABC[positions[2]] in WHEELS[order[2]][1]
        if middle_on_notch:
            positions[0] = (positions[0] + 1) % 26
        if middle_on_notch or right_on_notch:
            positions[1] = (positions[1] + 1) % 26
        positions[2] = (positions[2] + 1) % 26
        x = plugs.get(letter, letter)
        for i in (2, 1, 0):
            x = through_wheel(x, WHEELS[order[i]][0], positions[i], ring_values[i], False)
        x = UKW_B[ABC.index(x)]
        for i in (0, 1, 2):
            x = through_wheel(x, WHEELS[order[i]][0], positions[i], ring_values[i], True)
        out.append(plugs.get(x, x))
    return "".join(out)


def offsets(order, rings, positions, length):
    """Offset (position - ring) of each wheel at each of ``length`` keystrokes."""

    p = list(positions)
    middle_notches = {ord(c) - 65 for c in WHEELS[order[1]][1]}
    right_notches = {ord(c) - 65 for c in WHEELS[order[2]][1]}
    trajectory = []
    for _ in range(length):
        middle_on = p[1] in middle_notches
        right_on = p[2] in right_notches
        if middle_on:
            p[0] = (p[0] + 1) % 26
        if middle_on or right_on:
            p[1] = (p[1] + 1) % 26
        p[2] = (p[2] + 1) % 26
        trajectory.append(tuple((p[i] - rings[i]) % 26 for i in range(3)))
    return trajectory


def part_one(trials: int, seed: int) -> bool:
    ok = True
    for order, rings, start, plug, plain, expected in (
        (("I", "II", "III"), "AAA", "AAA", "", "AAAAA", "BDZGO"),
        (("I", "II", "III"), "BBB", "AAA", "", "AAAAA", "EWTYX"),
    ):
        mine = independent_crypt(order, rings, start, plug, plain)
        repo = enigma.EnigmaMachine(order, rings, start, plug).crypt(plain)
        good = mine == repo == expected
        ok &= good
        print(f"vector {plain}->{expected}: independent {mine}, repo {repo}: {'ok' if good else 'MISMATCH'}")
    machine = enigma.EnigmaMachine(("III", "II", "I"), "AAA", "KDO")
    seen = []
    for _ in range(4):
        machine.step()
        seen.append(machine.positions)
    good = seen == ["KDP", "KDQ", "KER", "LFS"]
    ok &= good
    print(f"double step from KDO (rotors III II I): {seen}: {'ok' if good else 'MISMATCH'}")

    rng = random.Random(seed)
    names = list(WHEELS)
    bad = 0
    for _ in range(trials):
        order = tuple(rng.sample(names, 3))
        rings = "".join(rng.choice(ABC) for _ in range(3))
        start = "".join(rng.choice(ABC) for _ in range(3))
        letters = rng.sample(ABC, 2 * rng.randint(0, 13))
        plug = " ".join(letters[i] + letters[i + 1] for i in range(0, len(letters), 2))
        length = rng.randint(1, 700)
        plain = "".join(rng.choice(ABC) for _ in range(length))
        a = independent_crypt(order, rings, start, plug, plain)
        b = enigma.EnigmaMachine(order, rings, start, plug).crypt(plain)
        tables = [ef.rotor_tables(x) for x in order]
        ring_ix = [ABC.index(x) for x in rings]
        start_ix = [ABC.index(x) for x in start]
        c = ef.indices_to_text(
            ef.crypt_indices(tables, ring_ix, start_ix, ef.text_to_indices(plain), ef.plugboard_table(plug))
        )
        table = ef.position_permutations(tables, ring_ix, start_ix, length)
        d = ef.indices_to_text(
            ef.decrypt_with_tables(table, ef.text_to_indices(plain), ef.plugboard_table(plug))
        )
        bad += not (a == b == c == d)
    print(f"random keys: {trials - bad}/{trials} agree across independent / enigma.py / crypt_indices / tables")
    return ok and bad == 0


def part_two(trials: int, seed: int) -> None:
    rng = random.Random(seed)
    names = list(WHEELS)
    for rule_name in ("middle_past_notch", "middle_complete"):
        for length in (97, 107, 167):
            covered = 0
            for _ in range(trials):
                order = tuple(rng.sample(names, 3))
                rings = tuple(rng.randrange(26) for _ in range(3))
                positions = tuple(rng.randrange(26) for _ in range(3))
                truth = offsets(order, rings, positions, length)
                reach = tuple((positions[i] - rings[i]) % 26 for i in range(3))
                rule = ss.RingRule(rule_name, (0, 0, 0), tuple(range(26)), length)
                swept = rule.settings(order, [(reach[0], reach[1], positions[2])])
                covered += any(offsets(order, r, p, length) == truth for r, p in swept)
            claimed = ss.rule_key_coverage(rule_name, length, tuple(names))
            print(
                f"{rule_name:18s} {length:3d} letters: empirical {covered / trials:.3f} "
                f"({trials} keys), rule_key_coverage {claimed:.3f}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--trials", type=int, default=3000, help="random keys for part 1")
    parser.add_argument("--coverage-trials", type=int, default=600, help="keys per row for part 2")
    arguments = parser.parse_args()
    ok = part_one(arguments.trials, 20261011)
    part_two(arguments.coverage_trials, 7)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
