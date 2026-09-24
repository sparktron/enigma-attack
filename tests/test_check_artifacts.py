import json
import unittest

import check_artifacts


class ResolveTests(unittest.TestCase):
    def test_plain_and_nested_keys(self) -> None:
        document = {"a": 1, "b": {"c": 2}}
        self.assertEqual(dict(check_artifacts.resolve(document, "a")), {"a": 1})
        self.assertEqual(dict(check_artifacts.resolve(document, "b.c")), {"b.c": 2})

    def test_star_expands_every_key(self) -> None:
        document = {"delta": {"train": 1.0, "held_out": -2.0}}
        self.assertEqual(
            dict(check_artifacts.resolve(document, "delta.*")),
            {"delta.held_out": -2.0, "delta.train": 1.0},
        )

    def test_list_wildcard_indexes_elements(self) -> None:
        document = {"seeds": [{"id": 1}, {"id": 2}]}
        self.assertEqual(
            dict(check_artifacts.resolve(document, "seeds[].id")),
            {"seeds[0].id": 1, "seeds[1].id": 2},
        )

    def test_absent_path_yields_missing(self) -> None:
        values = dict(check_artifacts.resolve({"a": 1}, "b.c"))
        self.assertIs(values["b"], check_artifacts.MISSING)


class CompareTests(unittest.TestCase):
    def test_identical_documents_agree(self) -> None:
        doc = {"status": "refuted", "delta": {"held_out": -0.5}}
        values, shapes, unmatched = compare_both(doc, doc, ["status", "delta.*"])
        self.assertEqual((values, shapes, unmatched), ([], [], []))

    def test_changed_value_is_a_value_difference(self) -> None:
        values, shapes, _ = compare_both(
            {"status": "refuted"}, {"status": "supported"}, ["status"]
        )
        self.assertEqual(len(values), 1)
        self.assertEqual(shapes, [])

    def test_added_key_is_a_shape_difference_only(self) -> None:
        values, shapes, _ = compare_both(
            {"delta": {"held_out": -0.5}},
            {"delta": {"held_out": -0.5, "training": 0.6}},
            ["delta.*"],
        )
        self.assertEqual(values, [])
        self.assertEqual(len(shapes), 1)

    def test_path_matching_nothing_is_reported_separately(self) -> None:
        # The one way an allowlist fails open: a typo checks nothing silently.
        values, shapes, unmatched = compare_both({"a": 1}, {"a": 1}, ["typo.path"])
        self.assertEqual((values, shapes), ([], []))
        self.assertEqual(unmatched, ["typo.path"])


class ClaimsFileTests(unittest.TestCase):
    def test_every_declared_artifact_exists_and_declares_paths(self) -> None:
        claims = check_artifacts.load_claims(check_artifacts.DEFAULT_CLAIMS)
        self.assertTrue(claims["artifacts"])
        for name, entry in claims["artifacts"].items():
            with self.subTest(artifact=name):
                self.assertTrue((check_artifacts.ROOT / name).exists())
                self.assertTrue(entry["claim_paths"])
                self.assertTrue(entry["runner"])

    def test_claim_paths_are_well_formed(self) -> None:
        claims = check_artifacts.load_claims(check_artifacts.DEFAULT_CLAIMS)
        for name, entry in claims["artifacts"].items():
            for claim in entry["claim_paths"]:
                with self.subTest(artifact=name, claim=claim):
                    self.assertFalse(claim.startswith("."))
                    self.assertFalse(claim.endswith("."))
                    self.assertNotIn("..", claim)
                    for segment in claim.split("."):
                        self.assertTrue(segment)
                        self.assertTrue(
                            segment == "*" or not segment.startswith("*"),
                            "'*' matches a whole object and takes no prefix",
                        )

    # Whether each claim path still matches a real field is checked by
    # `check_artifacts.py drift`, which compares against freshly regenerated
    # output. Asserting it here against the committed copies would turn an
    # intentional shape change into a unit-test failure, which is the
    # behaviour the drift check deliberately reports as a warning instead.


def compare_both(a, b, paths):
    return check_artifacts.compare(a, b, paths)


if __name__ == "__main__":
    unittest.main()
