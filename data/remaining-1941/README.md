# Verified inventory and local pilot

Sources fetched29 October2026. `sources/manifest.json` pins the original HTML
and intercept PDF bytes, URLs and retrieval times. Original source copyrights
and per-page licences apply; this archive does not grant a new licence.
No external publication or communication was made. Initial download used an
inline Python loop equivalent to `scripts/fetch_remaining1941_sources.py`;
the committed script refuses to overwrite this snapshot.

Rebuild offline: `python3 remaining1941_inventory.py`.
Run the preregistered pilot: `python3 remaining1941_pilot.py` (refuses to
overwrite its output directory). Exact command, assumptions and acceptance
criteria: `docs/remaining-1941-effort.md`.

`inventory.json` covers the nine non-excluded entries on the stale unbroken
list, retains solved entries with their status, and leaves four unresolved.
RXPSB is112 total/107 body positions, not its header114 or stale list104/99.
`?` represents one unreadable position, not whitespace or a skipped keypress.
The original scans were inspected; uncertain readings and boundary questions
remain explicit. The original transmitted lengths are unknown when the form
and its count disagree.

Pilot raw outputs are durable under `pilot-v1/`: pre-run provenance, every
control and sampled setting, complete all-start score vectors, and summary.
None of the old September target data or conclusions is changed.
