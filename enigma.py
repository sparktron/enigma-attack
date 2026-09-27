#!/usr/bin/env python3
"""Transparent three-wheel Enigma-family simulator.

The :class:`EnigmaI` compatibility wrapper retains the project's original API.
The configurable :class:`EnigmaMachine` adds alternate entry wheels, reflectors,
multi-notch rotors, settable reflectors, and the documented 1941 Swiss-K stepping
change needed by the Phase 3 variant comparison.
"""
from __future__ import annotations

import string
from collections.abc import Mapping, Sequence

A = string.ascii_uppercase
ROTOR_WIRINGS = {
    "I": ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II": ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV": ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V": ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
    "VI": ("JPGVOUMFYQBENHZRDKASXLICTW", "ZM"),
    "VII": ("NZJHGRCXMYSWBOUFAIVLPEKQDT", "ZM"),
    "VIII": ("FKQHTLXOCBJSPDZRAMEWNIUYGV", "ZM"),
}
REFLECTOR_WIRINGS = {
    "A": "EJMZALYXVBWFCRQUONTSPIKHGD",
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
}
REFLECTOR_B = REFLECTOR_WIRINGS["B"]
IDENTITY_WIRING = A


def idx(c: str) -> int:
    return ord(c) - 65


def ch(i: int) -> str:
    return chr(i % 26 + 65)


def _permutation(wiring: str, label: str) -> list[int]:
    wiring = wiring.upper()
    if len(wiring) != 26 or set(wiring) != set(A):
        raise ValueError(f"{label} must be a permutation of A-Z")
    return [idx(c) for c in wiring]


def _reflector(wiring: str) -> list[int]:
    result = _permutation(wiring, "reflector wiring")
    if any(i == value or result[value] != i for i, value in enumerate(result)):
        raise ValueError("reflector wiring must be fixed-point-free and involutive")
    return result


def plugmap(pairs: str = "") -> list[int]:
    """Build an involutive plugboard map from space-separated pairs."""
    mapping = list(range(26))
    used: set[str] = set()
    for pair in pairs.upper().split():
        if len(pair) != 2 or any(c not in A for c in pair):
            raise ValueError(f"invalid plugboard pair: {pair!r}")
        if pair[0] == pair[1]:
            raise ValueError(f"plugboard pair connects a letter to itself: {pair!r}")
        if used.intersection(pair):
            raise ValueError(f"plugboard letter reused: {pair!r}")
        used.update(pair)
        first, second = map(idx, pair)
        mapping[first], mapping[second] = second, first
    return mapping


class Rotor:
    def __init__(
        self,
        name: str,
        ring: str = "A",
        pos: str = "A",
        *,
        rotor_wirings: Mapping[str, tuple[str, str]] | None = None,
    ) -> None:
        name = name.upper()
        ring = ring.upper()
        pos = pos.upper()
        wirings = ROTOR_WIRINGS if rotor_wirings is None else rotor_wirings
        if name not in wirings:
            raise ValueError(f"unknown rotor: {name!r}")
        if len(ring) != 1 or ring not in A:
            raise ValueError(f"invalid ring setting: {ring!r}")
        if len(pos) != 1 or pos not in A:
            raise ValueError(f"invalid rotor position: {pos!r}")
        wiring, notches = wirings[name]
        self.name = name
        self.w = _permutation(wiring, f"rotor {name} wiring")
        self.inv = [0] * 26
        for i, value in enumerate(self.w):
            self.inv[value] = i
        if not notches or any(c not in A for c in notches.upper()):
            raise ValueError(f"rotor {name} must have at least one A-Z turnover")
        self.notches = frozenset(idx(c) for c in notches.upper())
        self.notch = min(self.notches)  # Backward-compatible inspection aid.
        self.ring = idx(ring)
        self.pos = idx(pos)

    def at_notch(self) -> bool:
        return self.pos in self.notches

    def step(self) -> None:
        self.pos = (self.pos + 1) % 26

    def fwd(self, x: int) -> int:
        y = (x + self.pos - self.ring) % 26
        y = self.w[y]
        return (y - self.pos + self.ring) % 26

    def rev(self, x: int) -> int:
        y = (x + self.pos - self.ring) % 26
        y = self.inv[y]
        return (y - self.pos + self.ring) % 26


class EnigmaMachine:
    """Configurable, reciprocal, three-wheel Enigma-family machine."""

    def __init__(
        self,
        rotors: Sequence[str],
        rings: str = "AAA",
        positions: str = "AAA",
        plugboard: str = "",
        *,
        rotor_wirings: Mapping[str, tuple[str, str]] | None = None,
        reflector: str = REFLECTOR_B,
        entry_wiring: str = IDENTITY_WIRING,
        reflector_position: str = "A",
        stepping: str = "pawl",
    ) -> None:
        rotors = tuple(name.upper() for name in rotors)
        rings = rings.upper()
        positions = positions.upper()
        reflector_position = reflector_position.upper()
        if len(rotors) != 3 or len(rings) != 3 or len(positions) != 3:
            raise ValueError("3 rotors/rings/positions required")
        if len(set(rotors)) != 3:
            raise ValueError("rotors must be distinct")
        if len(reflector_position) != 1 or reflector_position not in A:
            raise ValueError(f"invalid reflector position: {reflector_position!r}")
        if stepping not in {"pawl", "swiss_k_1941"}:
            raise ValueError(f"unsupported stepping mode: {stepping!r}")

        wirings = ROTOR_WIRINGS if rotor_wirings is None else rotor_wirings
        self.L, self.M, self.R = [
            Rotor(name, ring, position, rotor_wirings=wirings)
            for name, ring, position in zip(rotors, rings, positions)
        ]
        self.plug = plugmap(plugboard)
        self.entry = _permutation(entry_wiring, "entry wiring")
        self.entry_inv = [0] * 26
        for i, value in enumerate(self.entry):
            self.entry_inv[value] = i
        self.reflector = _reflector(reflector)
        self.reflector_pos = idx(reflector_position)
        self.stepping = stepping

    @property
    def positions(self) -> str:
        return "".join(ch(rotor.pos) for rotor in (self.L, self.M, self.R))

    @property
    def reflector_position(self) -> str:
        return ch(self.reflector_pos)

    def step(self) -> None:
        if self.stepping == "swiss_k_1941":
            # The Swiss Army modification immobilized the right wheel, made the
            # middle wheel fast, and left the slow wheel/UKW turnovers intact.
            left_notch = self.L.at_notch()
            middle_notch = self.M.at_notch()
            if left_notch:
                self.reflector_pos = (self.reflector_pos + 1) % 26
            if middle_notch or left_notch:
                self.L.step()
            self.M.step()
            return

        # Pawl machine: middle-wheel double step.
        middle_notch = self.M.at_notch()
        right_notch = self.R.at_notch()
        if middle_notch:
            self.L.step()
        if middle_notch or right_notch:
            self.M.step()
        self.R.step()

    def key(self, c: str) -> str:
        if c not in A:
            return c
        self.step()
        x = self.plug[idx(c)]
        x = self.entry[x]
        x = self.R.fwd(x)
        x = self.M.fwd(x)
        x = self.L.fwd(x)
        x = (x + self.reflector_pos) % 26
        x = self.reflector[x]
        x = (x - self.reflector_pos) % 26
        x = self.L.rev(x)
        x = self.M.rev(x)
        x = self.R.rev(x)
        x = self.entry_inv[x]
        x = self.plug[x]
        return ch(x)

    def crypt(self, text: str) -> str:
        return "".join(self.key(c) for c in text.upper() if c in A)


class EnigmaI(EnigmaMachine):
    """Compatibility wrapper for the standard steckered service Enigma."""

    def __init__(
        self,
        rotors: Sequence[str] = ("I", "II", "III"),
        rings: str = "AAA",
        positions: str = "AAA",
        plugboard: str = "",
        reflector: str = "B",
    ) -> None:
        reflector_name = reflector.upper()
        if reflector_name not in REFLECTOR_WIRINGS:
            raise ValueError(f"unknown reflector: {reflector!r}")
        super().__init__(
            rotors,
            rings,
            positions,
            plugboard,
            reflector=REFLECTOR_WIRINGS[reflector_name],
        )


if __name__ == "__main__":
    # Widely published standard Enigma-I vector: I-II-III, rings AAA, start AAA.
    vector = EnigmaI(rotors=("I", "II", "III"), rings="AAA", positions="AAA").crypt("AAAAA")
    print("VECTOR AAAAA ->", vector)
    assert vector == "BDZGO"
    # Reciprocity sanity check.
    plaintext = "DIESISTEINTEST"
    config = dict(
        rotors=("II", "V", "III"),
        rings="HMF",
        positions="RWD",
        plugboard="AC BE DG FH KN MO PR SU TV XZ",
    )
    ciphertext = EnigmaI(**config).crypt(plaintext)
    recovered = EnigmaI(**config).crypt(ciphertext)
    print("PT", plaintext)
    print("CT", ciphertext)
    print("RT", recovered)
    assert recovered == plaintext
    # Py-Enigma's documented German Army procedure example.
    config = dict(
        rotors=("II", "IV", "V"),
        rings="BUL",
        positions="WXC",
        plugboard="AV BS CG DL FU HZ IN KM OW RX",
    )
    assert EnigmaI(**config).crypt("KCH") == "BLA"
