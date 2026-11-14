"""Build a source-linked inventory without guessing unreadable characters."""
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
BASE = "https://www.cryptocellar.org/bgac/"
EXCLUDED = ("BYQMZ", "FKQLZ", "XFEDT")
ROMAN = {str(i): r for i, r in enumerate(("I", "II", "III", "IV", "V"), 1)}


def text(value):
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def sections(path):
    for heading, body in re.findall(r"<h4>(.*?)</h4>.*?<pre>(.*?)</pre>", path.read_text(), re.S | re.I):
        yield text(heading), text(body)


def normalize(grouped):
    compact = "".join(grouped.split()).replace("-", "?")
    if not compact or re.search(r"[^A-Z?]", compact):
        raise ValueError("ciphertext must contain A-Z and positional erasures only")
    return compact


def build():
    source = ROOT / "data/remaining-1941/sources"
    manifest = json.loads((source / "manifest.json").read_text())
    for entry in manifest:
        if hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"source drift: {entry['path']}")
    wanted = {"EHSTQ": 3, "RXPSB": 53, "KLJBO": 87, "LXACA": 100, "WEUWY": 138,
              "AWTZK": 187, "ZNLZT": 189, "JBIYH": 242, "FMNGI": 285}
    keys = {
        "AWTZK": ("143", "EXS", "AO BF CQ DH EW GJ KX NU PY RT", "ERT"),
        "ZNLZT": ("143", "EXS", "AO BF CQ DH EW GJ KX NU PY RT", "NML"),
        "JBIYH": ("541", "EXT", "AU BI CY ET FL HK MP NR OX QV", "TZU"),
        "FMNGI": ("243", "UHP", "AH DJ EM FO GI KP LU NS QW TX", "TOG"),
    }
    notes = {
        "EHSTQ": ["HTML header says Funkspruch Nr.45; original red serial and heading say 3.",
                  "No positional erasure in published text; faint handwriting is not proof of error-free interception.",
                  "No 22 June key in either published key list; no demonstrated key-sharing companion."],
        "RXPSB": ["Unbroken list says 104/99; original header says114, but counting published groups gives112 total/107 body positions, including two erasures (105 readable body letters). Do not manufacture two extra characters to match the header.",
                  "GX-WE and UNU-T contain positional erasures; retain both, do not delete them.",
                  "Original inspected: six lines ending ED, 22 complete five-letter groups plus ED including Kenngruppe. Header discrepancy of two positions is unresolved; no basis for removing letters.",
                  "PLDRV shares reception date/callsign 5l8 and AK to Ib, but publisher dates its encryption/key to 27 June. RXPSB has 1020 and reception1126 on28 June; previous-day key is a test hypothesis, not a constraint."],
        "KLJBO": ["Published OYL-N, -NWK-, A-UVV give four positional erasures.",
                  "Scan has trailing writing after the last published group, possibly an operator mark; not promoted to ciphertext. Published 55 total positions match header. Boundary remains an archival uncertainty.",
                  "Other 3 July messages are marked TS (manual cipher); solved does not imply an Enigma daily key."],
        "LXACA": ["Received 5 July0445, prepared2340: publisher suggests 4 July key, and says 5 July key fails.",
                  "No 4 July Enigma key appears in these key lists; same-date TS solutions impose no Enigma key constraint.",
                  "20 body letters; coherent-looking text alone would be weak evidence."],
        "WEUWY": ["Overview credits the Nr138 puzzle solved26 September2026; keep out of new cracking queue.",
                  "Key-list note that it fails is stale relative to overview. Overview footnote44 corrects indicator to NUG YKS, deriving SPE under B315/NAV/AC BN FM GI JL KO PU QX RZ TV.",
                  "Nr138 is not independently established as ordinary Enigma: puzzle resolution and shared plaintext with Nr140 do not supply a new Nr138 key. Preserve this distinction.",
                  "DXOI- contains one erasure; Nr140 has a different body. Original scans of both inspected."],
        "AWTZK": ["Published-key recovery; author reports9 garbles in49 body letters. Do not silently repair to grammatical text."],
        "ZNLZT": ["Already solved26 September2026; author reports11 garbles in69 body letters. SQNB- includes one unreadable position.",
                  "AWTZK same date, callsign uyo, and explicitly the same published daily key: sharing is evidenced for this pair only."],
        "JBIYH": ["Already solved8 October2026; published start TZU."],
        "FMNGI": ["Already solved20 September2026; Nr285 received transcription has errors. Publisher prefers outgoing Nr205NF, also transcribed on the page.",
                  "Store Nr285 as received; do not replace it silently with Nr205NF."],
    }
    result = []
    overview = text((source / "1941-msg-list.html").read_text())
    keytext = text((source / "e-keys-jun-oct-1941.html").read_text()) + text((source / "e-keys-july-1941.html").read_text())
    for page in ("g-army-messages.html", "g-army-july-1941.html"):
        for head, body in sections(source / page):
            match = re.search(r"of (\d\d)\.(\d\d)\.(\d{4}), Nr\. (\d+), \(([A-Z]{5})\)", head)
            if not match:
                continue
            day, month, year, number, name = match.groups()
            if name not in wanted or int(number) != wanted[name]:
                continue
            before, after = body.split(name + " ", 1)
            lines = []
            for line in (name + " " + after).splitlines():
                if not re.fullmatch(r"[A-Z -]+", line.strip()):
                    break
                lines.append(line.strip())
            grouped = "\n".join(lines)
            ciphertext = normalize(grouped)[5:]
            indicator = re.findall(r"\b([A-Z]{3}) ([A-Z]{3})\b", before)[-1]
            row = dict(id=name, number=int(number), date=f"{year}-{month}-{day}",
                       reception_time=re.search(r"Uhr: (\d{4})", before).group(1),
                       preparation_time=re.search(r"\(?([0-2]\d[0-5]\d)\)?\s+-", before).group(1),
                       callsign=re.search(r"Von: (\S+)", before).group(1),
                       indicator=list(indicator), header=text(before), grouped_including_kenngruppe=grouped,
                       declared_total_in_header=int(re.findall(r"-\s+(\d+)\s+-", before)[-1]),
                       ciphertext=ciphertext, total_positions=5+len(ciphertext), body_positions=len(ciphertext),
                       legible_letters=sum(c != "?" for c in ciphertext),
                       erasure_positions_1based=[i+1 for i,c in enumerate(ciphertext) if c == "?"],
                       transcription_source=BASE+page,
                       original_source=BASE+f"spruch/{day}{month}{year}-{int(number):03d}-in.pdf",
                       original_visually_inspected=True, ambiguities_and_constraints=notes[name],
                       status="unresolved" if name in ("EHSTQ","RXPSB","KLJBO","LXACA") else "published_solved_puzzle" if name=="WEUWY" else "published_key",
                       overview_rows=[line.strip() for line in overview.splitlines() if re.search(rf"\b{name}\b", line)],
                       solved_key_list_rows=[line.strip() for line in keytext.splitlines() if re.search(rf"\b{name}\b", line)])
            if name in keys:
                order, rings, plugs, start = keys[name]
                row["published_key"] = dict(rotors=[ROMAN[x] for x in order], rings=rings, plugboard=plugs, start=start, reflector="B", source=BASE+"e-keys-july-1941.html")
            result.append(row)
    if len(result) != 9 or set(wanted) != {m["id"] for m in result}:
        raise ValueError("inventory incomplete")
    return dict(schema="remaining-1941-inventory/v1", verified_date="2026-10-29",
                scope="Nine non-excluded entries on the supplied stale unbroken list; not all unresolved cipher systems in the entire archive.",
                excluded=list(EXCLUDED), list_source=BASE+"1941-msg-list-unbroken.html",
                source_manifest_sha256=hashlib.sha256((source/"manifest.json").read_bytes()).hexdigest(),
                unresolved=[m["id"] for m in result if m["status"]=="unresolved"], messages=result)


if __name__ == "__main__":
    out = ROOT / "data/remaining-1941/inventory.json"
    out.write_text(json.dumps(build(), indent=2, ensure_ascii=False)+"\n")
    print(out)
