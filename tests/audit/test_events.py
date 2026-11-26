"""TA-B02–B06: semantic events and snapshots (contract rev 0.3 section 5, ER02, ER04).

TA-B01 is the unchanged P2 engine suite (``tests/engine``), run with only the
section 13 seam and inventory amendments.

Expected identifiers, data objects and placement rules are written here from
the contract; snapshots are compared with test-side patch reconstructions.
"""

import dataclasses
import json
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from tests.audit.support import (
    DEFENSIVE, RUN0, S0, S1, STANDARD, CARRIERS, WALK_SEEDS, b02_witness, cjson, refold, walk,
)
from tests.battle.scenarios import S1_CELLS
from tests.support.battle_builder import as_adversarial, build, opening_document
from tests.engine.test_opening import deplete

CL = ("CLOSURE_DISPLACEMENT", "CLOSURE_CHECK", "RECOVERY", "ADVANCE", "END_CHECK")
IN_OPEN = ["r0:IN:INITIAL_CHECK", "r0:IN:OPEN_ROUND"]


def principal(rnd, side, o, *tail):
    return [f"r{rnd}:{side}.o{o}:ROOT", f"r{rnd}:{side}.o{o}:IMMEDIATE_CHECK"] + list(tail)


def closure(rnd, last):
    return [f"r{rnd}:CL:{k}" for k in CL + (last,)]


def g4_ids():
    roots = [IN_OPEN]
    for rnd in range(1, 13):
        first, second = ("S0", "S1") if rnd % 2 else ("S1", "S0")
        roots.append(principal(rnd, first, 1))
        roots.append(principal(rnd, second, 1) + closure(rnd, "TERMINAL" if rnd == 12 else "OPEN_ROUND"))
    return roots


EXPECTED_IDS = {
    "G1": [IN_OPEN, principal(1, "S0", 1), principal(1, "S1", 1),
           principal(1, "S0", 2) + closure(1, "OPEN_ROUND")],
    "G2": [IN_OPEN, principal(1, "S0", 1)],
    "G3": [IN_OPEN, principal(1, "S0", 1, "r1:S0.o1:TERMINAL")],
    "G4": g4_ids(),
}
WITNESS_IDS = [IN_OPEN, principal(1, "S0", 1),
               ["r1:S1.o1:ROOT", "r1:S1.o1:IMMEDIATE_CHECK", "r1:CL:CLOSURE_DISPLACEMENT",
                "r1:CL:CLOSURE_CHECK", "r1:CL:RECOVERY", "r1:CL:ADVANCE", "r1:CL:END_CHECK",
                "r1:CL:OPEN_ROUND"]]
POINT = {"INITIAL_CHECK": "INITIAL_CHECK", "IMMEDIATE_CHECK": "AFTER_ROOT",
         "CLOSURE_CHECK": "AFTER_CLOSURE_DISPLACEMENT", "END_CHECK": "ROUND_END"}
USE = {"HoldOrder": "INDIVIDUAL", "PassOrder": "PASS", "DeclareWithdrawal": "POSTURE_WITHDRAWAL",
       "Capitulate": None}
ROOT_PATHS = ("/ledger/uses", "/sides", "/formations", "/personnel", "/mounts", "/ammunition",
              "/contacts")


def doc(state):
    return json.loads(B.canonical_bytes(state))


def leaf_changes(a, b, path=""):
    """Test-side changed pointers (type-sensitive; unequal shapes are leaves)."""
    if cjson(a) == cjson(b):
        return []
    if type(a) is dict and type(b) is dict and a.keys() == b.keys():
        return [p for k in sorted(a) for p in leaf_changes(a[k], b[k], f"{path}/{k}")]
    if type(a) is list and type(b) is list and len(a) == len(b):
        return [p for i in range(len(a)) for p in leaf_changes(a[i], b[i], f"{path}/{i}")]
    return [path]


def bare_roots(state, commands):
    """Resolve each command by bare ``resolve``; yields (before, command, Resolved)."""
    out = []
    for c in commands:
        before = B.canonical_bytes(state)
        r = E.resolve(state, c)
        if type(r) is not E.Resolved:
            raise AssertionError(repr(r)[:300])
        if B.canonical_bytes(state) != before:
            raise AssertionError("resolve mutated its input")
        out.append((state, c, r))
        state = r.accepted.state
    return out


def b0_state():
    return build(deplete(as_adversarial(opening_document(), "B03a"), S1_CELLS))


class EventChecks(unittest.TestCase):

    def check_root(self, before, command, resolved, cursor, label):
        """Placement (5.3), data (5.4), positions and snapshot refold (B02)."""
        rec, snaps = resolved.record, resolved.snapshots
        self.assertEqual(rec.cursor, cursor, label)
        self.assertEqual(rec.cursor, before.clock.event_cursor + 1, label)
        self.assertEqual(rec.previous, B.digest(before), label)
        self.assertEqual(rec.current, B.digest(resolved.accepted.state), label)
        self.assertEqual(tuple(e.stage for e in rec.events), resolved.accepted.stages, label)
        self.assertEqual(len(snaps), len(rec.events), label)
        start = doc(before)
        events = [{"effects": [{"path": f.path, "new": json.loads(f.new)} for f in e.effects]}
                  for e in rec.events]
        rebuilt = refold(start, events)
        prev = start
        kinds = [e.stage.name for e in rec.events]
        for i, (e, s, d) in enumerate(zip(rec.events, snaps, rebuilt)):
            where = f"{label} {e.stage_id}"
            self.assertEqual((s.stage, s.stage_id), (e.stage, e.stage_id), where)
            self.assertEqual(cjson(s.document()), cjson(d), where)
            for f in e.effects:
                self.assertEqual(f.old, cjson(self.at(prev, f.path)), where)
            self.assertEqual(e.draws, (), where)
            self.check_placement(e.stage.name, i, prev, d, where)
            nxt = kinds[i + 1] if i + 1 < len(kinds) else None
            self.assertEqual(e.data, cjson(self.expected_data(e.stage.name, command, d, nxt)), where)
            self.assertIsInstance(B.EventRef(e.stage_id), B.EventRef)
            prev = d
        self.assertEqual(cjson(rebuilt[-1]), B.canonical_bytes(resolved.accepted.state), label)

    @staticmethod
    def at(doc_, pointer):
        node = doc_
        for s in pointer[1:].split("/"):
            node = node[int(s)] if type(node) is list else node[s]
        return node

    def check_placement(self, stage, i, a, b, where):
        changed = leaf_changes(a, b)
        cursor = [p for p in changed if p == "/clock/event_cursor"]
        if i == 0:
            self.assertEqual(cursor, ["/clock/event_cursor"], where)
            self.assertEqual(b["clock"]["event_cursor"], a["clock"]["event_cursor"] + 1, where)
        else:
            self.assertEqual(cursor, [], where)
        rest = [p for p in changed if p != "/clock/event_cursor"]
        if stage in ("INITIAL_CHECK", "CLOSURE_DISPLACEMENT", "CLOSURE_CHECK", "RECOVERY",
                     "END_CHECK"):
            self.assertEqual(rest, [], where)
        elif stage == "ROOT":
            self.assertEqual(cjson(a["phase"]), cjson(b["phase"]), where)
            for p in rest:
                self.assertTrue(any(p == r or p.startswith(r + "/") for r in ROOT_PATHS), (where, p))
        elif stage == "IMMEDIATE_CHECK":
            self.assertIn(rest, ([], ["/phase/side"]), where)
        elif stage == "ADVANCE":
            self.assertEqual(rest, ["/clock/completed_rounds"], where)
            self.assertEqual(b["clock"]["completed_rounds"], a["clock"]["completed_rounds"] + 1)
        elif stage == "OPEN_ROUND":
            for p in rest:
                self.assertTrue(p.startswith(("/phase", "/ledger")), (where, p))
            self.assertEqual(b["phase"]["kind"], "AwaitingPrincipal", where)
        elif stage == "TERMINAL":
            for p in rest:
                self.assertTrue(p.startswith(("/phase", "/ledger")), (where, p))
            self.assertEqual(b["phase"]["kind"], "Terminal", where)
            self.assertIsNone(b["ledger"], where)
        else:
            self.fail(stage)
        for fixed in ("schema", "scenario"):
            self.assertEqual(cjson(a[fixed]), cjson(b[fixed]), where)

    @staticmethod
    def expected_data(stage, command, after, nxt):
        if stage in POINT:
            return {"point": POINT[stage], "result": "TERMINAL" if nxt == "TERMINAL" else "CONTINUE"}
        if stage == "ROOT":
            body = E.encode_command(command)
            return {"kind": body["kind"], "side": body["side"],
                    "formation": body.get("formation"), "use": USE[body["kind"]]}
        if stage in ("CLOSURE_DISPLACEMENT", "RECOVERY"):
            return {"applied": []}
        if stage == "ADVANCE":
            return {"completed": after["clock"]["completed_rounds"]}
        if stage == "OPEN_ROUND":
            return {"round": after["clock"]["completed_rounds"] + 1, "first": after["phase"]["side"]}
        if stage == "TERMINAL":
            return {"record": after["phase"]["record"]}
        raise AssertionError(stage)


class Goldens(EventChecks):

    def run_carrier(self, fixture, commands, expected):
        d = B.descriptor(fixture)
        state = (B.f01_opening(d.variant, d.orientation)
                 if d.fixture_class is B.FixtureClass.CANONICAL_OPENING else B.f01_supplied(fixture))
        roots = bare_roots(state, commands)
        self.assertEqual([[e.stage_id for e in r.record.events] for _, _, r in roots], expected)
        for n, (before, c, r) in enumerate(roots, start=1):
            self.check_root(before, c, r, n, f"{fixture.token} root {n}")
        return roots

    def test_b02_goldens(self):
        for name in ("G1", "G2", "G3", "G4"):
            with self.subTest(carrier=name):
                fixture, commands = CARRIERS[name]
                roots = self.run_carrier(fixture, commands(), EXPECTED_IDS[name])
                self.assertEqual(sum(len(r.record.events) for _, _, r in roots),
                                 {"G1": 14, "G2": 4, "G3": 5, "G4": 122}[name])

    def test_b02_g0_and_b1_no_records(self):
        s = E.BattleSession.open(DEFENSIVE, RUN0)
        r = s.submit(E.OpenBattle())
        self.assertIs(type(r), E.Rejected)
        self.assertIs(r.code, E.RejectCode.PHASE)
        self.assertEqual((s.records, s.journal, s.state.clock.event_cursor), ((), (), 0))

    def test_b02_extra_s1_closing_witness(self):
        roots = self.run_carrier(STANDARD, [E.OpenBattle(), E.PassOrder(S0), E.PassOrder(S1)],
                                 WITNESS_IDS)
        self.assertEqual(len(roots[-1][2].record.events), 8)
        self.assertEqual([r.stage_id for r in b02_witness().records[-1].events], WITNESS_IDS[-1])

    def test_b02_b0_bare_terminal(self):
        state = b0_state()
        origins = [l.origin for l in state.personnel]
        self.assertTrue(any(o is not None for o in origins))
        (before, c, r), = bare_roots(state, [E.OpenBattle()])
        self.assertEqual([e.stage_id for e in r.record.events],
                         ["r0:IN:INITIAL_CHECK", "r0:IN:TERMINAL"])
        self.check_root(before, c, r, 1, "B0")
        t = r.accepted.state
        self.assertEqual((t.clock.event_cursor, t.clock.completed_rounds), (1, 0))
        self.assertEqual(t.phase.record.charged_rounds, 0)
        self.assertEqual([l.origin for l in t.personnel], origins)


class Records(EventChecks):

    def test_b03_both_finished_transient(self):
        s = E.BattleSession.open(STANDARD)
        for c in CARRIERS["G1"][1]()[:3]:
            s.submit(c)
        before = s.state
        r = E.resolve(before, E.PassOrder(S0))
        snaps = r.snapshots
        transient = [x for x in snaps if x.stage is not E.Stage.OPEN_ROUND]
        self.assertEqual(len(transient), 7)
        for x in transient[1:]:
            d = x.document()
            uses = {u["side"] for u in d["ledger"]["uses"] if u["kind"] == "PASS"}
            self.assertEqual(uses, {"S0", "S1"})
            with self.assertRaises(B.DomainError):
                B.decode_state(d)
        final = snaps[-1].document()
        self.assertEqual(B.canonical_bytes(B.decode_state(final)), B.canonical_bytes(r.accepted.state))
        self.assertEqual(B.validate_state(snaps[0]), B.validate_state(object()))
        self.assertEqual(B.validate_state(snaps[0])[0].clause, "V00")
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(snaps[0], E.PassOrder(S1))
        self.assertEqual(cm.exception.clause, "V00")

    def test_b03_immutability_and_projection(self):
        r = E.resolve(E.BattleSession.open(STANDARD).state, E.OpenBattle())
        e, s = r.record.events[1], r.snapshots[1]
        for obj, name in ((e, "data"), (e.effects[0], "new"), (s, "values"), (r.record, "events"),
                          (r, "snapshots")):
            with self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(obj, name, getattr(obj, name))
        self.assertIs(type(e.data), bytes)
        self.assertIs(type(e.effects), tuple)
        d1 = s.document()
        d1["phase"]["side"] = "S1"
        d1["ledger"]["uses"].append(1)
        self.assertEqual(s.document()["phase"], {"kind": "AwaitingPrincipal", "side": "S0"})
        self.assertEqual(s.document()["ledger"]["uses"], [])

    def test_b03_continuation_and_record_binding(self):
        roots = bare_roots(B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD),
                           CARRIERS["G3"][1]())
        g2 = bare_roots(B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD),
                        [E.OpenBattle(), E.PassOrder(S0)])
        root, imm = g2[1][2].snapshots
        self.assertEqual(root.document()["phase"]["side"], "S0")
        self.assertEqual(imm.document()["phase"]["side"], "S1")
        r = roots[1][2]
        term = r.record.events[-1]
        self.assertEqual(json.loads(term.data)["record"], r.snapshots[-1].document()["phase"]["record"])

    def test_b03_direct_errors(self):
        ok_effect = dict(path="/clock/event_cursor", old=b"0", new=b"1")
        cases = [
            (E.Effect, dict(ok_effect, path=1), "T15", "path"),
            (E.Effect, dict(ok_effect, path="clock"), "T16", "path"),
            (E.Effect, dict(ok_effect, path="/clock/~2"), "T16", "path"),
            (E.Effect, dict(ok_effect, path=""), "T16", "path"),
            (E.Effect, dict(ok_effect, old="0"), "T15", "old"),
            (E.Effect, dict(ok_effect, old=b"00"), "T16", "old"),
            (E.Effect, dict(ok_effect, new=b"1.0"), "T16", "new"),
            (E.Effect, dict(ok_effect, new=b"0"), "T16", "new"),
            (E.Effect, dict(ok_effect, new=b'{"b":1,"a":2}'), "T16", "new"),
        ]
        for cls, kw, code, path in cases:
            with self.subTest(kw=kw):
                with self.assertRaises(B.InvalidValue) as cm:
                    cls(**kw)
                self.assertEqual((cm.exception.clause, cm.exception.path), (code, path))
        ev = dict(stage=E.Stage.ROOT, stage_id="r1:S0.o1:ROOT", data=b"{}", effects=(), draws=())
        dr = E.DrawRecord(E.Channel.injury, 0, 5)
        eff = E.Effect(**ok_effect)
        cases = [
            (dict(ev, stage="ROOT"), "T15", "stage"),
            (dict(ev, stage_id=b"r1"), "T15", "stage_id"),
            (dict(ev, stage_id="r1:S0.o1:TERMINAL"), "T16", "stage_id"),
            (dict(ev, stage_id="r1:S0.o1:MELEE:S0.H1:S1.H1:-"), "T16", "stage_id"),
            (dict(ev, data=b"[]"), "T16", "data"),
            (dict(ev, data="{}"), "T15", "data"),
            (dict(ev, effects=[eff]), "T15", "effects"),
            (dict(ev, effects=(1,)), "T15", "effects/0"),
            (dict(ev, effects=(eff, eff)), "T16", "effects"),
            (dict(ev, draws=(dr,)), "T16", "draws"),
            (dict(ev, draws=((),)), "T15", "draws/0"),
        ]
        for kw, code, path in cases:
            with self.subTest(kw=kw):
                with self.assertRaises(B.InvalidValue) as cm:
                    E.StageEvent(**kw)
                self.assertEqual((cm.exception.clause, cm.exception.path), (code, path))
        for kw, code, path in ((dict(channel="injury", index=0, numerator=1), "T15", "channel"),
                               (dict(channel=E.Channel.injury, index=64, numerator=1), "T10", "index"),
                               (dict(channel=E.Channel.injury, index=0, numerator=True), "T15",
                                "numerator"),
                               (dict(channel=E.Channel.injury, index=0, numerator=2 ** 53), "T10",
                                "numerator")):
            with self.assertRaises(B.InvalidValue) as cm:
                E.DrawRecord(**kw)
            self.assertEqual((cm.exception.clause, cm.exception.path), (code, path))
        r = E.resolve(E.BattleSession.open(STANDARD).state, E.OpenBattle())
        s0 = r.snapshots[0]
        with self.assertRaises(B.InvalidValue) as cm:
            E.StageSnapshot(s0.stage, s0.stage_id, s0.values[:-1])
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T04", "values"))
        with self.assertRaises(B.InvalidValue) as cm:
            E.StageSnapshot(s0.stage, s0.stage_id, list(s0.values))
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "values"))
        bad = (s0.values[0], "x") + s0.values[2:]
        with self.assertRaises(B.InvalidValue) as cm:
            E.StageSnapshot(s0.stage, s0.stage_id, bad)
        self.assertTrue(cm.exception.path.startswith("values/"), cm.exception.path)
        with self.assertRaises(B.InvalidValue) as cm:
            E.Resolved(r.accepted, r.record, r.snapshots[:1])
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", "snapshots"))
        with self.assertRaises(B.InvalidValue) as cm:
            E.Resolved(r.accepted, r.record, tuple(reversed(r.snapshots)))
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", "snapshots"))
        with self.assertRaises(B.InvalidValue) as cm:
            E.RootRecord(1, r.record.command, r.record.command_digest, r.record.previous,
                         r.record.current, r.record.events + r.record.events[:1])
        self.assertEqual(cm.exception.clause, "T16")
        for run in ((0, 0), 0, "RunKey(0,0)"):
            with self.assertRaises(B.InvalidValue) as cm:
                E.BattleSession.open(STANDARD, run)
            self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "run"))
        with self.assertRaises(B.UnknownId):
            E.BattleSession.open(B.FixtureId("F01-v1-nowhere"), (0, 0))


class Walks(EventChecks):

    def test_b04_b05_b06_walks(self):
        for seed in WALK_SEEDS:
            s, commands, _ = walk(seed)
            d = B.descriptor(s.records and B.FixtureId(json.loads(
                s.export_audit(seal=False).split(b"\n")[0])["fixture"]))
            state = (B.f01_opening(d.variant, d.orientation)
                     if d.fixture_class is B.FixtureClass.CANONICAL_OPENING
                     else B.f01_supplied(d.fixture_id))
            ids = []
            for n, (c, rec) in enumerate(zip(commands, s.records), start=1):
                r = E.resolve(state, c)
                self.assertEqual(r.record, rec, seed)
                self.check_root(state, c, r, n, f"seed {seed} root {n}")
                ids += [e.stage_id for e in rec.events]
                state = r.accepted.state
            self.assertEqual(len(ids), len(set(ids)), seed)
            self.assertEqual(B.canonical_bytes(state), B.canonical_bytes(s.state), seed)


if __name__ == "__main__":
    unittest.main()
