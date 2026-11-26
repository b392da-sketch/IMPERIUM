"""Shared, independently written helpers for the P3 acceptance suite.

The serializer, chain, patcher and EP08 arithmetic here are test-side
implementations: they import nothing from the producer (``engine.events``,
``engine.session``) or from the audit package, so expected values are not
taken from the code under test.
"""

import hashlib
import json
import os

import imperium.battle as B
from imperium.battle import engine as E
from tests.engine.helpers import OPENINGS, STANDARD, DEFENSIVE

S0, S1 = B.Side.S0, B.Side.S1
FULL = os.environ.get("IMPERIUM_FULL_RANDOM") == "1"
SEEDS = range(1000)
WALK_SEEDS = SEEDS if FULL else range(0, 1000, 4)
HOLDOUT = (range(10000, 14096), range(30000, 31024))
RUN0 = E.RunKey(0, 0)
ORACLES = os.path.join(os.path.dirname(__file__), "reference_oracles.json")


def allowed_seed(seed):
    """Runtime allowlist (TA-I04): development seeds 0–999 only."""
    if type(seed) is not int or not 0 <= seed <= 999 or any(seed in r for r in HOLDOUT):
        raise AssertionError(f"seed {seed!r} outside the development allowlist")
    return seed


def fid(token):
    return B.FormationId(token)


def hold(side, token):
    return E.HoldOrder(side, fid(token))


# ---------------------------------------------------------------- serializer


def cjson(tree):
    """Canonical P1 13.4 JSON, written test-side."""
    return json.dumps(tree, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def chained(trees):
    """Serialize line trees (without ``chain``) into journal bytes."""
    out, link = [], None
    for t in trees:
        t = {k: v for k, v in t.items() if k != "chain"}
        b = cjson(t)
        link = sha(b if link is None else link.encode("ascii") + b)
        t["chain"] = link
        out.append(cjson(t) + b"\n")
    return b"".join(out)


def trees(data):
    return [json.loads(line) for line in data.split(b"\n")[:-1]]


def rechain(data, mutate):
    """Apply ``mutate(list_of_trees)`` and rebuild the chain."""
    ts = trees(data)
    mutate(ts)
    return chained(ts)


def final_chain(data):
    return trees(data)[-1]["chain"]


# ---------------------------------------------------------------- patcher


def segments(pointer):
    return [s.replace("~1", "/").replace("~0", "~") for s in pointer[1:].split("/")]


def patch(doc, pointer, value):
    """Return a deep-copied document with one location replaced."""
    doc = json.loads(cjson(doc))
    node = doc
    segs = segments(pointer)
    for s in segs[:-1]:
        node = node[int(s)] if type(node) is list else node[s]
    last = segs[-1]
    if type(node) is list:
        node[int(last)] = value
    else:
        node[last] = value
    return doc


def put(doc, pointer, value):
    """Replace one existing location in place."""
    node = doc
    segs = segments(pointer)
    for s in segs[:-1]:
        node = node[int(s)] if type(node) is list else node[s]
    if type(node) is list:
        node[int(segs[-1])] = value
    else:
        if segs[-1] not in node:
            raise KeyError(pointer)
        node[segs[-1]] = value


def refold(doc, events):
    """Test-local refold: each event's effects in order; returns snapshot docs."""
    out = []
    for e in events:
        doc = json.loads(cjson(doc))
        for eff in e["effects"]:
            put(doc, eff["path"], json.loads(cjson(eff["new"])))
        out.append(doc)
    return out


# ---------------------------------------------------------------- EP08


def ep08(seed, pair, replicate, stage, channel, index):
    """Test-local EP08: the 53 high bits of SHA-256, from the full integer."""
    payload = json.dumps(["D4-SHA256-v1", seed, pair, replicate, stage, channel, index],
                         separators=(",", ":")).encode()
    return int(hashlib.sha256(payload).hexdigest(), 16) >> (256 - 53)


def oracles():
    with open(ORACLES, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- carriers


def g4_commands():
    out = [E.OpenBattle()]
    for rnd in range(1, 13):
        first, second = (S0, S1) if rnd % 2 else (S1, S0)
        out += [E.PassOrder(first), E.PassOrder(second)]
    return out


CARRIERS = {
    "G1": (STANDARD, lambda: [E.OpenBattle(), hold(S0, "S0.H1"), E.PassOrder(S1), E.PassOrder(S0)]),
    "G2": (STANDARD, lambda: [E.OpenBattle(), E.DeclareWithdrawal(S0)]),
    "G3": (STANDARD, lambda: [E.OpenBattle(), E.Capitulate(S0)]),
    "G4": (STANDARD, g4_commands),
    "G0": (DEFENSIVE, lambda: []),
}


def session(name, run=RUN0):
    fixture, commands = CARRIERS[name]
    s = E.BattleSession.open(fixture, run)
    for c in commands():
        r = s.submit(c)
        if type(r) is not E.Accepted:
            raise AssertionError(f"{name}: {c} gave {r!r}"[:200])
    return s


def journals(name, run=RUN0):
    s = session(name, run)
    return s.export_audit(seal=True), s.export_audit(seal=False)


# ---------------------------------------------------------------- walks


_WALKS = {}


def walk(seed, run=RUN0, interleave=False):
    """The P2 X01 walk for ``seed`` (seven openings, cycled), with a run key.

    Returns ``(session, commands, rejections)``; cached per process.
    """
    from tests.engine.test_cross import choose, illegal_proposals, legal_commands
    import random

    key = (allowed_seed(seed), run, interleave)
    if key in _WALKS:
        return _WALKS[key]
    rng = random.Random(seed)
    s = E.BattleSession.open(OPENINGS[seed % len(OPENINGS)], run)
    commands, rejections = [], []
    while True:
        legal = legal_commands(s.state)
        if not legal:
            break
        if interleave:
            for c, code in illegal_proposals(s.state):
                if rng.random() < 0.5:
                    r = s.submit(c)
                    rejections.append((c, type(r), getattr(r, "code", None), code))
        c = choose(rng, legal)
        r = s.submit(c)
        if type(r) is not E.Accepted:
            raise AssertionError(f"seed {seed}: legal {c} gave {r!r}"[:300])
        commands.append(c)
    if not interleave:
        _WALKS[key] = (s, commands, rejections)
    return s, commands, rejections


def b02_witness():
    """ER06: OpenBattle, Pass(S0), then S1's closing Pass in round 1."""
    s = E.BattleSession.open(STANDARD, RUN0)
    for c in (E.OpenBattle(), E.PassOrder(S0), E.PassOrder(S1)):
        assert type(s.submit(c)) is E.Accepted
    return s


__all__ = ["OPENINGS", "STANDARD", "DEFENSIVE"]
