import unittest

import recon


class ReconMaskTests(unittest.TestCase):
    def test_mask_does_not_create_repeated_adjacency(self) -> None:
        self.assertNotIn(("ABC", 2), recon.repeated_ngrams("AB?CAB?C"))

    def test_mask_does_not_create_lag_matches(self) -> None:
        lag_two = next(row for row in recon.autocorrelation("AB?AB") if row[0] == 2)
        self.assertEqual(lag_two[1], 0)


if __name__ == "__main__":
    unittest.main()
