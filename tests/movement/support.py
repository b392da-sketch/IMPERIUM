"""Shared literal carriers and assertions for the P4 acceptance suite.

Expected values are written in the tests or read from Codex's pinned
oracle files (CARRIER_ORACLES.json, REJECTION_ORACLES.json, los_oracle.py);
nothing here derives a checked value from engine code. Bare states are
literal P1 documents decoded through P1's decoder.
"""

import copy
import hashlib
import json
import pathlib

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.canon import canonical_bytes_of
from tests.battle.common import a1, cond, f, fr, place
from tests.engine.helpers import EngineCase
from tests.support.battle_builder import build

HERE = pathlib.Path(__file__).resolve().parent
S0, S1 = B.Side.S0, B.Side.S1
STANDARD = B.FixtureId("F01-v1-open-standard")
MIRRORED = B.FixtureId("F01-v1-open-mirrored")
ORACLE_DIGESTS = {
    "los_oracle.py": "51b1cdf616d82b042b048b842e183b728b6b57e72d9854b9abf41f938833b629",
    "carrier_oracles.json": "ebd19b538bf9849a00f45a5719c84971d85a5b292d6e2eaf9a777722b82319b8",
    "rejection_oracles.json": "ef2099b54d33afc176acba2984a8433e3e4e2bdc84bf74946ccc17dde4204dc5",
}
P2_STAGE_NAMES = ("ADVANCE", "CLOSURE_CHECK", "CLOSURE_DISPLACEMENT", "END_CHECK",
                  "IMMEDIATE_CHECK", "INITIAL_CHECK", "OPEN_ROUND", "RECOVERY", "ROOT",
                  "TERMINAL")
P4_STAGE_NAMES = ("STEP1", "STEP2", "STEP3", "WITHDRAW", "GROUP_STEP", "PIVOT", "GROUP_PIVOT",
                  "EVACUATE", "WINDOW", "RESPONSE")


def oracle_bytes(name):
    data = (HERE / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != ORACLE_DIGESTS[name]:
        raise AssertionError(f"{name} differs from the frozen oracle")
    return data


def carriers():
    return json.loads(oracle_bytes("carrier_oracles.json"))


def rejection_oracles():
    return json.loads(oracle_bytes("rejection_oracles.json"))


def cjson(tree):
    return json.dumps(tree, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fid(token):
    return B.FormationId(token)


def gid(token):
    return B.GroupId(token)


def hx(q, r):
    return B.Hex(q, r)


def side_of(token):
    return S0 if token.startswith("S0") else S1


def mv(token, *cells):
    return E.MoveOrder(side_of(token), fid(token), tuple(hx(*c) for c in cells))


def pv(token, turn, steps=1):
    return E.PivotOrder(side_of(token), fid(token), turn, steps)


def wd(token, cell):
    return E.WithdrawOrder(side_of(token), fid(token), hx(*cell))


def ev(token):
    return E.EvacuateOrder(side_of(token), fid(token))


def gm(group, members, direction):
    return E.GroupMoveOrder(side_of(group), gid(group), tuple(fid(m) for m in members), direction)


def gp(group, members, turn):
    return E.GroupPivotOrder(side_of(group), gid(group), tuple(fid(m) for m in members), turn)


def decision(doc, window_id=None):
    """A decision command from its document, optionally rebinding the token."""
    d = dict(doc)
    if window_id is not None:
        d["window_id"] = window_id
    return E.decode_command(cjson(d))


def doc(label="P4"):
    """Catalogue A1 (adversarial open-standard, awaiting S0 in round 1)."""
    return a1(label=label)


def state_of(d):
    return build(d)


def opened(fixture=STANDARD):
    s = E.BattleSession.open(fixture)
    s.submit(E.OpenBattle())
    return s


def run_carrier(name, upto=None, fixture=STANDARD):
    """A session replaying Codex's literal command stream for one carrier."""
    case = carriers()[name]
    s = E.BattleSession.open(fixture)
    rows = case["roots"] if upto is None else case["roots"][:upto]
    for row in rows:
        r = s.submit(E.decode_command(cjson(row["command"])))
        if type(r) is E.Suspended:
            r = s.submit(E.decode_command(cjson(row["decision"])))
        if type(r) is not E.Accepted:
            raise AssertionError(f"{name}: {r!r}"[:400])
    return s


def window_hash(base_digest, command, after):
    """Codex's ER02 formula, written independently of the engine."""
    command_hash = sha(cjson(E.encode_command(command)))
    return sha(cjson(["IMPERIUM-P4-window-1", base_digest, command_hash, after]))


def complete(state, command):
    """Resolve one P4 order, declining its window if one opens."""
    r = E.resolve(state, command)
    if type(r) is E.Suspended:
        w = r.root.window
        r = E.resolve(r.root, E.DeclineResponse(w.side, w.window_id))
    if type(r) is not E.Resolved:
        raise AssertionError(repr(r)[:400])
    return r


class MovementCase(EngineCase):

    def suspended(self, state, command):
        before = B.canonical_bytes(state)
        r = E.step(state, command)
        self.assertIs(type(r), E.Suspended, msg=repr(r)[:400])
        self.assertIs(r.root.base, state)
        self.assertIs(r.root.command, command)
        self.assertEqual(B.canonical_bytes(state), before)
        return r.root

    def window_rejected(self, root, command, code, path, detail):
        r = E.step(root, command)
        self.assertIs(type(r), E.WindowRejected, msg=repr(r)[:400])
        self.assertIs(r.root, root)
        self.assertIs(r.code, code)
        self.assertEqual((r.path, r.detail), (path, detail))
        return r

    def reject_at(self, state, command, code, path):
        detail = rejection_oracles()[code.name]["detail"] if code.name in rejection_oracles() \
            else None
        return self.rejected(state, command, code, path, detail)


__all__ = [n for n in dir() if not n.startswith("__")] + ["copy", "cond", "f", "fr", "place",
                                                          "canonical_bytes_of"]
