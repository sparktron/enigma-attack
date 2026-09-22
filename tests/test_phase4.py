import copy
import dataclasses
import json
import pathlib
import random
import tempfile
import unittest
from unittest import mock

from enigma import A
from phase1 import ArmyGermanScorer, load_corpus
from phase4 import (
    DEFAULT_CONFIG,
    _split_messages,
    _training_only_baseline,
    _mutate_plugboard,
    initial_state,
    load_config,
    mutate_daily_key,
    mutate_machine,
    run_experiment,
    run_seed,
    score_state,
    state_signature,
)


class Phase4MutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config()
        self.baseline = initial_state(self.config)

    def test_machine_mutations_preserve_required_constraints(self) -> None:
        state = self.baseline
        rng = random.Random(991)
        weights = self.config["optimizer"]["machine_mutation_weights"]
        for _ in range(300):
            state, _ = mutate_machine(state, rng, weights)
            for wiring, notches in state.rotor_wirings.values():
                self.assertEqual(set(wiring), set(A))
                self.assertEqual(len(wiring), 26)
                self.assertEqual(len(notches), 1)
                self.assertIn(notches, A)
            for index, letter in enumerate(state.reflector):
                partner = ord(letter) - 65
                self.assertNotEqual(index, partner)
                self.assertEqual(ord(state.reflector[partner]) - 65, index)

    def test_daily_mutations_preserve_order_rings_and_plugboard(self) -> None:
        state = self.baseline
        rng = random.Random(1234)
        optimizer = self.config["optimizer"]
        expected_rotors = set(self.baseline.rotor_wirings)
        for _ in range(300):
            state, _ = mutate_daily_key(
                state,
                rng,
                optimizer["daily_mutation_weights"],
                optimizer["max_plugboard_pairs"],
            )
            for key in state.daily_keys.values():
                self.assertEqual(set(key.rotors), expected_rotors)
                self.assertEqual(len(key.rings), 3)
                self.assertTrue(set(key.rings).issubset(set(A)))
                letters = "".join(key.plugboard_pairs)
                self.assertEqual(len(letters), len(set(letters)))
                self.assertLessEqual(
                    len(key.plugboard_pairs),
                    optimizer["max_plugboard_pairs"],
                )

    def test_zero_plugboard_capacity_is_safe(self) -> None:
        self.assertEqual(_mutate_plugboard((), random.Random(0), 0), ())
        with self.assertRaises(ValueError):
            _mutate_plugboard(("AB",), random.Random(0), 0)
        updated, _ = mutate_daily_key(
            self.baseline, random.Random(0), {"plugboard_edit": 1.0}, 0
        )
        self.assertTrue(all(not key.plugboard_pairs for key in updated.daily_keys.values()))


class Phase4ExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config()
        self.config["optimizer"]["iterations"] = 20
        self.config["optimizer"]["trace_every"] = 5
        self.messages = load_corpus()
        self.train, self.held_out = _split_messages(self.messages, self.config)
        self.baseline = initial_state(self.config)
        self.scorer = ArmyGermanScorer()

    def test_seed_run_is_deterministic(self) -> None:
        first = run_seed(
            self.config,
            self.baseline,
            self.train,
            self.held_out,
            self.scorer,
            77,
        )
        second = run_seed(
            self.config,
            self.baseline,
            self.train,
            self.held_out,
            self.scorer,
            77,
        )
        first.pop("runtime_seconds")
        second.pop("runtime_seconds")
        self.assertEqual(first, second)

    def test_baseline_selection_excludes_held_out_messages(self) -> None:
        baseline, selection = _training_only_baseline(self.config, self.train, self.scorer)
        changed_holdout = [dataclasses.replace(message, ciphertext="A" * len(message.ciphertext))
                           for message in self.held_out]
        unchanged_train, _ = _split_messages(self.train + changed_holdout, self.config)
        second, _ = _training_only_baseline(self.config, unchanged_train, self.scorer)
        self.assertEqual(state_signature(baseline), state_signature(second))
        selected = {name for date in selection["dates"] for name in date["train_designators"]}
        self.assertTrue(selected.isdisjoint({message.designator for message in self.held_out}))

    def test_held_out_messages_are_not_scored_during_optimization(self) -> None:
        calls: list[tuple[str, ...]] = []

        def recording_score(state, messages, scorer):
            calls.append(tuple(message.designator for message in messages))
            return score_state(state, messages, scorer)

        with mock.patch("phase4.score_state", side_effect=recording_score):
            run_seed(
                self.config,
                self.baseline,
                self.train,
                self.held_out,
                self.scorer,
                88,
            )
        train_names = tuple(message.designator for message in self.train)
        held_out_names = tuple(message.designator for message in self.held_out)
        self.assertTrue(all(call == train_names for call in calls[:-3]))
        self.assertEqual(calls[-3:], [held_out_names, train_names, held_out_names])

    def test_small_experiment_records_raw_reproducibility_data(self) -> None:
        config = copy.deepcopy(self.config)
        config["optimizer"]["seeds"] = [7, 11]
        config["acceptance"]["minimum_passing_seeds"] = 1
        with tempfile.TemporaryDirectory() as directory:
            config_path = pathlib.Path(directory) / "config.json"
            config_path.write_text(
                json.dumps(config, indent=2) + "\n",
                encoding="utf-8",
            )
            artifact = run_experiment(config, config_path, ["--test"])
        self.assertEqual(len(artifact["seed_results"]), 2)
        self.assertIn(artifact["status"], {
            "supported_under_preregistered_metric",
            "refuted_under_preregistered_metric",
        })
        self.assertIn("dirty", artifact["code"])
        self.assertEqual(artifact["environment"]["parallel_workers"], 1)
        self.assertEqual(
            artifact["configuration"]["payload"]["hypothesis"],
            config["hypothesis"],
        )
        self.assertEqual(
            artifact["baseline"]["state_signature"],
            state_signature(self.baseline),
        )


if __name__ == "__main__":
    unittest.main()
