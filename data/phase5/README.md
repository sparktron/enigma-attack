# Phase 5 conservation-gate controls

`army-plaintext-controls.json` holds known German Army plaintexts published at
CryptoCellar's [modern breaking page](https://cryptocellar.org/enigma/enigma-modern-breaking.html).
Only whitespace was removed; the letters are unchanged.

The Phase 5 conservation gate shuffles each one into a true transposition and
requires the gate to find it compatible with Army plaintext monograms. This is a
positive control in the Phase 6/7 sense: it fails loudly rather than silently, and
an uncalibrated gate records its exclusions as unusable instead of applying them.

The reference distribution the gate tests against is derived at runtime from
`../phase7/BigramFrequency1941.txt`, so the published counts have one source of
truth in this repository.

Source attribution: Geoff Sullivan and Frode Weierud, CryptoCellar. The
[site license](https://cryptocellar.org/bgac/index.html) is CC BY-NC-SA 4.0.
Keep that restriction in mind when redistributing the data.
