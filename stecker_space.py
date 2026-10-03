"""The rotor-setting spaces the Phase 1 sweeps enumerate, and their ring rules.

Which ring settings a body-direct sweep holds or searches decides which true
keys have an exactly equivalent setting inside the swept space.
:class:`RingRule` turns searched axes into settings, and
:func:`rule_key_coverage` measures that coverage exactly by comparing
stepping patterns.
"""

from __future__ import annotations

import functools
import itertools
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import enigma_fast


def ring_space(specification: Any) -> list[tuple[int, int, int]]:
    if specification == "all":
        return list(itertools.product(range(26), repeat=3))
    if isinstance(specification, list):
        return [
            tuple(ord(letter) - 65 for letter in value.upper())  # type: ignore[misc]
            for value in specification
        ]
    raise ValueError(f"unsupported ring specification: {specification!r}")


def rotor_order_space(specification: Any, wheel_set: Sequence[str]) -> list[tuple[str, ...]]:
    if specification == "all_permutations":
        return [tuple(order) for order in itertools.permutations(wheel_set, 3)]
    if isinstance(specification, list):
        return [tuple(name.upper() for name in order) for order in specification]
    raise ValueError(f"unsupported rotor-order specification: {specification!r}")


RING_RULES = ("held", "middle_past_notch", "middle_complete")

Rings = tuple[int, int, int]
Setting = tuple[Rings, tuple[int, int, int]]


def middle_start_phases(notches: Iterable[int], length: int, complete: bool) -> list[int]:
    """Visible middle-wheel start positions a sweep needs for one wheel.

    Over ``length`` letters the right wheel passes its notch at most
    ``ceil(length / 26)`` times, so the middle wheel advances at most that often.
    A start from which none of the positions it can reach is a middle notch
    never steps the left wheel, and the message is then enciphered by a machine
    whose left wheel is fixed.  The first phase returned is the one just past
    the notch, the farthest from it.  ``complete`` appends every other start,
    those from which the notch falls inside the message, so a true key whose
    left wheel does step still has an equivalent in the swept space.
    """

    notch_set = frozenset(notches)
    advances = -(-length // 26)
    clear = [
        start
        for start in range(26)
        if not any((start + step) % 26 in notch_set for step in range(advances + 1))
    ]
    just_past = next(
        ((notch + 1) % 26 for notch in sorted(notch_set) if (notch + 1) % 26 in clear), None
    )
    if just_past is None:
        raise ValueError(f"no middle start keeps {sorted(notch_set)} out of {length} letters")
    phases = [just_past]
    if complete:
        phases.extend(start for start in range(26) if start not in clear)
    return phases


@dataclass(frozen=True)
class RingRule:
    """How a sweep turns its searched axes into rings and visible positions.

    Only the wheel *offset* (position minus ring) reaches the wiring, but the
    stepping depends on the absolute position.  A swept setting that has the
    true offsets and a different ring therefore agrees with the true key only
    until a wheel passes its notch at a different moment than the true wheel
    does.  The right wheel's position and ring both matter, because the middle
    wheel steps when the right wheel passes its notch; the left wheel's ring
    does not, because nothing follows it.  The middle wheel's ring matters
    because its notch steps the left wheel.

    ``held``
        The rings are fixed (``held``) apart from the right ring, which takes
        every value in ``right_rings``.  The start axes are visible positions.
    ``middle_past_notch``
        The left ring is fixed, the right ring is searched, and the middle ring
        is chosen from the searched middle offset so that the middle wheel
        starts just past its notch.  The start axes are the left and middle
        *offsets* and the right position.
    ``middle_complete``
        As above, but every middle start from which the notch falls inside the
        message is searched as well as the one past it.
    """

    name: str
    held: Rings
    right_rings: tuple[int, ...]
    length: int

    def __post_init__(self) -> None:
        if self.name not in RING_RULES:
            raise ValueError(f"unknown ring rule: {self.name!r}")

    @classmethod
    def from_config(cls, settings: Mapping[str, Any], length: int) -> "RingRule":
        held = tuple(ord(letter) - 65 for letter in settings["rings"].upper())
        right = (
            tuple(resolve_axis(settings["right_ring"]))
            if "right_ring" in settings
            else (held[2],)
        )
        return cls(settings.get("ring_rule", "held"), held, right, length)  # type: ignore[arg-type]

    def middle_phases(self, middle_wheel: str) -> list[int] | None:
        if self.name == "held":
            return None
        return middle_start_phases(
            enigma_fast.rotor_tables(middle_wheel).notches,
            self.length,
            self.name == "middle_complete",
        )

    def settings(
        self, names: Sequence[str], starts: Sequence[tuple[int, int, int]]
    ) -> list[Setting]:
        phases = self.middle_phases(names[1])
        out: list[Setting] = []
        for start in starts:
            if phases is None:
                for ring in self.right_rings:
                    out.append(((self.held[0], self.held[1], ring), tuple(start)))  # type: ignore[arg-type]
                continue
            offset_left, offset_middle, position_right = start
            for phase in phases:
                for ring in self.right_rings:
                    out.append(
                        (
                            (self.held[0], (phase - offset_middle) % 26, ring),
                            ((offset_left + self.held[0]) % 26, phase, position_right),
                        )
                    )
        return out


def reducible_space_size(rule_name: str, length: int, wheel_set: Sequence[str]) -> int:
    """Settings a complete sweep of every wheel order would evaluate under a rule.

    Each order has 26 left offsets, 26 middle offsets, 26 right positions and 26
    right rings.  ``held`` and ``middle_past_notch`` evaluate one setting per
    combination; ``middle_complete`` adds one per extra middle start.
    """

    rule = RingRule(rule_name, (0, 0, 0), (0,), length)
    total = 0
    for order in rotor_order_space("all_permutations", wheel_set):
        phases = rule.middle_phases(order[1])
        total += 26**4 * (1 if phases is None else len(phases))
    return total


def stepping_pattern(
    middle_notches: Iterable[int],
    right_notches: Iterable[int],
    position_middle: int,
    position_right: int,
    length: int,
) -> bytes:
    """Which letters step the left and middle wheels, as ``position_permutations`` does."""

    middle_set, right_set = frozenset(middle_notches), frozenset(right_notches)
    pattern = bytearray()
    for _ in range(length):
        left = position_middle in middle_set
        middle = left or position_right in right_set
        if middle:
            position_middle = (position_middle + 1) % 26
        position_right = (position_right + 1) % 26
        pattern.append(2 * left + middle)
    return bytes(pattern)


@functools.lru_cache(maxsize=None)
def rule_key_coverage(rule_name: str, length: int, wheel_set: tuple[str, ...]) -> float:
    """Fraction of true keys that have an exact equivalent in the swept space.

    Two settings with equal offsets decipher a message identically exactly when
    their left and middle wheels step at the same letters, so equivalence is a
    comparison of stepping patterns.  The right wheel is always reachable
    because the right ring is a searched axis.  Every wheel pair and every
    true middle position, middle ring and right position is weighted equally,
    which is uniform over daily keys because the left wheel does not enter.
    """

    rule = RingRule(rule_name, (0, 0, 0), (0,), length)
    covered = total = 0
    for middle_name in wheel_set:
        for right_name in wheel_set:
            if middle_name == right_name:
                continue
            middle_notches = enigma_fast.rotor_tables(middle_name).notches
            right_notches = enigma_fast.rotor_tables(right_name).notches
            patterns = {
                (position_middle, position_right): stepping_pattern(
                    middle_notches, right_notches, position_middle, position_right, length
                )
                for position_middle in range(26)
                for position_right in range(26)
            }
            phases = rule.middle_phases(middle_name)
            for position_middle in range(26):
                for ring_middle in range(26):
                    offset = (position_middle - ring_middle) % 26
                    swept = [offset] if phases is None else phases
                    for position_right in range(26):
                        true_pattern = patterns[(position_middle, position_right)]
                        total += 1
                        if any(patterns[(start, position_right)] == true_pattern for start in swept):
                            covered += 1
    return covered / total


def resolve_axis(specification: Any) -> list[int]:
    if specification == "all":
        return list(range(26))
    if isinstance(specification, str):
        return [ord(letter) - 65 for letter in specification.upper()]
    if isinstance(specification, list):
        return [ord(str(value).upper()) - 65 for value in specification]
    raise ValueError(f"unsupported start-position axis: {specification!r}")
