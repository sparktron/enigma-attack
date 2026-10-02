#!/usr/bin/env python3
"""Table-driven Enigma kernel for large standard-Enigma sweeps.

``enigma.py`` stays the readable reference machine and the thing every other
phase is checked against.  It is also far too slow for Phase 1: a full
standard-Enigma daily-key sweep is roughly 10^6 keys per date, and the
reference machine revalidates three rotor wirings, a reflector and a plugboard
on every construction.

This module trades transparency for speed in exactly two ways, and nothing
else:

* every rotor is precomputed as 26 forward and 26 reverse permutations, one per
  ``(position - ring)`` offset, so a letter costs table lookups instead of
  modular arithmetic;
* the plugboard is lifted out of the rotor path.  At a fixed rotor state the
  unsteckered machine is one involution ``E`` and the steckered machine is
  ``P . E . P``, so a stecker hill-climb can reuse precomputed per-position
  permutations and never re-run the stepping.

Both are exact algebraic rewrites, not approximations.  :func:`parity_report`
checks this kernel against ``enigma.py`` on pseudorandom settings and is called
by the experiment runner before any search, so a divergence stops the run
rather than quietly producing a faster wrong answer.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterable, Sequence

from enigma import A, EnigmaI, REFLECTOR_WIRINGS, ROTOR_WIRINGS

IDENTITY_PLUGBOARD = tuple(range(26))


def _offset_tables(wiring: str) -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
    """Return ``(forward, reverse)`` tables indexed by ``(position - ring)``."""

    forward_base = [ord(letter) - 65 for letter in wiring]
    reverse_base = [0] * 26
    for source, target in enumerate(forward_base):
        reverse_base[target] = source
    forward: list[tuple[int, ...]] = []
    reverse: list[tuple[int, ...]] = []
    for offset in range(26):
        forward.append(
            tuple(
                (forward_base[(index + offset) % 26] - offset) % 26 for index in range(26)
            )
        )
        reverse.append(
            tuple(
                (reverse_base[(index + offset) % 26] - offset) % 26 for index in range(26)
            )
        )
    return tuple(forward), tuple(reverse)


class RotorTables:
    """Precomputed offset permutations and turnover positions for one rotor."""

    __slots__ = ("name", "forward", "reverse", "notches")

    def __init__(self, name: str) -> None:
        wiring, notches = ROTOR_WIRINGS[name]
        self.name = name
        self.forward, self.reverse = _offset_tables(wiring)
        self.notches = frozenset(ord(letter) - 65 for letter in notches)


_ROTOR_CACHE: dict[str, RotorTables] = {}


def rotor_tables(name: str) -> RotorTables:
    name = name.upper()
    cached = _ROTOR_CACHE.get(name)
    if cached is None:
        cached = RotorTables(name)
        _ROTOR_CACHE[name] = cached
    return cached


def reflector_table(name: str = "B") -> tuple[int, ...]:
    return tuple(ord(letter) - 65 for letter in REFLECTOR_WIRINGS[name.upper()])


def plugboard_table(pairs: str | Iterable[str] = "") -> tuple[int, ...]:
    """Build the involution used by :func:`crypt_indices` from stecker pairs."""

    mapping = list(range(26))
    used: set[int] = set()
    tokens = pairs.split() if isinstance(pairs, str) else list(pairs)
    for token in tokens:
        token = token.upper()
        if len(token) != 2 or any(letter not in A for letter in token):
            raise ValueError(f"invalid plugboard pair: {token!r}")
        first, second = (ord(letter) - 65 for letter in token)
        if first == second:
            raise ValueError(f"plugboard pair connects a letter to itself: {token!r}")
        if first in used or second in used:
            raise ValueError(f"plugboard letter reused: {token!r}")
        used.update((first, second))
        mapping[first], mapping[second] = second, first
    return tuple(mapping)


def plugboard_pairs(mapping: Sequence[int]) -> str:
    """Render an involution as the canonical space-separated pair string."""

    pairs = sorted(
        (letter, mapping[letter]) for letter in range(26) if mapping[letter] > letter
    )
    return " ".join(f"{chr(65 + a)}{chr(65 + b)}" for a, b in pairs)


def text_to_indices(text: str) -> tuple[int, ...]:
    """Map A-Z to 0-25 and the uncertainty mask ``?`` to -1."""

    indices = []
    for character in text.upper():
        if character == "?":
            indices.append(-1)
        elif character in A:
            indices.append(ord(character) - 65)
        else:
            raise ValueError(f"unsupported ciphertext character: {character!r}")
    return tuple(indices)


def indices_to_text(indices: Sequence[int]) -> str:
    return "".join("?" if index < 0 else chr(65 + index) for index in indices)


def crypt_indices(
    order: Sequence[RotorTables],
    rings: Sequence[int],
    positions: Sequence[int],
    data: Sequence[int],
    plugboard: Sequence[int] = IDENTITY_PLUGBOARD,
    reflector: Sequence[int] = reflector_table("B"),
) -> list[int]:
    """Encipher/decipher index data.  ``-1`` steps the machine and stays ``-1``.

    ``order`` is left, middle, right.  Enigma is reciprocal, so this is both the
    encryption and the decryption routine.
    """

    left, middle, right = order
    left_forward, left_reverse = left.forward, left.reverse
    middle_forward, middle_reverse = middle.forward, middle.reverse
    right_forward, right_reverse = right.forward, right.reverse
    middle_notches, right_notches = middle.notches, right.notches

    position_left, position_middle, position_right = positions
    ring_left, ring_middle, ring_right = rings
    offset_left = (position_left - ring_left) % 26
    offset_middle = (position_middle - ring_middle) % 26
    offset_right = (position_right - ring_right) % 26

    forward_left = left_forward[offset_left]
    reverse_left = left_reverse[offset_left]
    forward_middle = middle_forward[offset_middle]
    reverse_middle = middle_reverse[offset_middle]

    output: list[int] = []
    append = output.append
    for value in data:
        middle_at_notch = position_middle in middle_notches
        if middle_at_notch:
            position_left = (position_left + 1) % 26
            offset_left = (offset_left + 1) % 26
            forward_left = left_forward[offset_left]
            reverse_left = left_reverse[offset_left]
        if middle_at_notch or position_right in right_notches:
            position_middle = (position_middle + 1) % 26
            offset_middle = (offset_middle + 1) % 26
            forward_middle = middle_forward[offset_middle]
            reverse_middle = middle_reverse[offset_middle]
        position_right = (position_right + 1) % 26
        offset_right = (offset_right + 1) % 26

        if value < 0:
            append(-1)
            continue
        x = plugboard[value]
        x = right_forward[offset_right][x]
        x = forward_middle[x]
        x = forward_left[x]
        x = reflector[x]
        x = reverse_left[x]
        x = reverse_middle[x]
        x = right_reverse[offset_right][x]
        append(plugboard[x])
    return output


def position_permutations(
    order: Sequence[RotorTables],
    rings: Sequence[int],
    positions: Sequence[int],
    length: int,
    reflector: Sequence[int] = reflector_table("B"),
) -> list[int]:
    """Flatten the unsteckered permutation at each of ``length`` positions.

    The result is one list of ``26 * length`` entries: the permutation for
    position ``t`` occupies ``[26 * t, 26 * t + 26)``.  Steckered decryption of
    ciphertext index ``c`` at position ``t`` is then
    ``plugboard[table[26 * t + plugboard[c]]]`` with no stepping work at all,
    which is what makes the stecker hill-climb affordable.
    """

    left, middle, right = order
    middle_notches, right_notches = middle.notches, right.notches
    position_left, position_middle, position_right = positions
    ring_left, ring_middle, ring_right = rings
    offset_left = (position_left - ring_left) % 26
    offset_middle = (position_middle - ring_middle) % 26
    offset_right = (position_right - ring_right) % 26

    # The middle and left wheels are constant for runs of 26 letters, so the
    # composite core is rebuilt only when one of them actually moves.
    core: list[int] | None = None
    table: list[int] = []
    for _ in range(length):
        middle_at_notch = position_middle in middle_notches
        moved = False
        if middle_at_notch:
            position_left = (position_left + 1) % 26
            offset_left = (offset_left + 1) % 26
            moved = True
        if middle_at_notch or position_right in right_notches:
            position_middle = (position_middle + 1) % 26
            offset_middle = (offset_middle + 1) % 26
            moved = True
        position_right = (position_right + 1) % 26
        offset_right = (offset_right + 1) % 26

        if core is None or moved:
            forward_left = left.forward[offset_left]
            reverse_left = left.reverse[offset_left]
            forward_middle = middle.forward[offset_middle]
            reverse_middle = middle.reverse[offset_middle]
            core = [
                reverse_middle[reverse_left[reflector[forward_left[forward_middle[x]]]]]
                for x in range(26)
            ]
        forward_right = right.forward[offset_right]
        reverse_right = right.reverse[offset_right]
        table.extend(reverse_right[core[forward_right[x]]] for x in range(26))
    return table


def decrypt_with_tables(
    table: Sequence[int], data: Sequence[int], plugboard: Sequence[int]
) -> list[int]:
    """Apply a plugboard to precomputed per-position permutations."""

    return [
        -1 if value < 0 else plugboard[table[offset + plugboard[value]]]
        for offset, value in zip(range(0, 26 * len(data), 26), data)
    ]


def standard_rotor_orders(names: Sequence[str] = ("I", "II", "III", "IV", "V")):
    """Left-middle-right orders over the Army/Air Force wheel set."""

    return list(itertools.permutations(names, 3))


def unsteckered_date_counts(
    order: Sequence[RotorTables],
    rings: Sequence[int],
    messages: Sequence[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]],
    reflector: Sequence[int],
    counts: list[int],
) -> list[tuple[int, int, int]]:
    """Decrypt a whole date's traffic unsteckered and accumulate letter counts.

    ``messages`` holds ``(grundstellung, encrypted_message_key, body)`` index
    triples.  ``counts`` is a 26-entry accumulator the caller zeroes; the
    return value is the recovered message key per message.  This is the sweep's
    inner loop, so the stepping and the letter census are fused and the
    plaintext is never materialised.
    """

    left, middle, right = order
    left_forward, left_reverse = left.forward, left.reverse
    middle_forward, middle_reverse = middle.forward, middle.reverse
    right_forward, right_reverse = right.forward, right.reverse
    middle_notches, right_notches = middle.notches, right.notches
    ring_left, ring_middle, ring_right = rings

    keys: list[tuple[int, int, int]] = []
    for grundstellung, encrypted_key, body in messages:
        # Stage one: the clear Grundstellung deciphers the message key.
        position_left, position_middle, position_right = grundstellung
        offset_left = (position_left - ring_left) % 26
        offset_middle = (position_middle - ring_middle) % 26
        offset_right = (position_right - ring_right) % 26
        forward_left = left_forward[offset_left]
        reverse_left = left_reverse[offset_left]
        forward_middle = middle_forward[offset_middle]
        reverse_middle = middle_reverse[offset_middle]
        key: list[int] = []
        for value in encrypted_key:
            middle_at_notch = position_middle in middle_notches
            if middle_at_notch:
                position_left = (position_left + 1) % 26
                offset_left = (offset_left + 1) % 26
                forward_left = left_forward[offset_left]
                reverse_left = left_reverse[offset_left]
            if middle_at_notch or position_right in right_notches:
                position_middle = (position_middle + 1) % 26
                offset_middle = (offset_middle + 1) % 26
                forward_middle = middle_forward[offset_middle]
                reverse_middle = middle_reverse[offset_middle]
            position_right = (position_right + 1) % 26
            offset_right = (offset_right + 1) % 26
            x = right_forward[offset_right][value]
            x = forward_middle[x]
            x = forward_left[x]
            x = reflector[x]
            x = reverse_left[x]
            x = reverse_middle[x]
            key.append(right_reverse[offset_right][x])
        keys.append((key[0], key[1], key[2]))

        # Stage two: the body at the recovered message key.
        position_left, position_middle, position_right = key
        offset_left = (position_left - ring_left) % 26
        offset_middle = (position_middle - ring_middle) % 26
        offset_right = (position_right - ring_right) % 26
        forward_left = left_forward[offset_left]
        reverse_left = left_reverse[offset_left]
        forward_middle = middle_forward[offset_middle]
        reverse_middle = middle_reverse[offset_middle]
        for value in body:
            middle_at_notch = position_middle in middle_notches
            if middle_at_notch:
                position_left = (position_left + 1) % 26
                offset_left = (offset_left + 1) % 26
                forward_left = left_forward[offset_left]
                reverse_left = left_reverse[offset_left]
            if middle_at_notch or position_right in right_notches:
                position_middle = (position_middle + 1) % 26
                offset_middle = (offset_middle + 1) % 26
                forward_middle = middle_forward[offset_middle]
                reverse_middle = middle_reverse[offset_middle]
            position_right = (position_right + 1) % 26
            offset_right = (offset_right + 1) % 26
            if value < 0:
                continue
            x = right_forward[offset_right][value]
            x = forward_middle[x]
            x = forward_left[x]
            x = reflector[x]
            x = reverse_left[x]
            x = reverse_middle[x]
            counts[right_reverse[offset_right][x]] += 1
    return keys


def parity_report(seed: int, samples: int) -> dict[str, object]:
    """Check this kernel against ``enigma.py`` on pseudorandom settings.

    Both the direct kernel and the precomputed-permutation path are checked,
    with and without a plugboard, because they are separate implementations of
    the same algebra and either could drift on its own.
    """

    generator = random.Random(seed)
    orders = standard_rotor_orders()
    mismatches: list[dict[str, object]] = []
    for _ in range(samples):
        names = list(orders[generator.randrange(len(orders))])
        rings = "".join(generator.choice(A) for _ in range(3))
        start = "".join(generator.choice(A) for _ in range(3))
        letters = generator.sample(A, 2 * generator.randrange(0, 11))
        pairs = " ".join(
            letters[index] + letters[index + 1] for index in range(0, len(letters), 2)
        )
        length = generator.randrange(1, 200)
        text = "".join(generator.choice(A) for _ in range(length))

        expected = EnigmaI(
            rotors=names, rings=rings, positions=start, plugboard=pairs
        ).crypt(text)

        order = [rotor_tables(name) for name in names]
        ring_indices = [ord(letter) - 65 for letter in rings]
        start_indices = [ord(letter) - 65 for letter in start]
        plugboard = plugboard_table(pairs)
        data = text_to_indices(text)

        direct = indices_to_text(
            crypt_indices(order, ring_indices, start_indices, data, plugboard)
        )
        precomputed = indices_to_text(
            decrypt_with_tables(
                position_permutations(order, ring_indices, start_indices, len(data)),
                data,
                plugboard,
            )
        )
        if direct != expected or precomputed != expected:
            mismatches.append(
                {
                    "rotors": names,
                    "rings": rings,
                    "positions": start,
                    "plugboard": pairs,
                    "direct_matches_reference": direct == expected,
                    "precomputed_matches_reference": precomputed == expected,
                }
            )
    return {
        "reference": "enigma.EnigmaI",
        "seed": seed,
        "samples": samples,
        "checked_paths": ["crypt_indices", "position_permutations+decrypt_with_tables"],
        "mismatches": mismatches,
        "passed": not mismatches,
    }
