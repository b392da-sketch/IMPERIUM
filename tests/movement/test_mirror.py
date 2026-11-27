"""TA-P4-L02: half-turn invariance of every carrier on the mirrored F01.

Spatial inputs rotate (q,r) -> (10-q,8-r) and directions/facings +3 mod 6;
actor identities and signed turns are preserved. Physical state after the
transform, effort, uses and stage-id sequences must agree; wire bytes and
digests may differ, and each window token binds its own full base.
"""

import json
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from tests.movement.support import MIRRORED, STANDARD, carriers, cjson, window_hash


def rot(cell):
    return [10 - cell[0], 8 - cell[1]]


def mirror_command(doc):
    d = json.loads(json.dumps(doc))
    if "path" in d:
        d["path"] = [rot(c) for c in d["path"]]
    if "destination" in d:
        d["destination"] = rot(d["destination"])
    if "direction" in d:
        d["direction"] = (d["direction"] + 3) % 6
    return d


def physical(state, mirrored):
    out = {}
    for g in state.formations:
        cell, facing = [g.cell.q, g.cell.r], g.facing
        if mirrored:
            cell, facing = rot(cell), (facing + 3) % 6
        out[g.formation.token] = (tuple(cell), facing, g.disposition.name, g.condition)
    return out


CELL_KEYS = ("cell", "origin", "destination")
FACING_KEYS = ("facing", "facing_before")


def unmirror(tree):
    """Rotate every recorded cell and facing of a mirrored ledger back."""
    if type(tree) is list:
        return [unmirror(x) for x in tree]
    if type(tree) is not dict:
        return tree
    out = {}
    for k, v in tree.items():
        if k in CELL_KEYS:
            out[k] = rot(v)
        elif k == "declared":
            out[k] = [rot(c) for c in v]
        elif k in FACING_KEYS:
            out[k] = (v + 3) % 6
        else:
            out[k] = unmirror(v)
    return out


def logical(state, mirrored):
    if state.ledger is None:
        return None
    doc = B.encode_state(state)["ledger"]
    return unmirror(doc) if mirrored else doc


def run(name, fixture, mirrored):
    s = E.BattleSession.open(fixture)
    ids, states = [], []
    for row in carriers()[name]["roots"]:
        command_doc = mirror_command(row["command"]) if mirrored else row["command"]
        base = s.state
        command = E.decode_command(cjson(command_doc))
        r = s.submit(command)
        if type(r) is E.Suspended:
            w = r.root.window
            assert w.window_id == window_hash(B.digest(base), command, w.after)
            decision = dict(row["decision"], window_id=w.window_id)
            r = s.submit(E.decode_command(cjson(decision)))
        assert type(r) is E.Accepted, repr(r)[:300]
        states.append(s.state)
    for line in s.export_audit().split(b"\n")[1:-2]:
        ids.append([e["id"] for e in json.loads(line)["events"]])
    return s, ids, states


class L02Mirror(unittest.TestCase):

    def test_carriers(self):
        for name in carriers():
            with self.subTest(carrier=name):
                a, ids_a, states_a = run(name, STANDARD, False)
                b, ids_b, states_b = run(name, MIRRORED, True)
                self.assertEqual(ids_a, ids_b)
                for sa, sb in zip(states_a, states_b):
                    self.assertEqual(physical(sa, False), physical(sb, True))
                    self.assertEqual(logical(sa, False), logical(sb, True))
                    self.assertEqual(sa.clock, sb.clock)
                    self.assertEqual(type(sa.phase), type(sb.phase))
                self.assertNotEqual(B.digest(a.state), B.digest(b.state))


if __name__ == "__main__":
    unittest.main()
