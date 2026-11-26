"""Digests, canonical bytes and import-order determinism (AT-R04, AT-R08, 13.6).

16.5 runs this module twice, under PYTHONHASHSEED 0 and 1; the expected
values below are literal, so both runs must agree with each other and with
the descriptors.
"""

import os
import subprocess
import sys
import unittest

import imperium.battle as B
from tests.battle import oracle
from tests.battle.common import a1
from tests.battle.scenarios import capitulation, collapse
from tests.support.battle_builder import build

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPECTED = {
    "F01-v1-open-standard": ("84b518d2", "c810920d"),
    "F01-v1-open-mirrored": ("91ba7188", "f3ee9fbf"),
    "F01-v1-rough-standard": ("d9ba56e8", "1efef34d"),
    "F01-v1-rough-mirrored": ("4c0814d6", "3f8890dc"),
    "F01-v1-barrier-standard": ("49209f9a", "e42a51c9"),
    "F01-v1-barrier-mirrored": ("8ddb6fef", "fd507838"),
    "F01-v1-open-standard-mount-shortfall": ("9abd67ed", "5e73410b"),
    "F01-v1-defensive-mutual-capitulation": ("32493376", "10590eea"),
}
SCRIPT = """
import sys
first = sys.argv[1]
if first == "codec":
    import imperium.battle.codec
else:
    import imperium.battle.fixtures
import imperium.battle as B
for d in B.DESCRIPTORS:
    s = B.f01_supplied(d.fixture_id) if d.fixture_id in B.supplied_ids() else B.f01_opening(d.variant, d.orientation)
    print(d.fixture_id.token, B.normalized_digest(s), B.digest(s), B.digest(B.decode_bytes(B.canonical_bytes(s))))
try:
    B.decode_bytes(b'{"schema":"imperium.battle-state/1","b":1,"a":2,"c":[1.5]}')
except B.DecodeError as e:
    print(e.code, repr(e.path), e.detail, e.offset)
"""


def fixture_state(d):
    if d.fixture_id in B.supplied_ids():
        return B.f01_supplied(d.fixture_id)
    return B.f01_opening(d.variant, d.orientation)


class DeterminismTests(unittest.TestCase):
    def test_descriptor_digests(self):
        self.assertEqual({d.fixture_id.token for d in B.DESCRIPTORS}, set(EXPECTED))
        for d in B.DESCRIPTORS:
            s = fixture_state(d)
            n, full = EXPECTED[d.fixture_id.token]
            self.assertEqual(B.normalized_digest(s), d.normalized_genesis_digest)
            self.assertEqual(B.digest(s), d.full_genesis_digest)
            self.assertTrue(d.normalized_genesis_digest.startswith(n))
            self.assertTrue(d.full_genesis_digest.startswith(full))

    def test_oracle_bytes(self):
        for d in B.DESCRIPTORS:
            s = fixture_state(d)
            self.assertEqual(B.canonical_bytes(s), oracle.canonical(B.encode_state(s)))
            self.assertEqual(B.digest(s), oracle.sha(oracle.canonical(B.encode_state(s))))

    def test_adversarial_round_trip_stable(self):
        for doc in (a1(), collapse(), capitulation()):
            s = build(doc)
            self.assertEqual(B.canonical_bytes(B.decode_bytes(B.canonical_bytes(s))),
                             B.canonical_bytes(s))
            self.assertEqual(B.digest(build(doc)), B.digest(s))

    def test_error_determinism(self):
        data = b'{"schema":"imperium.battle-state/1","b":1,"a":2}'
        seen = set()
        for _ in range(3):
            with self.assertRaises(B.DecodeError) as cm:
                B.decode_bytes(data)
            e = cm.exception
            seen.add((e.code, e.path, e.detail, e.offset, e.violations))
        self.assertEqual(len(seen), 1)

    def test_at_r04_import_orders_and_hash_seeds(self):
        outputs = []
        for first in ("codec", "fixtures"):
            for seed in ("0", "1"):
                env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": seed}
                result = subprocess.run([sys.executable, "-s", "-W", "error", "-c", SCRIPT, first],
                                        cwd=ROOT, env=env, capture_output=True, text=True,
                                        check=True)
                outputs.append(result.stdout)
        self.assertEqual(len(set(outputs)), 1, outputs)
        lines = outputs[0].splitlines()
        self.assertEqual(len(lines), 9)
        for line in lines[:8]:
            token, n, full, again = line.split()
            self.assertTrue(n.startswith(EXPECTED[token][0]))
            self.assertTrue(full.startswith(EXPECTED[token][1]))
            self.assertEqual(full, again)
