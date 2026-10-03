"""Phase 1 traffic in kernel index form, from the corpus or a known-key control."""

from __future__ import annotations

import json
import pathlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import enigma_fast
from enigma import A, EnigmaI
from provenance import sha256_text

# The indicator is two trigrams.  ``phase1.py:139`` fixes the first as the clear
# Grundstellung and the second as the enciphered message key.  That is the usual
# 1940+ Army convention, but a transcription could have recorded them the other
# way round, so both orderings are searched wherever the indicator is used.
INDICATOR_ORDERINGS = {
    "grundstellung_first": (0, 1),
    "message_key_first": (1, 0),
}


@dataclass(frozen=True)
class Traffic:
    """One message reduced to the index form the kernel consumes."""

    designator: str
    first_trigram: tuple[int, ...]
    second_trigram: tuple[int, ...]
    body: tuple[int, ...]

    def oriented(
        self, ordering: str
    ) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
        grund, encrypted = INDICATOR_ORDERINGS[ordering]
        trigrams = (self.first_trigram, self.second_trigram)
        return trigrams[grund], trigrams[encrypted], self.body

    @property
    def letters(self) -> int:
        return sum(1 for value in self.body if value >= 0)


def traffic_from_corpus(
    corpus_path: pathlib.Path, date: str, designators: Sequence[str]
) -> list[Traffic]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    by_designator = {record["designator"]: record for record in corpus["messages"]}
    traffic: list[Traffic] = []
    for designator in designators:
        record = by_designator[designator]
        if record["date"] != date:
            raise ValueError(f"{designator} is not from {date}")
        traffic.append(
            Traffic(
                designator=designator,
                first_trigram=enigma_fast.text_to_indices(record["indicator"][0]),
                second_trigram=enigma_fast.text_to_indices(record["indicator"][1]),
                body=enigma_fast.text_to_indices(record["ciphertext"]),
            )
        )
    return traffic


def normalize_plaintext(raw: str, length: int | None = None) -> str:
    text = "".join(raw.split()).upper()
    if any(letter not in A for letter in text):
        raise ValueError("control plaintext must be A-Z after whitespace removal")
    if length is not None:
        if len(text) < length:
            raise ValueError(f"control plaintext is shorter than the requested {length}")
        text = text[:length]
    return text


def random_plugboard(generator: random.Random, pairs: int) -> str:
    letters = generator.sample(list(A), 2 * pairs)
    return " ".join(letters[index] + letters[index + 1] for index in range(0, 2 * pairs, 2))


def encipher_control(spec: Mapping[str, Any]) -> tuple[list[Traffic], dict[str, Any]]:
    """Encipher known plaintexts under a known key with the reference machine.

    The control ciphertext is produced by ``enigma.EnigmaI`` while the attack
    runs on ``enigma_fast``.  A control that only round-trips through the fast
    kernel would pass even if the kernel and the search shared a fault.
    """

    key = spec["key"]
    rotors = tuple(name.upper() for name in key["rotor_order"])
    rings = key["rings"].upper()
    plugboard = key.get("plugboard", "")
    ordering = spec.get("indicator_ordering", "grundstellung_first")
    grund_index, encrypted_index = INDICATOR_ORDERINGS[ordering]

    traffic: list[Traffic] = []
    rendered: list[dict[str, Any]] = []
    plaintexts: list[str] = []
    for message in spec["messages"]:
        plaintext = normalize_plaintext(message["plaintext"], message.get("length"))
        grundstellung = message["grundstellung"].upper()
        message_key = message["message_key"].upper()
        encrypted_key = EnigmaI(
            rotors=rotors, rings=rings, positions=grundstellung, plugboard=plugboard
        ).crypt(message_key)
        ciphertext = EnigmaI(
            rotors=rotors, rings=rings, positions=message_key, plugboard=plugboard
        ).crypt(plaintext)
        transcribed = ["", ""]
        transcribed[grund_index] = grundstellung
        transcribed[encrypted_index] = encrypted_key
        traffic.append(
            Traffic(
                designator=message["designator"],
                first_trigram=enigma_fast.text_to_indices(transcribed[0]),
                second_trigram=enigma_fast.text_to_indices(transcribed[1]),
                body=enigma_fast.text_to_indices(ciphertext),
            )
        )
        plaintexts.append(plaintext)
        rendered.append(
            {
                "designator": message["designator"],
                "length": len(plaintext),
                "indicator": transcribed,
                "true_message_key": message_key,
                "plaintext_sha256": sha256_text(plaintext),
            }
        )
    truth = {
        "rotor_order_left_to_right": list(rotors),
        "rings": rings,
        "plugboard": enigma_fast.plugboard_pairs(enigma_fast.plugboard_table(plugboard)),
        "plugboard_pairs": len(plugboard.split()),
        "indicator_ordering": ordering,
        "messages": rendered,
    }
    return traffic, {"truth": truth, "plaintexts": plaintexts}
