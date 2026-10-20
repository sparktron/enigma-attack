#!/usr/bin/env python3
"""Rebuild data/historical/keyed-messages.json from the companion page.

Reads a saved copy of https://cryptocellar.org/enigma/enigma-modern-breaking.html
(the page is not committed; its SHA-256 is recorded in the output) and
transcribes each message's key, discriminant, ciphertext and raw plaintext.

The page prints No. 1 of 1 October's key line for No. 2 as well, start
position included. That start position is replaced by the only one of the
17,576 that deciphers No. 2 to its published raw plaintext; the search is
run here, not assumed, and the published value is kept beside it.
"""

from __future__ import annotations

import argparse
import html
import itertools
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from enigma import A, EnigmaI  # noqa: E402
from provenance import sha256_file  # noqa: E402

PAGE_URL = "https://cryptocellar.org/enigma/enigma-modern-breaking.html"
KEY = re.compile(r"^([BC])([1-5])([1-5])([1-5]) ([a-z]{3}) ([A-Z]{3})((?: [A-Z]{2}){10}) *$")
GROUPS = re.compile(r"^ *[A-Z-]{1,5}(?: [A-Z-]{1,5})* *$")
HEADER = re.compile(r"^Message No\. (\d+) of (\d+) (\w+) (\d{4}) *$")
MONTHS = {m: i for i, m in enumerate(
    "January February March April May June July August September October November December".split(), 1)}
ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
REPEATED_KEY_LINE = "1941-10-01-2"
NOTES = {
    "1941-08-27-71": "The message form records only the first part of the ciphertext; the raw plaintext is the matching part.",
    "1941-07-19-233": ("Enciphered on 18 July with that day's key and received on the 19th. '-' marks a ciphertext letter "
                       "illegible on the form and the plaintext letter it would give; the machine still steps for it."),
    "1941-08-22-30": "Enciphered on 21 August with that day's key and sent on the 22nd.",
}


def page_lines(page: str) -> list[str]:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|h\d|tr|pre|li)>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    # The raw plaintext is indented with non-breaking spaces.
    return text.replace(" ", " ").splitlines()


def parse(lines: list[str]) -> list[dict]:
    out, header, i = [], None, 0
    while i < len(lines):
        found = HEADER.match(lines[i])
        if found:
            header = found
        key = KEY.match(lines[i])
        if key and header:
            number, day, month, year = header.groups()
            i += 1
            cipher, raw, in_raw = [], [], False
            while i < len(lines):
                line = lines[i]
                if not line.strip():
                    i += 1
                    continue
                if not GROUPS.match(line):
                    break
                if line.startswith("      "):
                    in_raw = True
                (raw if in_raw else cipher).append(line.split())
                i += 1
            groups = [g for row in cipher for g in row]
            date = f"{year}-{MONTHS[month]:02d}-{int(day):02d}"
            out.append({
                "id": f"{date}-{number}",
                "number": int(number),
                "date": date,
                "key_as_published": " ".join(key.group(0).split()),
                "reflector": key.group(1),
                "rotors": [ROMAN[key.group(n)] for n in (2, 3, 4)],
                "rings": key.group(5).upper(),
                "start_position": key.group(6),
                "plugboard": key.group(7).strip(),
                "discriminant": groups[0],
                "ciphertext": "".join(groups[1:]),
                "raw_plaintext": "".join(g for row in raw for g in row),
            })
            header = None
            continue
        i += 1
    return out


def agreement(message: dict, start: str) -> int:
    machine = EnigmaI(rotors=message["rotors"], rings=message["rings"], positions=start,
                      plugboard=message["plugboard"], reflector=message["reflector"])
    return sum(a == b for a, b in zip(machine.crypt(message["ciphertext"]), message["raw_plaintext"]))


def correct_start_position(message: dict) -> tuple[str, int]:
    scores = sorted(((agreement(message, "".join(p)), "".join(p)) for p in itertools.product(A, repeat=3)),
                    reverse=True)
    (best, start), (runner_up, _) = scores[0], scores[1]
    if best != len(message["ciphertext"]):
        raise SystemExit(f"{message['id']}: no start position reproduces the plaintext (best {best})")
    return start, runner_up


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page", type=pathlib.Path, help="saved copy of the companion page")
    parser.add_argument("--retrieved", required=True, help="retrieval date of that copy, YYYY-MM-DD")
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "data" / "historical" / "keyed-messages.json")
    arguments = parser.parse_args()

    messages = parse(page_lines(arguments.page.read_text(encoding="utf-8", errors="replace")))
    if len(messages) != 13:
        raise SystemExit(f"expected the article's 13 messages, parsed {len(messages)}")
    for message in messages:
        if message["id"] == REPEATED_KEY_LINE:
            start, runner_up = correct_start_position(message)
            message["start_position_as_published"] = message["start_position"]
            message["start_position"] = start
            message["note"] = (
                f"The page prints No. 1's key line for this message, start position {message['start_position_as_published']} "
                f"included, and {message['start_position_as_published']} does not decipher it. Under the published wheels, "
                f"rings and plugs, {start} is the only one of the 17,576 start positions that reproduces the published raw "
                f"plaintext ({len(message['ciphertext'])} of {len(message['ciphertext'])} letters); the next best agrees "
                f"on {runner_up}. Searched 2026-10-20.")
        elif message["id"] in NOTES:
            message["note"] = NOTES[message["id"]]

    document = {
        "schema": "enigma-attack.historical-keyed-messages/v1",
        "purpose": ("Authentic 1941 German Army Enigma messages with their recovered keys and published raw plaintext. "
                    "tests/test_historical_messages.py deciphers each with enigma.EnigmaI and requires the published raw "
                    "plaintext letter for letter, so the machine model is checked against real traffic, not only against "
                    "keys this repository planted itself."),
        "source": {
            "url": PAGE_URL,
            "attribution": "Olaf Ostwald and Frode Weierud, 'Modern breaking of Enigma ciphertexts', Cryptologia 41(5), 395-421, companion page at CryptoCellar",
            "license": "CC BY-NC-SA 4.0, as data/phase5/README.md records for the CryptoCellar material",
            "retrieved_utc": arguments.retrieved,
            "sha256": sha256_file(arguments.page),
            "sha256_note": "Identical to the copy fetched for data/phase2/held-out-plaintexts.json on 2026-10-06.",
        },
        "conventions": {
            "key_as_published": "Reflector and wheel order (B423 = UKW B, wheels IV II III left to right), ring settings, start position (message setting), ten plugs.",
            "discriminant": "The first group is the Kenngruppe and is not enciphered; deciphering starts at the second group.",
            "ciphertext": "The groups after the discriminant, whitespace removed.",
            "raw_plaintext": "The page's raw plaintext, whitespace removed; garbles kept as published, X as word separator, Q for CH.",
        },
        "messages": messages,
    }
    arguments.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
