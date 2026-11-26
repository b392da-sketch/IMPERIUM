"""Catalogue seed fixtures as literal documents: Secure O0, the terminal
collapse and the terminal capitulation states (ACCEPTANCE_TEST_DESIGN.md,
"Exact fixture and oracle conventions").

Every count and summary below is written literally from the catalogue;
none is computed from package code.
"""

from tests.battle.common import (
    at_exit, f, fi, in_formation, on_cell, place, plot, set_asset_place, set_lots, terminal,
    unheld,
)
from tests.support.battle_builder import as_adversarial, opening_document

S1_CELLS = {
    "S1.H1": (8, 2), "S1.H2": (7, 2), "S1.H3": (6, 2), "S1.H4": (5, 2),
    "S1.H5": (7, 1), "S1.H6": (6, 1), "S1.L1": (6, 3), "S1.C1": (9, 2),
}
S0_CELLS = {
    "S0.H1": (2, 6), "S0.H2": (3, 6), "S0.H3": (4, 6), "S0.H4": (5, 6),
    "S0.H5": (3, 7), "S0.H6": (4, 7), "S0.L1": (4, 5), "S0.C1": (1, 6),
}
COUNTS = {"H": 240, "L": 120, "C": 80}


def count_of(fid):
    return COUNTS[fid.split(".")[1][0]]


def secure_o0(label="SECURE-O0"):
    d = as_adversarial(opening_document(), label)
    place(d, "S0.H1", (5, 4), 4)
    place(d, "S1.L1", (8, 3), 1)
    return d


def deadline_objective_victory(label="XT01"):
    d = secure_o0(label)
    d["clock"] = {"completed_rounds": 12, "event_cursor": 40}
    d["phase"] = terminal("DEADLINE_OBJECTIVE_VICTORY", "VICTORY", "S0", (None, None),
                          "ROUND_END", 12, {"kind": "SECURE", "side": "S0"},
                          ("CONTESTING", "CONTESTING"), (8, 8), (1640, 1640), (0, 0))
    return d


def collapse(label="COLLAPSE", point="ROUND_END", completed=5, charged=5):
    """S1 at zero viability with S1.H1 routing on the map."""
    d = as_adversarial(opening_document(), label)
    d["clock"] = {"completed_rounds": completed, "event_cursor": 20}
    f(d, "S1.H1")["disposition"] = "ROUTING"
    for fid, cell in S1_CELLS.items():
        if fid == "S1.H1":
            continue
        f(d, fid)["disposition"] = "DEPLETED"
        set_lots(d, fid, [plot(f"{fid}:D1", fid, count_of(fid), "DEAD", on_cell(*cell), None,
                               origin="EV-1")])
        set_asset_place(d, fid, "UNASSIGNED_RECORDED", on_cell(*cell), "S1", "OWN", "UNRESOLVED")
    d["phase"] = terminal("ZERO_VIABILITY_UNILATERAL", "VICTORY", "S0", (None, "COLLAPSE"),
                          point, charged, unheld(), ("CONTESTING", "CONTESTING"), (8, 0),
                          (1640, 240), (0, 0))
    return d


def capitulation(label="CAPITULATION"):
    """S1 capitulates after a root: S0 victory (catalogue terminal capitulation)."""
    d = as_adversarial(opening_document(), label)
    d["clock"] = {"completed_rounds": 3, "event_cursor": 30}
    # S1.H1 withdrawn at (8,0): 210 available at the S1 exit, 30 captured wounded at (8,2).
    place(d, "S1.H1", (8, 0), disposition="WITHDRAWN")
    set_lots(d, "S1.H1", [
        plot("S1.H1:P0", "S1.H1", 210, "AVAILABLE", at_exit("S1"), "S1"),
        plot("S1.H1:W1", "S1.H1", 30, "CAPTURED", on_cell(8, 2), "S0", captured="WOUNDED",
             origin="EV-1"),
    ])
    set_asset_place(d, "S1.H1", "ASSIGNED", at_exit("S1"), "S1", "OWN", "NOT_APPLICABLE")
    # S1.H2 depleted at (7,2): 240 dead there, stock recorded there in own custody.
    f(d, "S1.H2")["disposition"] = "DEPLETED"
    set_lots(d, "S1.H2", [plot("S1.H2:D1", "S1.H2", 240, "DEAD", on_cell(7, 2), None,
                               origin="EV-2")])
    set_asset_place(d, "S1.H2", "UNASSIGNED_RECORDED", on_cell(7, 2), "S1", "OWN", "UNRESOLVED")
    # The rest surrendered: fit lots captured at their own cells, stock to S0 inventory.
    for fid, cell in S1_CELLS.items():
        if fid in ("S1.H1", "S1.H2"):
            continue
        f(d, fid)["disposition"] = "SURRENDERED"
        set_lots(d, fid, [plot(f"{fid}:P0", fid, count_of(fid), "CAPTURED", on_cell(*cell), "S0",
                               captured="FIT")])
        set_asset_place(d, fid, "UNASSIGNED_RECORDED", on_cell(*cell), "S0",
                        "SURRENDERED_INVENTORY", "NOT_APPLICABLE")
    d["phase"] = terminal("CAPITULATION", "VICTORY", "S0", (None, "CAPITULATED"), "AFTER_ROOT", 4,
                          unheld(), ("CONTESTING", "CONTESTING"), (8, 0), (1640, 0), (0, 210))
    return d


__all__ = ["secure_o0", "deadline_objective_victory", "collapse", "capitulation", "S0_CELLS",
           "S1_CELLS", "count_of", "fi", "in_formation"]
