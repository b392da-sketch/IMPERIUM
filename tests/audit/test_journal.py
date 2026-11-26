"""TA-C01–C05: the audit journal wire, golden bytes, commands, atomic
publication and the P2 journal projection (contract rev 0.3 sections 6–7, 11).

Expected journal bytes are built here from an independent primitive model:
stable P2 states from the accepted ``step`` transition, the section 5.3
placement rules for intermediate documents, a test-side canonical diff,
the section 5.4 data objects, the section 7 line schemas and a test-side
chain. Nothing below takes an expected value from ``export_audit``.
"""

import importlib
import json
import unittest
from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
from tests.audit.support import (
    CARRIERS, DEFENSIVE, RUN0, S0, S1, STANDARD, WALK_SEEDS, chained, cjson, journals, oracles,
    session, sha, trees, walk,
)
from tests.audit.test_events import EventChecks, b0_state
from tests.engine.test_boundary import VARIANTS, closing
from tests.support.battle_builder import build

session_module = importlib.import_module("imperium.battle.engine.session")
STAGES = ("ADVANCE", "CLOSURE_CHECK", "CLOSURE_DISPLACEMENT", "END_CHECK", "IMMEDIATE_CHECK",
          "INITIAL_CHECK", "OPEN_ROUND", "RECOVERY", "ROOT", "TERMINAL")
HEADER_KEYS = {"kind", "schema", "state_schema", "command_schema", "event_schema", "rng",
               "registry", "fixture", "pair", "genesis", "run", "chain"}
ROOT_KEYS = {"kind", "cursor", "command", "command_digest", "previous", "current", "events",
             "chain"}
TRAILER_KEYS = {"kind", "roots", "cursor", "final", "terminal", "stages", "draws", "chain"}
PAIRS = {"open": "F01-v1-open", "rough": "F01-v1-rough", "barrier": "F01-v1-barrier"}
COMMANDS = {
    "OpenBattle": (E.OpenBattle(), b'{"kind":"OpenBattle","schema":"imperium.battle-command/1"}'),
    "HoldOrder": (E.HoldOrder(S0, B.FormationId("S0.H1")),
                  b'{"formation":"S0.H1","kind":"HoldOrder","schema":"imperium.battle-command/1",'
                  b'"side":"S0"}'),
    "PassOrder": (E.PassOrder(S1), b'{"kind":"PassOrder","schema":"imperium.battle-command/1",'
                                   b'"side":"S1"}'),
    "DeclareWithdrawal": (E.DeclareWithdrawal(S0),
                          b'{"kind":"DeclareWithdrawal","schema":"imperium.battle-command/1",'
                          b'"side":"S0"}'),
    "Capitulate": (E.Capitulate(S1), b'{"kind":"Capitulate","schema":"imperium.battle-command/1",'
                                     b'"side":"S1"}'),
}


def jdoc(state):
    return json.loads(B.canonical_bytes(state))


def copy(tree):
    return json.loads(cjson(tree))


def diff(a, b, path=""):
    """Test-side canonical diff (section 5.2), as (path, old, new) triples."""
    if cjson(a) == cjson(b):
        return []
    if type(a) is dict and type(b) is dict and a.keys() == b.keys():
        return [x for k in sorted(a) for x in diff(a[k], b[k], f"{path}/{k.replace('~', '~0').replace('/', '~1')}")]
    if type(a) is list and type(b) is list and len(a) == len(b):
        return [x for i in range(len(a)) for x in diff(a[i], b[i], f"{path}/{i}")]
    return [(path, a, b)]


def new_use(command):
    t = type(command)
    side = command.side.name
    if t is E.HoldOrder:
        return {"group": None, "kind": "INDIVIDUAL", "members": [command.formation.token],
                "side": side, "work": [{"kind": "Hold"}]}
    if t is E.PassOrder:
        return {"group": None, "kind": "PASS", "members": [], "side": side, "work": []}
    if t is E.DeclareWithdrawal:
        return {"group": None, "kind": "POSTURE_WITHDRAWAL", "members": [], "side": side,
                "work": []}
    return None


def model_docs(before, after, command, stages):
    """Intermediate documents from the two stable documents and section 5.3."""
    docs, cur = [], copy(before)
    names = [s.name for s in stages]
    for i, stage in enumerate(names):
        cur = copy(cur)
        if i == 0:
            cur["clock"]["event_cursor"] += 1
        if stage == "ROOT":
            for k in ("sides", "formations", "personnel", "mounts", "ammunition", "contacts"):
                if "TERMINAL" in names or "CLOSURE_DISPLACEMENT" not in names:
                    cur[k] = copy(after[k])
            u = new_use(command)
            if u is not None:
                cur["ledger"]["uses"] = cur["ledger"]["uses"] + [u]
        elif stage == "IMMEDIATE_CHECK" and i == len(names) - 1:
            cur["phase"] = copy(after["phase"])
        elif stage == "ADVANCE":
            cur["clock"]["completed_rounds"] += 1
        elif stage in ("OPEN_ROUND", "TERMINAL"):
            cur["phase"], cur["ledger"] = copy(after["phase"]), copy(after["ledger"])
        docs.append(cur)
    if cjson(docs[-1]) != cjson(after):
        raise AssertionError("model does not reach the accepted successor")
    return docs


def model_journal(fixture, commands, run, seal):
    d = B.descriptor(fixture)
    state = (B.f01_opening(d.variant, d.orientation)
             if d.fixture_class is B.FixtureClass.CANONICAL_OPENING else B.f01_supplied(fixture))
    pair = (PAIRS[d.variant.name.lower()] if d.fixture_class is B.FixtureClass.CANONICAL_OPENING
            else fixture.token)
    lines = [{"kind": "header", "schema": "imperium.battle-audit/1",
              "state_schema": "imperium.battle-state/1",
              "command_schema": "imperium.battle-command/1",
              "event_schema": "imperium.battle-event/1", "rng": "D4-SHA256-v1",
              "registry": "IMPERIUM-BK-1", "fixture": fixture.token, "pair": pair,
              "genesis": B.digest(state),
              "run": None if run is None else {"seed": run.seed, "replicate": run.replicate}}]
    counts = dict.fromkeys(STAGES, 0)
    for n, c in enumerate(commands, start=1):
        r = E.step(state, c)
        assert type(r) is E.Accepted
        before, after = jdoc(state), jdoc(r.state)
        docs = model_docs(before, after, c, r.stages)
        ids = model_ids(before, c, r.stages)
        events, prev = [], before
        for i, (stage, sid, cur) in enumerate(zip(r.stages, ids, docs)):
            nxt = r.stages[i + 1].name if i + 1 < len(r.stages) else None
            events.append({"stage": stage.name, "id": sid,
                           "data": EventChecks.expected_data(stage.name, c, cur, nxt),
                           "effects": [{"path": p, "old": o, "new": v} for p, o, v in diff(prev, cur)],
                           "draws": []})
            counts[stage.name] += 1
            prev = cur
        body = json.loads(COMMAND_BODY(c))
        lines.append({"kind": "root", "cursor": n, "command": body,
                      "command_digest": sha(cjson(body)), "previous": B.digest(state),
                      "current": B.digest(r.state), "events": events})
        state = r.state
    if seal:
        lines.append({"kind": "trailer", "roots": len(commands), "cursor": state.clock.event_cursor,
                      "final": B.digest(state), "terminal": type(state.phase) is B.Terminal,
                      "stages": counts, "draws": 0})
    return chained(lines)


def COMMAND_BODY(c):
    body = {"kind": type(c).__name__, "schema": "imperium.battle-command/1"}
    if hasattr(c, "side"):
        body["side"] = c.side.name
    if type(c) is E.HoldOrder:
        body["formation"] = c.formation.token
    return cjson(body)


def model_ids(before, command, stages):
    """Section 4.3 ids from the pre-root document."""
    completed = before["clock"]["completed_rounds"]
    out = []
    if type(command) is E.OpenBattle:
        return [f"r0:IN:{s.name}" for s in stages]
    side = command.side.name
    o = sum(1 for u in before["ledger"]["uses"] if u["side"] == side) + 1
    rnd = completed + 1
    closing_ = False
    for s in stages:
        if s.name in ("CLOSURE_DISPLACEMENT",):
            closing_ = True
        out.append(f"r{rnd}:CL:{s.name}" if closing_ else f"r{rnd}:{side}.o{o}:{s.name}")
    return out


class Wire(unittest.TestCase):

    def test_c01_framing_and_schemas(self):
        for name in CARRIERS:
            for data in journals(name):
                with self.subTest(carrier=name, sealed=data.endswith(b'}\n') and b'"trailer"' in data):
                    self.assertTrue(data.endswith(b"\n"))
                    self.assertNotIn(b"\r", data)
                    self.assertNotIn(b"\n\n", data)
                    self.assertTrue(data.isascii())
                    raw = data.split(b"\n")[:-1]
                    for line in raw:
                        self.assertEqual(cjson(json.loads(line)), line)
                    ts = trees(data)
                    self.assertEqual(set(ts[0]), HEADER_KEYS)
                    for t in ts[1:]:
                        self.assertEqual(set(t), TRAILER_KEYS if t["kind"] == "trailer" else ROOT_KEYS)
                        if t["kind"] == "root":
                            for e in t["events"]:
                                self.assertEqual(set(e), {"stage", "id", "data", "effects", "draws"})
                                self.assertIs(type(e["data"]), dict)
                                for f in e["effects"]:
                                    self.assertEqual(set(f), {"path", "old", "new"})
                    self.assertEqual(chained(ts), data)
                    if ts[-1]["kind"] == "trailer":
                        self.assertEqual(sorted(ts[-1]["stages"]), list(STAGES))

    def test_c02_golden_bytes(self):
        digests = {}
        for name in ("G1", "G2", "G3", "G4"):
            fixture, commands = CARRIERS[name]
            for seal in (True, False):
                expected = model_journal(fixture, commands(), RUN0, seal)
                with self.subTest(carrier=name, seal=seal):
                    self.assertEqual(session(name).export_audit(seal=seal), expected)
                digests[(name, seal)] = sha(expected)
            expected = model_journal(fixture, commands(), None, True)
            self.assertEqual(session(name, None).export_audit(), expected)
        for name in ("G1", "G2", "G3", "G4"):
            print(f"\nC02 {name} sealed {digests[(name, True)]} prefix {digests[(name, False)]}",
                  end="")

    def test_c02_g0_oracle(self):
        model = oracles()["g0_wire_model"]
        for key in ("original", "replacement_valid_run"):
            m = model[key]
            s = E.BattleSession.open(DEFENSIVE, E.RunKey(m["seed"], 0))
            r = s.submit(E.OpenBattle())
            self.assertIs(r.code, E.RejectCode.PHASE)
            sealed, prefix = s.export_audit(), s.export_audit(seal=False)
            self.assertEqual(sha(prefix), m["prefix_sha256"])
            self.assertEqual(sha(sealed), m["sealed_sha256"])
            self.assertEqual(trees(prefix)[-1]["chain"], m["prefix_chain"])
            self.assertEqual(trees(sealed)[-1]["chain"], m["sealed_chain"])
            self.assertEqual(sealed, model_journal(DEFENSIVE, [], E.RunKey(m["seed"], 0), True))
            t = trees(sealed)[-1]
            self.assertEqual((t["roots"], t["cursor"], t["terminal"], t["draws"]), (0, 0, True, 0))
            self.assertEqual(t["final"], model["full_state_digest"])
            self.assertEqual(set(t["stages"].values()), {0})

    def test_c02_export_arguments(self):
        s = session("G1")
        before = (s.state, s.journal, s.records)
        for bad in (1, None, "yes"):
            with self.assertRaises(TypeError):
                s.export_audit(bad)
        mid = s.export_audit()
        self.assertEqual(before, (s.state, s.journal, s.records))
        self.assertIs(type(s.submit(E.PassOrder(S1))), E.Accepted)
        self.assertTrue(s.export_audit(seal=False).startswith(mid[:mid.rindex(b'{"chain"')]))


class Commands(unittest.TestCase):

    def test_c03_vectors(self):
        for name, (c, data) in COMMANDS.items():
            with self.subTest(command=name):
                self.assertEqual(E.command_bytes(c), data)
                self.assertEqual(E.decode_command(data), c)
                self.assertEqual(E.command_bytes(E.decode_command(data)), data)
                self.assertEqual(E.command_digest(c), sha(data))
                self.assertEqual(E.encode_command(c), json.loads(data))

    def test_c03_negatives(self):
        hold = COMMANDS["HoldOrder"][1]
        cases = [
            "x", None, bytearray(hold), memoryview(hold),
            b"", b" ", hold + b"\n", b" " + hold, hold.replace(b",", b", "),
            b'{"schema":"imperium.battle-command/1","kind":"OpenBattle"}',
            b'{"kind":"OpenBattle","schema":"imperium.battle-command/2"}',
            b'{"kind":"Rest","schema":"imperium.battle-command/1","side":"S0"}',
            b'{"kind":"OpenBattle","schema":"imperium.battle-command/1","side":"S0"}',
            b'{"kind":"PassOrder","schema":"imperium.battle-command/1"}',
            b'{"kind":"PassOrder","schema":"imperium.battle-command/1","side":"S2"}',
            b'{"kind":"PassOrder","schema":"imperium.battle-command/1","side":0}',
            b'{"kind":"PassOrder","schema":"imperium.battle-command/1","side":true}',
            b'{"kind":"PassOrder","kind":"PassOrder","schema":"imperium.battle-command/1","side":"S0"}',
            b'{"formation":"","kind":"HoldOrder","schema":"imperium.battle-command/1","side":"S0"}',
            b'{"formation":"S0.H1","kind":"HoldOrder","schema":"imperium.battle-command/1","side":"S0","x":1}',
            b'{"kind":"PassOrder","schema":"imperium.battle-command/1","side":"S\\u0030"}',
            b'{"kind":"PassOrder","schema":"imperium.battle-command/1","side":"S0","n":1.0}',
            b'["PassOrder"]', b"null", b"\xef\xbb\xbf" + hold, "é".encode() + hold,
            b'{"formation":"' + b"S" * 1024 + b'","kind":"HoldOrder","schema":"imperium.battle-command/1","side":"S0"}',
        ]
        for data in cases:
            with self.subTest(data=data[:60] if isinstance(data, (bytes, str)) else data):
                with self.assertRaises(B.InvalidValue) as cm:
                    E.decode_command(data)
                self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "command"))
        # No fixture-legality check: a well-formed unknown formation decodes.
        c = E.decode_command(hold.replace(b"S0.H1", b"S0.X9"))
        self.assertEqual(c.formation, B.FormationId("S0.X9"))


class Publication(unittest.TestCase):

    def snapshot(self, s):
        return (s.state, B.digest(s.state), s.journal, s.records, s.export_audit(),
                s.export_audit(seal=False))

    def test_c04_failure_before_publication(self):
        for target in ("JournalEntry", "digest"):
            with self.subTest(target=target):
                s = session("G1")
                before = self.snapshot(s)
                with mock.patch.object(session_module, target, side_effect=RuntimeError("boom")):
                    with self.assertRaises(RuntimeError):
                        s.submit(E.PassOrder(S1))
                self.assertEqual(self.snapshot(s), before)
                self.assertIs(s.state, before[0])
        s = session("G1")
        before = self.snapshot(s)
        events = importlib.import_module("imperium.battle.engine.events")
        step_module = importlib.import_module("imperium.battle.engine.step")
        with mock.patch.object(step_module, "build_root", side_effect=RuntimeError("record")):
            with self.assertRaises(RuntimeError):
                s.submit(E.PassOrder(S1))
        self.assertEqual(self.snapshot(s), before)
        self.assertTrue(callable(events.build_root))

    def test_c04_rejected_and_deferred(self):
        s = session("G1")
        before = self.snapshot(s)
        r = s.submit(E.PassOrder(S0))
        self.assertIs(type(r), E.Rejected)
        self.assertIs(r.code, E.RejectCode.WRONG_SIDE)
        self.assertEqual(self.snapshot(s), before)
        fake = E.Deferred(s.state, E.PassOrder(S1), E.Stage.RECOVERY, ("DO-P2-02",))
        calls = []

        def stub(state, command):
            calls.append(command)
            return fake

        with mock.patch.object(session_module, "resolve", side_effect=stub):
            self.assertIs(s.submit(E.PassOrder(S1)), fake)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.snapshot(s), before)

    def test_c04_b1_bare_deferral(self):
        for name, (kw, stage, obligations) in VARIANTS.items():
            with self.subTest(variant=name):
                state = build(closing("E-" + name, **kw))
                before = B.canonical_bytes(state)
                r = E.resolve(state, E.PassOrder(S1))
                self.assertIs(type(r), E.Deferred)
                self.assertIs(r.state, state)
                self.assertIs(r.stage, stage)
                self.assertEqual(r.obligations, obligations)
                self.assertEqual(r, E.step(state, E.PassOrder(S1)))
                self.assertEqual(B.canonical_bytes(state), before)
                self.assertEqual(state.clock.event_cursor, 1)

    def test_c05_journal_projection(self):
        sessions = [session(n) for n in ("G1", "G2", "G3", "G4")]
        sessions += [walk(seed)[0] for seed in WALK_SEEDS]
        for s in sessions:
            self.assertEqual(len(s.journal), len(s.records))
            for j, r in zip(s.journal, s.records):
                self.assertEqual((j.cursor, j.command_digest, j.previous, j.current),
                                 (r.cursor, r.command_digest, r.previous, r.current))
                self.assertEqual(r.command_digest, sha(E.command_bytes(r.command)))
            if s.records:
                self.assertEqual(s.records[0].previous,
                                 trees(s.export_audit(seal=False))[0]["genesis"])
                self.assertEqual(s.records[-1].current, B.digest(s.state))


if __name__ == "__main__":
    unittest.main()
