"""TA-X01–X06: seeded random play, illegal interleaving, conservation, ML lemmas,
determinism and the frozen baseline.

Seeds are 0–999 only. By default TA-X01 plays all 1000 seeds, validates every
state by construction and round-trips every fifth seed through both codecs;
TA-X02 interleaves illegal proposals on every fourth seed.
``IMPERIUM_FULL_RANDOM=1`` round-trips every state and interleaves on all
1000 seeds.
"""

import hashlib
import os
import pathlib
import random
import subprocess
import sys
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from tests.battle.common import cond, fr, individual, leg, move, place, response
from tests.engine.helpers import (
    OPENINGS, S0, S1, EngineCase, awaiting, build, hold_use, make_reformer,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = range(1000)
FULL_X02 = os.environ.get("IMPERIUM_FULL_RANDOM") == "1"
X02_SEEDS = SEEDS if FULL_X02 else range(0, 1000, 4)
FULL = os.environ.get("IMPERIUM_FULL_RANDOM") == "1"
ABSORBING = (B.Disposition.WITHDRAWN, B.Disposition.DEPLETED, B.Disposition.SURRENDERED)


def other(side):
    return S1 if side is S0 else S0


def legal_commands(state):
    """Independent enumeration from phase, parity, roster and open opportunities."""
    if type(state.phase) is B.Opening:
        return [E.OpenBattle()]
    if type(state.phase) is not B.AwaitingPrincipal:
        return []
    side = state.phase.side
    used = {m for u in state.ledger.uses for m in u.members}
    rounds = {r.formation: r for r in state.ledger.formations}
    avail = {}
    for l in state.personnel:
        if l.status is B.PersonnelStatus.AVAILABLE:
            avail[l.lineage] = avail.get(l.lineage, 0) + l.count
    disp = {f.formation: f.disposition for f in state.formations}
    out = [E.PassOrder(side)]
    for e in state.scenario.roster:
        fid = e.formation
        r = rounds[fid]
        if (e.side is side and r.opened_eligible and fid not in used and not r.displacement_attempted
                and disp[fid] in (B.Disposition.ORGANIZED, B.Disposition.REFORMING)
                and avail.get(fid, 0) > 0):
            out.append(E.HoldOrder(side, fid))
    posture = {s.side: s.posture for s in state.sides}[side]
    if posture is B.Posture.CONTESTING:
        out.append(E.DeclareWithdrawal(side))
    out.append(E.Capitulate(side))
    return out


def illegal_proposals(state):
    """Typed proposals each illegal by an earlier rule, with the expected code."""
    if type(state.phase) is B.Opening:
        return [(E.PassOrder(S0), E.RejectCode.PHASE), (E.HoldOrder(S0, B.FormationId("S0.H1")),
                                                         E.RejectCode.PHASE)]
    if type(state.phase) is not B.AwaitingPrincipal:
        return [(E.PassOrder(S0), E.RejectCode.PHASE), (E.OpenBattle(), E.RejectCode.PHASE)]
    side = state.phase.side
    out = [(E.OpenBattle(), E.RejectCode.PHASE),
           (E.PassOrder(other(side)), E.RejectCode.WRONG_SIDE),
           (E.HoldOrder(side, B.FormationId(f"{other(side).name}.H1")), E.RejectCode.NOT_OWN_FORMATION),
           (E.HoldOrder(side, B.FormationId("S9.X1")), E.RejectCode.UNKNOWN_FORMATION)]
    used = [m for u in state.ledger.uses for m in u.members if u.side is side]
    if used:
        out.append((E.HoldOrder(side, used[0]), E.RejectCode.NOT_READY))
    if {s.side: s.posture for s in state.sides}[side] is B.Posture.WITHDRAWING:
        out.append((E.DeclareWithdrawal(side), E.RejectCode.ALREADY_WITHDRAWING))
    return out


def choose(rng, commands):
    weights = []
    for c in commands:
        t = type(c)
        weights.append(1 if t is E.Capitulate else 6 if t is E.DeclareWithdrawal else
                       30 if t is E.PassOrder else 40)
    return rng.choices(commands, weights)[0]


def game(seed, interleave=False):
    rng = random.Random(seed)
    fixture_id = OPENINGS[seed % len(OPENINGS)]
    s = E.BattleSession.open(fixture_id)
    states = [s.state]
    commands = []
    rejections = []
    while True:
        legal = legal_commands(s.state)
        if not legal:
            break
        if interleave:
            for c, code in illegal_proposals(s.state):
                if rng.random() < 0.5:
                    before = s.state
                    r = s.submit(c)
                    rejections.append((type(r), r.code if type(r) is E.Rejected else None, code,
                                       r.state is before, s.state is before))
        c = choose(rng, legal)
        r = s.submit(c)
        if type(r) is not E.Accepted:
            raise AssertionError(f"seed {seed}: legal {c} gave {r!r}"[:300])
        commands.append(c)
        states.append(s.state)
    return s, states, commands, rejections


def lineage_view(state):
    pers, mounts, ammo = {}, {}, {}
    for l in state.personnel:
        pers[l.lineage] = pers.get(l.lineage, 0) + l.count
    for m in state.mounts:
        mounts[m.formation] = mounts.get(m.formation, 0) + m.count
    for a in state.ammunition:
        ammo[a.formation] = (a.carried + a.expended, a.expended)
    return pers, mounts, ammo


def _avail(st):
    out = {}
    for l in st.personnel:
        if l.status is B.PersonnelStatus.AVAILABLE:
            out[l.lineage] = out.get(l.lineage, 0) + l.count
    return out


def _mounts(st, assigned_only):
    out = {}
    for m in st.mounts:
        if m.serviceability is not B.Serviceability.SERVICEABLE:
            continue
        if assigned_only and m.assignment is not B.Assignment.ASSIGNED:
            continue
        out[m.formation] = out.get(m.formation, 0) + m.count
    return out


def _rallied(st):
    if st.ledger is None:
        return set()
    return {m for u in st.ledger.uses for m, w in zip(u.members, u.work) if type(w) is B.Rally}


def check_ml(test, prev, cur, seed):
    """ML1–ML6 (P1 10.8) between consecutive stable states."""
    pf = {f.formation: f for f in prev.formations}
    same_round = (type(prev.phase) is B.AwaitingPrincipal and type(cur.phase) is B.AwaitingPrincipal
                  and prev.clock.completed_rounds == cur.clock.completed_rounds)
    rallied = _rallied(cur) if same_round else set()
    for f in cur.formations:
        p = pf[f.formation]
        if p.disposition in ABSORBING:                                        # ML1
            test.assertIs(f.disposition, p.disposition, seed)
        test.assertGreaterEqual(f.condition.fatigue, p.condition.fatigue, seed)     # ML3
        if f.formation not in rallied:
            test.assertGreaterEqual(f.condition.cohesion, p.condition.cohesion, seed)
            test.assertGreaterEqual(f.condition.morale, p.condition.morale, seed)
    pa, ca = _avail(prev), _avail(cur)
    for k, v in ca.items():                                                   # ML4a
        test.assertLessEqual(v, pa.get(k, 0), seed)
    test.assertEqual(_mounts(prev, False), _mounts(cur, False), seed)         # ML4b stock S
    pa_m, ca_m = _mounts(prev, True), _mounts(cur, True)
    battlefield = (B.Disposition.ORGANIZED, B.Disposition.REFORMING, B.Disposition.ROUTING)
    for f in cur.formations:                                                  # ML4b assigned
        if f.disposition in battlefield and pf[f.formation].disposition in battlefield:
            test.assertEqual(ca_m.get(f.formation, 0), pa_m.get(f.formation, 0), seed)
    if same_round:                                                            # ML2, ML5
        pr = {r.formation: r for r in prev.ledger.formations}
        for r in cur.ledger.formations:
            q = pr[r.formation]
            test.assertTrue(q.safe_latch or not r.safe_latch, seed)
            for flag in ("incoming", "exerted", "displaced", "displacement_attempted"):
                test.assertTrue(getattr(r, flag) or not getattr(q, flag), seed)
            if r.formation not in rallied:
                test.assertTrue(r.incoming_since_rally or not q.incoming_since_rally, seed)
            if q.response is not None:
                test.assertEqual(r.response, q.response, seed)
        for f in cur.formations:
            if f.disposition is B.Disposition.REFORMING:
                test.assertIs(pf[f.formation].disposition, B.Disposition.REFORMING, seed)
    if type(cur.phase) is B.AwaitingPrincipal:                                # ML6
        rounds = {r.formation: r for r in cur.ledger.formations}
        for f in cur.formations:
            if f.disposition in (B.Disposition.ORGANIZED, B.Disposition.REFORMING):
                test.assertTrue(rounds[f.formation].opened_eligible, seed)


class RandomPlay(EngineCase):

    def test_x01_x03_x04(self):
        for seed in SEEDS:
            s, states, commands, _ = game(seed)
            self.assertLessEqual(len(commands), 97, seed)
            self.assertIs(type(s.state.phase), B.Terminal, seed)
            full = FULL or seed % 5 == 0
            base = lineage_view(states[0])
            for prev, cur in zip(states, states[1:]):
                if full:
                    self.assert_valid(cur)
                if type(cur.phase) is B.AwaitingPrincipal:
                    self.assertFalse(B.side_finished(cur, S0) and B.side_finished(cur, S1), seed)
                    self.assertLessEqual(cur.clock.completed_rounds, 11)
                self.assertEqual(lineage_view(cur), base, seed)
                self.check_ml(prev, cur, seed)
            self.assertEqual([e.cursor for e in s.journal], list(range(1, len(commands) + 1)))

    def check_ml(self, prev, cur, seed):
        check_ml(self, prev, cur, seed)

    def test_x04_nontrivial_carrier(self):
        """Hold on an imported A carrier with prior response, exertion, incoming and
        condition bands preserves every earlier field (ML2, ML3, ML5)."""
        d = awaiting(label="X04", uses=[
            hold_use("S0", "S0.H3"),
            individual("S1", "S1.L1", move([(3, 6)], [leg((3, 7), (3, 6), 4)])),
        ])
        place(d, "S0.H2", (5, 7))
        place(d, "S0.H5", (6, 7))
        place(d, "S1.L1", (3, 6), 4)
        place(d, "S0.H1", (2, 6), 5)
        cond(d, "S0.H1", c=1, m=1, fat=1, e=2)
        cond(d, "S0.H4", c=1, m=0, fat=2, e=4)
        make_reformer(d, "S0.H6")
        r = fr(d, "S0.H1")
        r["response"] = response("DEFENSIVE_PIVOT", "S1.L1")
        r["exerted"] = True
        r["incoming"] = True
        r["incoming_since_rally"] = True
        fr(d, "S1.L1")["exerted"] = True
        for token in ("S0.H1", "S0.H2", "S0.H3", "S0.H4", "S0.H5", "S0.H6", "S0.L1", "S0.C1", "S1.L1"):
            fr(d, token)["safe_latch"] = False
        s = build(d)
        t = self.accepted(s, E.HoldOrder(S0, B.FormationId("S0.H1")))
        u = self.accepted(t, E.HoldOrder(S1, B.FormationId("S1.H1")))
        w = self.accepted(u, E.HoldOrder(S0, B.FormationId("S0.H6")))
        for prev, cur in ((s, t), (t, u), (u, w)):
            check_ml(self, prev, cur, "X04")
        self.assertEqual(w.formations, s.formations)
        self.assertEqual(w.ledger.formations, s.ledger.formations)

    def test_x02_illegal_interleaving(self):
        for seed in X02_SEEDS:
            noisy, _, commands2, rejections = game(seed, interleave=True)
            # The rng consumes extra draws when interleaving, so compare the replay of the
            # noisy run's own accepted commands on a clean session instead.
            replay = E.BattleSession.open(OPENINGS[seed % len(OPENINGS)])
            for c in commands2:
                self.assertIs(type(replay.submit(c)), E.Accepted)
            self.assertEqual(B.canonical_bytes(replay.state), B.canonical_bytes(noisy.state), seed)
            self.assertEqual(replay.journal, noisy.journal, seed)
            for kind, got, expected, same_input, same_session in rejections:
                self.assertIs(kind, E.Rejected, seed)
                self.assertIs(got, expected, seed)
                self.assertTrue(same_input and same_session, seed)


SCRIPT = r"""
import hashlib, importlib, importlib.util, json, sys
sys.path.insert(0, ".")
first, second = sys.argv[1:]
import imperium.battle as B
name = "imperium.battle.engine"
spec = importlib.util.find_spec(name)
engine = importlib.util.module_from_spec(spec)
sys.modules[name] = engine
for item in (first, second):
    importlib.import_module(name + "." + item)
observed = [k.rsplit(".", 1)[1] for k in sys.modules if k in (name + ".terminal", name + ".custody")]
assert observed == [first, second], observed
assert name + ".step" not in sys.modules and name + ".session" not in sys.modules
spec.loader.exec_module(engine)
from tests.engine.test_cross import game
h = hashlib.sha256()
for seed in range(0, 1000, 37):
    s, states, commands, _ = game(seed)
    # replay to capture stages per accepted command
    r = engine.BattleSession.open(states[0].scenario.provenance.fixture_id)
    for c in commands:
        res = r.submit(c)
        e = r.journal[-1]
        h.update(json.dumps(dict(cursor=e.cursor, cmd=e.command_digest, prev=e.previous,
                                 current=e.current, stages=[x.name for x in res.stages]),
                            sort_keys=True).encode())
        h.update(B.canonical_bytes(res.state))
    assert r.journal == s.journal
print("ORDER", first + "<" + second, h.hexdigest())
"""


class Determinism(unittest.TestCase):

    def test_x05_hash_seeds_and_import_orders(self):
        """PR5-03: two independent sibling modules (E1 terminal, E2 custody) imported in both
        orders before the facade initializes, under PYTHONHASHSEED 0 and 1; the full trace
        (cursor, command digest, previous, current, stages, every accepted state's bytes)
        must agree."""
        results = set()
        for first, second in (("terminal", "custody"), ("custody", "terminal")):
            for seed in ("0", "1"):
                env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": seed}
                out = subprocess.run([sys.executable, "-c", SCRIPT, first, second], cwd=ROOT,
                                     env=env, capture_output=True, text=True, check=True).stdout
                line = out.strip().splitlines()[-1]
                self.assertTrue(line.startswith(f"ORDER {first}<{second} "), out)
                results.add(line.split()[-1])
        self.assertEqual(len(results), 1, results)
