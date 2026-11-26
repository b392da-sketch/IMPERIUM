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
from tests.engine.helpers import OPENINGS, S0, S1, EngineCase

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
        pf = {f.formation: f for f in prev.formations}
        for f in cur.formations:
            p = pf[f.formation]
            if p.disposition in ABSORBING:                       # ML1
                self.assertIs(f.disposition, p.disposition, seed)
            self.assertGreaterEqual(f.condition.fatigue, p.condition.fatigue, seed)   # ML3
        def avail(st):
            out = {}
            for l in st.personnel:
                if l.status is B.PersonnelStatus.AVAILABLE:
                    out[l.lineage] = out.get(l.lineage, 0) + l.count
            return out
        pa, ca = avail(prev), avail(cur)
        for k, v in ca.items():                                   # ML4a
            self.assertLessEqual(v, pa.get(k, 0), seed)
        def stock(st):
            out = {}
            for m in st.mounts:
                if m.serviceability is B.Serviceability.SERVICEABLE:
                    out[m.formation] = out.get(m.formation, 0) + m.count
            return out
        self.assertEqual(stock(prev), stock(cur), seed)           # ML4b
        same_round = (type(prev.phase) is B.AwaitingPrincipal and type(cur.phase) is B.AwaitingPrincipal
                      and prev.clock.completed_rounds == cur.clock.completed_rounds)
        if same_round:                                            # ML2, ML5
            pr = {r.formation: r for r in prev.ledger.formations}
            for r in cur.ledger.formations:
                q = pr[r.formation]
                self.assertTrue(q.safe_latch or not r.safe_latch, seed)
                for flag in ("incoming", "exerted", "displaced", "displacement_attempted"):
                    self.assertTrue(getattr(r, flag) or not getattr(q, flag), seed)
                if q.response is not None:
                    self.assertEqual(r.response, q.response, seed)
            for f in cur.formations:
                if f.disposition is B.Disposition.REFORMING:
                    self.assertIs(pf[f.formation].disposition, B.Disposition.REFORMING, seed)
        if type(cur.phase) is B.AwaitingPrincipal:                # ML6
            rounds = {r.formation: r for r in cur.ledger.formations}
            for f in cur.formations:
                if f.disposition in (B.Disposition.ORGANIZED, B.Disposition.REFORMING):
                    self.assertTrue(rounds[f.formation].opened_eligible, seed)

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
import importlib, sys, hashlib
order = sys.argv[1].split(",")
for name in order:
    importlib.import_module("imperium.battle.engine." + name)
import imperium.battle as B
from imperium.battle import engine as E
sys.path.insert(0, ".")
from tests.engine.test_cross import game
h = hashlib.sha256()
for seed in range(0, 1000, 37):
    s, states, commands, _ = game(seed)
    for e in s.journal:
        h.update((e.command_digest + e.previous + e.current).encode())
    h.update(B.canonical_bytes(s.state))
print("ORDER", sys.argv[1], h.hexdigest())
"""


class Determinism(unittest.TestCase):

    def test_x05_hash_seeds_and_import_orders(self):
        results = set()
        for order in ("commands,terminal,custody,rounds,step,session",
                      "session,step,rounds,custody,terminal,commands"):
            for seed in ("0", "1"):
                env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": seed}
                out = subprocess.run([sys.executable, "-c", SCRIPT, order], cwd=ROOT, env=env,
                                     capture_output=True, text=True, check=True).stdout
                line = out.strip().splitlines()[-1]
                self.assertTrue(line.startswith("ORDER " + order), out)
                results.add(line.split()[-1])
        self.assertEqual(len(results), 1, results)
