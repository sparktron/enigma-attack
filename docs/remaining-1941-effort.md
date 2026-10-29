# Remaining 1941 messages: new effort, 29 October 2026

## Question and scope

Which non-excluded entries on the supplied unbroken list are still unresolved,
and does a calibrated local RXPSB pilot justify a larger search?
BYQMZ, FKQLZ and XFEDT are excluded. Their historical configurations, artifacts,
and conclusions are preserved. This effort does not resume their searches.

Repository orientation: baseline `e96406eef8a2d70d63dd45b6137e3c749a7a0ad3`,
initial clean `master`, five commits behind recorded `origin/master`, zero
unpushed commits. Work branch `codex/remaining-1941-pilot`. No root AGENTS.md
exists on disk; the user's supplied instructions govern code navigation.
Read STATUS, ATTACK_PLAN, Phase 1 experiment history and lessons; navigated
simulator, fast kernel, scorer, reference/batched climbs and independent
verifier through jCodemunch. Markdown is unsupported by this jCodemunch index,
so documentation was read directly. Existing engine tests cover those reused
modules; new inventory/erasure/control-gate tests cover this runner. No shared
interface or cross-repository contract changes.

## Observed source facts

Snapshot date: **2026-10-29**. Raw HTML and ten original intercept PDFs,
URLs, UTC retrieval times and SHA-256 hashes are in
`data/remaining-1941/sources/manifest.json`. Each of the nine candidate originals
was rendered with system `/usr/bin/pdftoppm` and visually inspected. The bundled
Poppler required unavailable GLIBC_2.38, so system Poppler was used. Inspection
does not certify that the original radio reception was error-free.

The supplied [unbroken list](https://www.cryptocellar.org/bgac/1941-msg-list-unbroken.html)
is dated 19 September 2026. It lists 12 entries; removing the three exclusions
leaves nine entries to audit, **not nine currently unbroken messages**.
The [full overview](https://www.cryptocellar.org/bgac/1941-msg-list.html),
[June–October keys](https://www.cryptocellar.org/bgac/e-keys-jun-oct-1941.html),
[July keys](https://www.cryptocellar.org/bgac/e-keys-july-1941.html),
[June transcription](https://www.cryptocellar.org/bgac/g-army-messages.html), and
[July transcription](https://www.cryptocellar.org/bgac/g-army-july-1941.html)
were checked together. The offline builder records the exact matching overview
and key-list rows alongside each ciphertext.

Counted total/body positions (including unreadable positions):

- EHSTQ: **57/52**, no printed erasures; unresolved. Original red serial3;
  HTML header's Nr45 conflicts with it.
- RXPSB: **112/107**, erasures at body18 and104; **105 readable letters**;
  unresolved. The original header says114; the stale list says104/99. There
  are22 complete five-letter groups and a final ED, including the Kenngruppe.
  Neither the109-letter header subtraction nor99-letter list body is the
  transcribed body. Keep the unexplained two-position header discrepancy.
- KLJBO: **55/50**, erasures34,41,45,47; unresolved. Additional trailing writing
  on the scan might be an operator mark; boundary uncertainty remains.
- LXACA: **25/20**, no printed erasures; unresolved. Received5 July0445,
  prepared2340, probably4 July according to the publisher.
- WEUWY Nr138: **53/48**, erasure15. Overview credits the puzzle solved
  26 September2026; the old key-list failure note is stale. This is not a
  claim of independently reproducing an ordinary Enigma break for Nr138.
  Overview footnote44 corrects the indicator to NUG YKS, giving SPE under
  the9 July key, and relates its plaintext to Nr140.
- AWTZK: **54/49**, published solved; ZNLZT: **74/69**, published solved,
  erasure30. Both explicitly share B143, EXS, AO BF CQ DH EW GJ KX NU PY RT.
  Starts ERT and NML, indicators DUJ GEH and ZZD LRD.
- JBIYH: **60/55**, published solved8 October2026, B541/EXT,
  AU BI CY ET FL HK MP NR OX QV, startTZU, indicatorBSB NTK.
- FMNGI Nr285: **63/58**, published solved20 September2026, B243/UHP,
  AH DJ EM FO GI KP LU NS QW TX, startTOG, indicatorAFL BSA. The publisher
  prefers the less garbled outgoing Nr205NF; retain Nr285's received body.

All grouped bodies, normalized positional ciphertext, dates, reception and
preparation times, indicators, callsigns, sources, ambiguities and constraints
are in `data/remaining-1941/inventory.json`. `?` consumes a keystroke; it is
never deleted. These counts describe the transcription, not the unknown
error-free transmitted length. Four entries in this audited subset remain
unresolved. Other unresolved manual-cipher/archive entries are outside this
inventory's scope; this is not a census of every1941 intercept.

The [AWTZK/ZNLZT account](https://www.cryptocellar.org/bgac/the-awtzk-znlzt-breaks.html)
reports9 and11 garbles respectively. The
[FMNGI account](https://www.cryptocellar.org/bgac/the-fmngi-break.html) explains
why originating copies and sourced cribs can matter more than blind scoring.
Reported garble counts are the publisher's findings, not independently counted
against repaired plaintext here.

## Interpretation and target choice (inference)

RXPSB is the first target because107 body positions provide more statistical
evidence than EHSTQ52, KLJBO50 and LXACA20. This is a relative priority, not
a quantified probability of recovery. ZNLZT is already solved and is useful
as a verifier control, not as a new cracking target. RXPSB's two erasures and
unresolved length discrepancy reduce confidence; a source-supported crib or
originating copy could change the priority.

PLDRV Nr51 has RXPSB's reception date, callsign5l8 and AK→Ib route. But the
publisher explicitly says PLDRV was encrypted27 June, with B352/RGP/
AV BG CH EN FU KO MS PX RY TW. That key is a cheap **previous-day transfer
hypothesis**, not a28 June daily-key constraint. RXPSB's1020 header and1126
reception do not suggest midnight rollover. No28 June key appears in either
published list. Same-date solved TS traffic does not determine an Enigma key.
LXACA's4 July suggestion is useful historical context, but no4 July Enigma
key is supplied by these lists. No companion confirmation is required.

Non-transferring assumptions from the previous target:167-letter recovery
power, the September network/wiring doubts, the old target's indicators and
partitions, FKQLZ/XFEDT confirmation, high-IC constructed plaintext behavior,
and sweep-specific score thresholds or null odds. None is imported here.

## Preregistered experiment: remaining-1941-pilot-v1

Written before benchmark outcomes or historical decryption. Exact configuration:
`experiments/remaining-1941-pilot-v1/config.json`; entry point:
`python3 remaining1941_pilot.py`. Preparation is committed before this command.
The runner records that exact commit, branch, dirty state, imported-code hashes,
input/config hashes, Python/numpy/platform and worker count to `prerun.json`
before checks and controls. Baseline repository revision is recorded above.
Local single CPU process, no GPU, no paid compute, no external communications.
Budget: **1200 seconds wall** (at most one task/CPU,20 CPU-minutes), checks
between bounded units; fixed-unit overrun possible. Finite counts also cap work.

Falsifiable hypothesis: E first-plug restarts recover both exact plugboard and
all readable plaintext on at least18/24 random ten-pair keys, with true
mechanical settings supplied, for107-position Army plaintexts masked at18/104.
Fewer than18 refutes it. Compare paired clean and masked controls against the
existing identity-start IC→n-gram baseline. This measures **conditional
plugboard-stage power**, not full-search sensitivity.

Four windows from two authentic published raw plaintexts, including spelling
and operator errors, are fixed in config. Windows overlap:24 keys are not24
independent plaintexts. No invented high-IC plaintext, no tuning after results.
Seeds2026102901(parity),2026102902(plants),2026102903(pilot); per-draw seed
offsets are explicit in the runner. Parallelism is one. Reproduction requires
the recorded Python/numpy/scorer and floating-point behavior as well as seeds.

Preflight checks fast/reference and independent wheel paths, including unknown
positions and double stepping. Two masked E climbs must match the reference
climber's board and evaluation count. Four planted all-start controls at the
fixed daily-key hypothesis must rank the correct start first among all17576.
At least4/24 masked E keys must recover for the small feasibility pilot to run;
this deliberately low gate allows throughput measurement even if the main
75% hypothesis fails. Any preflight failure or budget expiry in controls
blocks historical work. A failed mandatory control is never waived.

Historical pilot, only after those gates:

1. Reproduce published-key AWTZK, ZNLZT, JBIYH, FMNGI raw decrypts and indicators.
   These remain existing published solutions, never new breaks.
2. RXPSB: try the27 June published key at **all17576 body starts**, retaining
   every score and checking the header-derived start separately. This spans
   one daily key only and does not establish it was used on RXPSB.
3. RXPSB: **240 mechanical points**, four independently sampled absolute
   ring/start settings per each of60 I–V orders, UKW-B, ten-pair maximum,
   E-start IC→n-gram climb. Uniform seeded sampling, no outcome-based tuning.
   Save every setting, resulting plugboard/plaintext, score, evaluations and
   independent/indicator checks in `raw.jsonl`. Top10 retained in summary.

Raw mechanical denominator is60×26^6=18,534,946,560 absolute ring/start
points; it includes equivalent representations. Sampling240 points is not
an exhaustive daily-key search or a uniform sample of distinct encryptions.
Plugboard optimization is heuristic, never counted as exhaustive coverage.

Acceptance: independently re-encrypt the complete raw plaintext to **all
legible ciphertext** with stepping through erasures; independently reproduce
the decrypt; check indicators; require coherent substantial military German.
Unknown source positions remain unverifiable. Any correction to a legible
source character needs an explicit independently justified error ledger.
Reciprocity alone is necessary but insufficient: every wrong key also roundtrips.
A score cannot accept a solution, and no key-sharing companion is assumed.
All proposed novel solutions require manual linguistic/source review.

Stopping/next decision: no adaptive restart or enlarged search in this run.
Larger search requires both at least18/24 masked conditional recoveries and
new daily-key/crib constraints **or** a new measured full-pipeline power/cost
study. The pilot alone cannot justify expensive blind expansion. A failed
heuristic run never proves undecryptability. Results go below and into STATUS
and Phase1 history, with observations separate from inference.

## Results

Not run at preparation commit. Configuration and raw evidence paths are fixed;
the completed run will be appended without changing this preregistration.
