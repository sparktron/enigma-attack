# Phase 3 research: documented Enigma variants

Research date: 2026-09-20

## Question and boundary

Which documented three-wheel Enigma-family configurations are historically
plausible enough to test before attempting free-form rotor recovery?

This phase includes only configurations whose wiring and stepping can be stated
from inspected sources and represented without silently substituting another
machine. It does not cover four-wheel M4 traffic, undocumented rewiring,
moving-reflector/geared machines, or a complete rings-and-plugboard search.

## Sources inspected

- David Hamer, Geoff Sullivan, and Frode Weierud,
  [Enigma Variations: An Extended Family of Machines](https://www.cryptocellar.org/pubs/enigvar.pdf)
  (accessed 2026-09-20). This is the primary source for Railway Enigma, Swiss K,
  Enigma T, and the mechanical distinctions of Abwehr machines.
- David Hamer,
  [Enigma Rotor Wiring](https://enigmamuseum.com/rotwirg.htm)
  (accessed 2026-09-20). This supplies a compact independent table for service
  rotors I-VIII and wide reflectors A-C.
- Py-Enigma,
  [Reference](https://py-enigma.readthedocs.io/en/latest/reference.html)
  (accessed 2026-09-20). This independently identifies VI-VIII with the
  Kriegsmarine M3/M4 family and documents the standard rotor/reflector catalog.

The executable transcription is [variants.json](../variants.json). Every
profile cites the catalog source identifiers that support it.

## Established facts

- Standard service rotors VI-VIII have two turnovers, unlike I-V. A simulator
  that stores only one notch cannot faithfully screen M3 configurations.
- Railway Enigma is a commercial-derived three-wheel machine with its own
  rotors, QWERTZ entry wheel, settable fixed reflector, and no plugboard. The
  cited paper associates it with German railway traffic in eastern Europe,
  Russia, and the Balkans.
- The cited Swiss K wiring has a QWERTZ entry wheel, settable reflector, and no
  plugboard. The Swiss Army changed stepping in 1941 so the right wheel stayed
  fixed, the middle wheel became fast, and the slow wheel and reflector retained
  turnover behavior. The paper says Swiss Air Force and diplomatic machines
  apparently remained unmodified.
- Enigma T/Tirpitz is mechanically describable, but the cited paper says it
  appears never to have been used operationally. Its intended Japanese naval
  destination is also a poor match for this corpus.
- Abwehr 11-15-17 machines used a moving reflector and cyclometric/geared
  stepping. Modeling them with ordinary pawl stepping would test a different
  machine, so Phase 3 records rather than approximates them.
- Four-wheel M4 requires a fourth wheel and thin reflectors. It is outside this
  phase's declared three-wheel boundary.

## Inferences used by the runner

- Standard service Enigma with UKW B remains the strongest historical prior
  because it matches the corpus's Army-style clear Grundstellung and encrypted
  message-key framing.
- UKW A/C, M3, Railway, and Swiss profiles are useful bounded controls: they can
  reveal whether documented wiring families produce an unusually strong score.
  For M3, Railway, and Swiss K, however, applying the corpus's Army indicator
  convention is explicitly a mechanical comparison, not a reconstruction of
  their operating procedure.
- Historical prior and language score are kept as separate fields. The runner
  does not blend them into an unexplained aggregate rank.
- Enigma T is executable for auditability but disabled by default because the
  contrary historical evidence is stronger than the case for including it.

## What remains uncertain

- The traffic's real network, date, reflector choice, ring settings, and
  plugboard are not independently authenticated.
- Commercial-family indicator procedures are not reconstructed here.
- No independent published ciphertext vector was found for each alternate
  profile during this research pass. Their wirings are source-backed, while
  engine behavior is checked through standard vectors, structural validation,
  stepping tests, and reciprocity.
- A weak smoke result cannot exclude a profile: the default run fixes rings to
  AAA, reflector position to A, and the plugboard to empty.

## Recommendation

Run the documented-variant smoke comparison before any arbitrary wiring search,
but treat it as triage only. Promote a result only if it has both a substantial
score advantage and independent plaintext or traffic-procedure confirmation.
If no profile clears that bar, retain the Phase 3 artifact as a bounded negative
record and move to the next planned hypothesis without claiming the documented
families were exhaustively excluded.
