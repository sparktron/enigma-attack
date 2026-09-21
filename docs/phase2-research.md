# Research: Which evidence should drive Batch C clustering and crib generation?

**Date:** 2026-09-19 · **Decision this feeds:** Phase 2 network grouping,
archive-search priorities, and crib ranking · **Out of scope:** claiming a break,
assuming all five messages share a key, or treating uncited vocabulary as known
plaintext.

## Facts

- CryptoCellar's challenge page, updated 27 July 2026, presents five unknown
  messages and says their operators, comments, and unusually low frequencies
  differ from the wider 1941 Army collection. It also says a different machine
  remains possible. — [Ultimate Enigma Challenge](https://www.cryptocellar.org/bgac/ultimate-enigma.html)
- CryptoCellar's status page dated 16 September 2026 lists only BYQMZ, FKQLZ,
  and XFEDT as still-unbroken Batch C messages. It does not state what happened
  to QTXMA or SZAEJ. — [1941 unbroken list](https://www.cryptocellar.org/bgac/1941-msg-list-unbroken.html)
- The message forms link BYQMZ to recipient `ugn`; the next included message,
  FKQLZ, carries `de ugn`. Frequencies 323 kHz and 716 kHz each recur across
  different operators. — [German Army messages](https://www.cryptocellar.org/bgac/g-army-messages.html), updated 1 August 2026
- A counterpart message found in the German Bundesarchiv enabled the July 2026
  break of ALQFI. The source describes it as a likely original/retransmission
  relationship and publishes raw plaintext containing X separators, spelled
  numbers, a repeated place name, and `Q` for `CH`. — [German Army messages](https://www.cryptocellar.org/bgac/g-army-messages.html), updated 1 August 2026
- Authentic Army decrypts attest tactical observation and command formulae as
  well as raw X and Q/CH conventions. — [1930 test message](https://www.cryptocellar.org/enigma/e-message-1930.html); [1938 Army message](https://www.cryptocellar.org/enigma/tbombe.html)

## Inference

- The operator runs, short time gaps, repeated frequencies, sequential numbers,
  and the `ugn` recipient-to-sender transition justify one traffic-analysis
  cluster. They do not prove one cipher, machine, daily key, or sender.
- Counterpart forms and retransmissions should be searched before inventing
  long cribs. The ALQFI result is direct evidence that this archival strategy can
  outperform ciphertext-only guessing in this collection.
- QTXMA and SZAEJ's omission from the later status list is a source discrepancy,
  not evidence that either has been solved.

## Speculation

- CryptoCellar suggests an Ordnungspolizei network as one possibility but says
  no confirming or refuting information was available. This hypothesis should
  remain a search term, not a cluster label or scoring boost.
- Clear operator remarks such as `Spruchkopf wiederholen` may suggest procedural
  vocabulary, but they do not establish that those words occur in ciphertext.

## Unresolved

- Why QTXMA and SZAEJ disappeared from the 16 September 2026 unbroken list.
- The meanings of the Batch C Q-code remarks and identities of the callsigns.
- Whether all five messages are Enigma, another machine, or a mixed set.
- Whether counterpart station copies, logs, or cleartext survive for callsign
  `ugn`, 323 kHz, 568 kHz, or 716 kHz traffic on 29–30 September 1941.

## Recommendation

Use a single metadata graph for archive discovery, but preserve per-message
cipher hypotheses. Rank only source-backed plaintext snippets by default, then
apply Enigma's no-self-encryption rule as a necessary precheck before expensive
Bombe work. Keep metadata-derived and generic cribs disabled unless explicitly
requested.

Main risk: authentic plaintext from other Army networks may be linguistically
plausible but irrelevant to this unusual network.

Strongest case against: if the traffic is not Enigma, Bombe-compatible cribs add
no useful evidence and may distract from Phase 5 model selection.

Reverse this if: a counterpart form, cleartext copy, or reliable network
identification supplies message-specific plaintext or demonstrates a non-Enigma
system.
