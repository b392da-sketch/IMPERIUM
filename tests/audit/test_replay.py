"""TA-H01–H02: authoritative replay and the assurance levels (contract rev 0.3
sections 8.4 and 9, ER06)."""

import json
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.audit import AuditError, verify
from tests.audit.support import (
    CARRIERS, RUN0, STANDARD, WALK_SEEDS, chained, cjson, final_chain, journals, oracles, refold,
    sha, trees, walk,
)


class Replay(unittest.TestCase):

    def test_h01_goldens(self):
        for name in CARRIERS:
            sealed, prefix = journals(name)
            with self.subTest(carrier=name):
                self.assertEqual(E.replay(sealed), verify(sealed))
                self.assertEqual(E.replay(sealed, expected_chain=final_chain(sealed)),
                                 verify(sealed))
                # Unsealed only with the explicit prefix opt-in.
                with self.assertRaises(AuditError) as cm:
                    E.replay(prefix)
                self.assertEqual(cm.exception.code, "AU16")
                # ER06: replay-only unsealed positive, and an anchored unsealed positive.
                r = E.replay(prefix, require_sealed=False)
                self.assertEqual((r.sealed, r), (False, verify(prefix, require_sealed=False)))
                a = E.replay(prefix, require_sealed=False, expected_chain=final_chain(prefix))
                self.assertEqual(a, r)
                with self.assertRaises(AuditError) as cm:
                    E.replay(prefix, require_sealed=False, expected_chain=final_chain(sealed))
                self.assertEqual(cm.exception.code, "AU17")

    def test_h01_walks(self):
        for seed in WALK_SEEDS:
            s = walk(seed)[0]
            for seal in (True, False):
                data = s.export_audit(seal=seal)
                self.assertEqual(E.replay(data, require_sealed=seal),
                                 verify(data, require_sealed=seal), seed)

    def test_h01_short_prefixes(self):
        sealed = journals("G4")[0]
        lines = sealed.split(b"\n")[:-1]
        for n in (1, 2, 5, 13, 26):
            data = b"".join(l + b"\n" for l in lines[:n])
            self.assertEqual(E.replay(data, require_sealed=False).roots, n - 1)

    def test_h02_safe_latch_witness(self):
        o = oracles()["h02_state_witness"]
        s = E.BattleSession.open(STANDARD, RUN0)
        s.submit(E.OpenBattle())
        original = s.export_audit()
        self.assertEqual(B.digest(s.state), o["p2_digest"])
        ts = trees(original)
        ev = ts[1]["events"][1]
        self.assertEqual(ev["stage"], "OPEN_ROUND")
        ledger = ev["effects"][0]
        self.assertEqual(ledger["path"], "/ledger")
        (row,) = [f for f in ledger["new"]["formations"] if f["formation"] == "S0.C1"]
        self.assertIs(row["safe_latch"], True)
        row["safe_latch"] = False
        genesis = json.loads(B.canonical_bytes(
            B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)))
        final = refold(genesis, ts[1]["events"])[-1]
        alternate = sha(cjson(final))
        self.assertEqual(alternate, o["p1_valid_alternate_digest"])
        self.assertEqual(B.digest(B.decode_bytes(cjson(final))), alternate)  # P1 accepts it
        ts[1]["current"] = alternate
        ts[2]["final"] = alternate
        forged = chained(ts)
        # L1 and L2 accept, reporting the alternate digest.
        self.assertEqual(verify(forged, require_sealed=False).final, alternate)
        self.assertEqual(verify(forged).final, alternate)
        # L3: the trusted original chain fails AU17.
        with self.assertRaises(AuditError) as cm:
            verify(forged, expected_chain=final_chain(original))
        self.assertEqual((cm.exception.code, cm.exception.line), ("AU17", 3))
        # L4: authoritative replay fails RP01 at the root.
        with self.assertRaises(E.ReplayError) as cm:
            E.replay(forged)
        self.assertEqual((cm.exception.code, cm.exception.line), ("RP01", 2))


if __name__ == "__main__":
    unittest.main()
