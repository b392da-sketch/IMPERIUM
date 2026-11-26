"""Shared literal helpers for the P1 acceptance suite.

Helpers here write literal document fragments that the test supplies;
they never derive a value that a clause checks.
"""

import copy
import json
import unittest

import imperium.battle as B
from tests.battle import oracle
from tests.support.battle_builder import as_adversarial, build, opening_document

ORDER = sorted(f"{s}.{p}" for s in ("S0", "S1") for p in ("H1", "H2", "H3", "H4", "H5", "H6", "L1", "C1"))


def fi(fid):
    """Index of a formation in roster order (tokens sorted)."""
    return ORDER.index(fid)


def canon(tree):
    return oracle.canonical(tree)


def hx(q, r):
    return [q, r]


def leg(o, d, facing, mode="FOOT"):
    return {"origin": list(o), "destination": list(d), "facing": facing, "mode": mode}


def move(declared, legs, end="COMPLETED"):
    return {"kind": "Move", "declared": [list(c) for c in declared], "legs": legs, "end": end}


def withdraw(o, d, facing, mode="FOOT"):
    return {"kind": "Withdraw", "leg": leg(o, d, facing, mode)}


def group_step(o, d, facing, mode="FOOT"):
    return {"kind": "GroupStep", "leg": leg(o, d, facing, mode)}


def group_pivot(before, turn):
    return {"kind": "GroupPivot", "facing_before": before, "turn": turn}


def pivot(before, turn, steps):
    return {"kind": "Pivot", "facing_before": before, "turn": turn, "steps": steps}


def assault(target, o, t, facing, mode="FOOT", outcome="CONTACT"):
    return {"kind": "Assault", "target": target, "origin": list(o), "target_cell": list(t),
            "facing": facing, "mode": mode, "outcome": outcome}


def missile(target, o, t, facing):
    return {"kind": "Missile", "target": target, "origin": list(o), "target_cell": list(t),
            "facing": facing}


def simple(kind, **fields):
    out = {"kind": kind}
    out.update(fields)
    return out


def use(side, kind, members, work, group=None):
    return {"side": side, "kind": kind, "group": group, "members": list(members), "work": list(work)}


def individual(side, member, work):
    return use(side, "INDIVIDUAL", [member], [work])


def fround(fid, opened=True, response=None, attempted=False, safe=False, incoming=False,
           since=None, exerted=False, displaced=False):
    return {
        "formation": fid, "opened_eligible": opened, "response": response,
        "displacement_attempted": attempted, "safe_latch": safe, "incoming": incoming,
        "incoming_since_rally": incoming if since is None else since, "exerted": exerted,
        "displaced": displaced,
    }


def response(kind, target):
    return {"kind": kind, "target": target}


def a1(variant="OPEN", label="A1", orientation="STANDARD"):
    """Catalogue A1: adversarial open-standard snapshot awaiting S0 in round 1."""
    d = as_adversarial(opening_document(variant, orientation), label)
    d["phase"] = {"kind": "AwaitingPrincipal", "side": "S0"}
    d["ledger"] = {"uses": [], "formations": [fround(f) for f in ORDER]}
    return d


def f(doc, fid):
    return doc["formations"][fi(fid)]


def fr(doc, fid):
    return doc["ledger"]["formations"][fi(fid)]


def place(doc, fid, cell, facing=None, disposition=None):
    rec = f(doc, fid)
    rec["cell"] = list(cell)
    if facing is not None:
        rec["facing"] = facing
    if disposition is not None:
        rec["disposition"] = disposition
    return doc


def cond(doc, fid, c=0, m=0, fat=0, e=0):
    f(doc, fid)["condition"] = {"cohesion": c, "morale": m, "fatigue": fat, "exertion": e}
    return doc


def lot_index(doc, lot):
    for i, l in enumerate(doc["personnel"]):
        if l["lot"] == lot:
            return i
    raise KeyError(lot)


def plot(lot, lineage, count, status, place_, custodian, captured=None, origin=None):
    return {"lot": lot, "lineage": lineage, "count": count, "status": status,
            "captured": captured, "place": place_, "custodian": custodian, "origin": origin}


def in_formation(fid):
    return {"kind": "InFormation", "formation": fid}


def on_cell(q, r):
    return {"kind": "OnCell", "cell": [q, r]}


def at_exit(side):
    return {"kind": "AtExit", "side": side}


def set_lots(doc, lineage, lots):
    """Replace every personnel lot of ``lineage`` with the given literal lots."""
    others = [l for l in doc["personnel"] if l["lineage"] != lineage]
    doc["personnel"] = sorted(others + lots, key=lambda l: l["lot"])
    return doc


def set_asset_place(doc, fid, assignment, place_, custodian, custody, recovery):
    for coll in ("mounts", "ammunition"):
        for rec in doc[coll]:
            if rec["formation"] == fid:
                rec.update(assignment=assignment, place=copy.deepcopy(place_),
                           custodian=custodian, custody=custody, recovery=recovery)
    return doc


def account(doc, fid):
    for a in doc["ammunition"]:
        if a["formation"] == fid:
            return a
    raise KeyError(fid)


def mount_lots(doc, fid):
    return [m for m in doc["mounts"] if m["formation"] == fid]


def terminal(reason, result, winner, defeat, point, charged, objective, postures, viable,
             onmap, exit_):
    return {"kind": "Terminal", "record": {
        "reason": reason, "result": result, "winner": winner, "defeat": list(defeat),
        "point": point, "charged_rounds": charged, "objective": objective,
        "postures": list(postures), "viable": list(viable), "onmap_available": list(onmap),
        "exit_available": list(exit_)}}


def unheld():
    return {"kind": "UNHELD", "side": None}


class BattleCase(unittest.TestCase):
    """Assertions for both channels (14.0)."""

    def accept(self, doc):
        state = build(doc)
        self.assertEqual(B.canonical_bytes(state), canon(doc))
        again = B.decode_state(B.encode_state(state))
        self.assertEqual(again, state)
        self.assertEqual(B.validate_state(state), ())
        return state

    def violations(self, doc):
        with self.assertRaises(B.DecodeError) as cm:
            build(doc)
        self.assertEqual(cm.exception.code, "CLAUSE", msg=str(cm.exception))
        return cm.exception.violations

    def reject(self, doc, clause):
        violations = self.violations(doc)
        clauses = [v.clause for v in violations]
        self.assertIn(clause, clauses, msg=f"{clause} not in {violations}")
        return violations

    def decode_code(self, doc, code, path=None):
        with self.assertRaises(B.DecodeError) as cm:
            build(doc)
        self.assertEqual(cm.exception.code, code, msg=str(cm.exception))
        if path is not None:
            self.assertEqual(cm.exception.path, path)
        return cm.exception

    def bytes_code(self, data, code, offset="unset", path=None):
        with self.assertRaises(B.DecodeError) as cm:
            B.decode_bytes(data)
        self.assertEqual(cm.exception.code, code, msg=str(cm.exception))
        if offset != "unset":
            self.assertEqual(cm.exception.offset, offset)
        if path is not None:
            self.assertEqual(cm.exception.path, path)
        return cm.exception


def dumps(tree):
    return json.dumps(tree).encode("utf-8")
