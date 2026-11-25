import json
import unittest

from imperium.events import Event, SCHEMA_VERSION, jsonl, state_digest
from imperium.fixture import Encounter, initial_encounter
from imperium.profiles import PROFILES


class EventTests(unittest.TestCase):
    def test_state_digest_ignores_storage_order(self):
        original = initial_encounter(PROFILES["F6"])
        original.contacts.update(((2, 7), (3, 8)))
        reordered = Encounter(tuple(reversed(original.formations)), set(reversed(sorted(original.contacts))))
        expected = state_digest(original, round_state={"side": 0, "ordinal": 1})
        self.assertEqual(state_digest(reordered, round_state={"ordinal": 1, "side": 0}), expected)
        self.assertNotEqual(state_digest(reordered, round_state={"ordinal": 2, "side": 0}), expected)
        original.formations[0].forced_stop = True
        self.assertNotEqual(state_digest(original, round_state={"side": 0, "ordinal": 1}), expected)

    def test_jsonl_canonical_keys_preserve_event_order(self):
        state = state_digest(initial_encounter(PROFILES["F6"]), round_state={})

        def event(stage, data):
            return Event("F6", 20000, 1, 1, stage, "test", state, state, data=data)

        first = event(1, {"b": 1, "a": {"d": 2, "c": 3}})
        reordered = event(1, {"a": {"c": 3, "d": 2}, "b": 1})
        self.assertEqual(jsonl([first]), jsonl([reordered]))
        encoded = jsonl([first, event(2, {})])
        rows = [json.loads(line) for line in encoded.splitlines()]
        self.assertEqual([row["stage_id"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["schema_version"], SCHEMA_VERSION)
        self.assertTrue(encoded.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
