# Historical keyed messages

`keyed-messages.json` holds the 13 authentic 1941 German Army messages used in
Ostwald and Weierud, "Modern breaking of Enigma ciphertexts" (*Cryptologia*
41(5), 2017). The data comes from the article's
[companion page](https://cryptocellar.org/enigma/enigma-modern-breaking.html),
which gives each message's ciphertext, recovered key and raw plaintext.

`tests/test_historical_messages.py` deciphers every message with
`enigma.EnigmaI` and requires the published raw plaintext letter for letter.
This is the only check in the repository of the machine model against real
traffic. All the other checks use test vectors or keys this repository planted.

Two of the records needed more than transcription:

- **No. 2 of 1 October 1941**: the page prints No. 1's key line, start
  position `DEI` included, and that setting does not decipher the message.
  Under the published wheels, rings and plugs, `ZAQ` is the only one of the
  17,576 start positions that reproduces the published plaintext (24 of 24
  letters); the next best agrees on 10. The record keeps `DEI` as
  `start_position_as_published`.
- **No. 233 of 19 July 1941**: three ciphertext letters are illegible on the
  form. They are kept as `-`. The test steps the machine for each one and
  expects `-` in the plaintext, as the page prints it.

The raw plaintexts are identical to the copies in
`../phase2/held-out-plaintexts.json` and `../phase5/army-plaintext-controls.json`.
The test asserts this for every message those files share with this one.

`scripts/extract_keyed_messages.py PAGE --retrieved YYYY-MM-DD` rebuilds this
file from a saved copy of the page, including the start-position search for
No. 2. The page is not committed; its SHA-256 is recorded in `source`.

Source attribution: Olaf Ostwald and Frode Weierud, CryptoCellar. The site
license is CC BY-NC-SA 4.0 (see `../phase5/README.md`).
