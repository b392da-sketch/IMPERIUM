"""Emit the accepted P2 states for the golden carriers, from a pinned P2 tree.

Run with ``python -I -s p2_states.py`` and the working directory set to an
extracted ``git archive`` of the accepted P2 runtime (5dcfd5d). The P3 C02
oracle takes stable states and stage names from this output, so its
expectations do not come from the P3 code under test.
"""

import json
import os
import sys

sys.path.insert(0, os.getcwd())

import imperium.battle as B  # noqa: E402
from imperium.battle import engine as E  # noqa: E402

assert not hasattr(E, "resolve"), "not a P2 tree"
S0, S1 = B.Side.S0, B.Side.S1
STANDARD = "F01-v1-open-standard"


def g4():
    out = [E.OpenBattle()]
    for rnd in range(1, 13):
        first, second = (S0, S1) if rnd % 2 else (S1, S0)
        out += [E.PassOrder(first), E.PassOrder(second)]
    return out


CARRIERS = {
    "G0": ("F01-v1-defensive-mutual-capitulation", []),
    "G1": (STANDARD, [E.OpenBattle(), E.HoldOrder(S0, B.FormationId("S0.H1")), E.PassOrder(S1),
                      E.PassOrder(S0)]),
    "G2": (STANDARD, [E.OpenBattle(), E.DeclareWithdrawal(S0)]),
    "G3": (STANDARD, [E.OpenBattle(), E.Capitulate(S0)]),
    "G4": (STANDARD, g4()),
}


def doc(state):
    return json.loads(B.canonical_bytes(state))


out = {}
for name, (token, commands) in CARRIERS.items():
    s = E.BattleSession.open(B.FixtureId(token))
    roots = []
    for c in commands:
        r = s.submit(c)
        assert type(r) is E.Accepted, (name, c)
        roots.append({"command": E.encode_command(c), "stages": [x.name for x in r.stages],
                      "after": doc(r.state)})
    out[name] = {"fixture": token, "genesis": doc(E.BattleSession.open(B.FixtureId(token)).state),
                 "roots": roots}
json.dump(out, sys.stdout, sort_keys=True)
