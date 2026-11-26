"""Independent primitive fixture documents (contract 11.4, 11.5.1, 13.5).

This module builds the eight registered genesis documents as plain JSON
trees, directly from the field declarations of 5.5, 6.1–6.4 and 13.5 and
the literal data of 11.3 and 11.5. It imports nothing from
``imperium.battle``: it is the oracle against which the package's
builder, decoder and descriptor constants are checked.

Provenance of this oracle: it was written by the implementer from the
frozen contract text, without calling package code. It is therefore an
implementer-side oracle, not one prepared by the independent reviewer;
the reviewer is asked to check it against 11.5.1 directly.
"""

import copy
import hashlib
import json

SCHEMA = "imperium.battle-state/1"
ZERO_DIGEST = "0" * 64
SOURCES = [
    "6a831d4a08db660e0e6cd15e0d023fd585e83bd7d1387cac6405d4981e382da5",
    "d01c2bb10f0f1074f7f18f0270e434fb9548867a4e007215b6daefcc73a72534",
    "a89fea614e1b9e76c7b5add120a4b0359aef2cf87a0938c5e0dc133162b70e7e",
]

# 11.5: (position, template, standard S0 cell)
S0_STANDARD = [
    ("H1", "HEAVY", (2, 6)),
    ("H2", "HEAVY", (3, 6)),
    ("H3", "HEAVY", (4, 6)),
    ("H4", "HEAVY", (5, 6)),
    ("H5", "HEAVY", (3, 7)),
    ("H6", "HEAVY", (4, 7)),
    ("L1", "LIGHT", (4, 5)),
    ("C1", "MOUNTED", (1, 6)),
]
PERSONNEL = {"HEAVY": 240, "LIGHT": 120, "MOUNTED": 80}
AMMUNITION = {"HEAVY": 2, "LIGHT": 4, "MOUNTED": 0}
GROUPS = [("G1", ["H1", "H2", "H5"]), ("G2", ["H3", "H4", "H6"])]

CANONICAL = [
    ("open", "OPEN", "standard", "STANDARD"),
    ("open", "OPEN", "mirrored", "MIRRORED"),
    ("rough", "ROUGH", "standard", "STANDARD"),
    ("rough", "ROUGH", "mirrored", "MIRRORED"),
    ("barrier", "BARRIER", "standard", "STANDARD"),
    ("barrier", "BARRIER", "mirrored", "MIRRORED"),
]
SHORTFALL_ID = "F01-v1-open-standard-mount-shortfall"
DEFENSIVE_ID = "F01-v1-defensive-mutual-capitulation"


def point_mirror(cell):
    return (10 - cell[0], 8 - cell[1])


def template(kind, personnel, mounts, ammunition, frontage, pitch, capacity, missile_range,
             max_steps, open_cost, rough_cost, melee, fallback):
    return {
        "kind": kind, "personnel": personnel, "mounts": mounts, "ammunition": ammunition,
        "frontage_dm": frontage, "pitch_dm": pitch, "edge_capacity": capacity,
        "missile_range": missile_range, "max_steps": max_steps, "open_cost": open_cost,
        "rough_cost": rough_cost, "melee_capable": melee, "foot_fallback": fallback,
    }


def profile():
    return {
        "profile_id": "D4-RP-0.1",
        "templates": [
            template("HEAVY", 240, 0, 2, 600, 15, 24, 1, 2, 1, 2, True, None),
            template("LIGHT", 120, 0, 4, 450, 20, 18, 2, 2, 1, 1, True, None),
            template("MOUNTED", 80, 80, 0, 600, 30, 12, None, 3, 1, 3, True, "HEAVY"),
        ],
        "opportunities": 4,
        "effort": 3,
        "principal_per_round": 1,
        "responses_per_round": 1,
        "responses_per_root": 1,
        "exertion_threshold": 6,
        "exertion_carry": True,
        "exertion_cleared_by": "COMPLETED_REST",
        "displacement_attempts": 1,
        "rounds": 12,
        "round_minutes": 10,
        "hex_pitch_m": 65,
        "packet": {
            "melee_p0": "1/10",
            "missile_p0": "1/20",
            "fatal_share": "1/4",
            "melee_pressure": ["1/5", "3/20"],
            "missile_pressure": ["3/25", "1/10"],
            "melee_a_ref": 24,
            "missile_a_ref": 40,
            "allocation": "B",
            "injury": "B1",
            "exposure": "E1",
            "pressure": "I1",
        },
    }


def board(variant):
    rough = {(2, 4), (8, 4)} if variant == "ROUGH" else set()
    terrain = []
    for q in range(11):
        for r in range(9):
            terrain.append([[q, r], "ROUGH" if (q, r) in rough else "OPEN"])
    edges = []
    if variant == "BARRIER":
        for s, d in [((3, 4), (4, 4)), ((4, 4), (3, 4)), ((6, 4), (7, 4)), ((7, 4), (6, 4))]:
            edges.append({
                "source": [s[0], s[1]], "destination": [d[0], d[1]],
                "traversable": False, "opaque": False, "surcharge": 0,
            })
    return {"width": 11, "height": 9, "terrain": terrain, "edges": edges, "objective": [5, 4]}


def ids_by_token(items, key):
    return sorted(items, key=key)


def opening(variant_token, orientation_token, fixture_class, fixture_id):
    """The primitive genesis document, with a 64-zero ``origin_digest``."""
    mirrored = orientation_token == "MIRRORED"
    roster = []
    formations = []
    personnel = []
    mounts = []
    ammunition = []
    for side in ("S0", "S1"):
        for pos, kind, s0_cell in S0_STANDARD:
            fid = f"{side}.{pos}"
            roster.append({"formation": fid, "side": side, "template": kind})
            standard_cell = s0_cell if side == "S0" else point_mirror(s0_cell)
            cell = point_mirror(standard_cell) if mirrored else standard_cell
            if mirrored:
                facing = 1 if side == "S0" else 4
            else:
                facing = 4 if side == "S0" else 1
            formations.append({
                "formation": fid, "disposition": "ORGANIZED", "cell": [cell[0], cell[1]],
                "facing": facing,
                "condition": {"cohesion": 0, "morale": 0, "fatigue": 0, "exertion": 0},
            })
            personnel.append({
                "lot": f"{fid}:P0", "lineage": fid, "count": PERSONNEL[kind],
                "status": "AVAILABLE", "captured": None,
                "place": {"kind": "InFormation", "formation": fid},
                "custodian": side, "origin": None,
            })
            if kind == "MOUNTED":
                mounts.append({
                    "lot": f"{fid}:M0", "formation": fid, "count": 80,
                    "serviceability": "SERVICEABLE", "assignment": "ASSIGNED",
                    "place": {"kind": "InFormation", "formation": fid},
                    "custodian": side, "custody": "OWN", "recovery": "NOT_APPLICABLE",
                })
            if AMMUNITION[kind]:
                ammunition.append({
                    "formation": fid, "carried": AMMUNITION[kind], "expended": 0,
                    "assignment": "ASSIGNED",
                    "place": {"kind": "InFormation", "formation": fid},
                    "custodian": side, "custody": "OWN", "recovery": "NOT_APPLICABLE",
                })
    roster = ids_by_token(roster, lambda e: e["formation"])
    formations = ids_by_token(formations, lambda e: e["formation"])
    personnel = ids_by_token(personnel, lambda e: e["lot"])
    mounts = ids_by_token(mounts, lambda e: e["lot"])
    ammunition = ids_by_token(ammunition, lambda e: e["formation"])
    groups = []
    for side in ("S0", "S1"):
        for g, members in GROUPS:
            groups.append({
                "group": f"{side}.{g}", "side": side,
                "members": sorted(f"{side}.{m}" for m in members),
            })
    groups = ids_by_token(groups, lambda e: e["group"])
    return {
        "schema": SCHEMA,
        "scenario": {
            "provenance": {
                "scenario_id": "F01",
                "scenario_version": "F01-v1",
                "variant": variant_token,
                "orientation": orientation_token,
                "profile_id": "D4-RP-0.1",
                "rules_baseline": "D3-v0.2+A01-A25",
                "sources": list(SOURCES),
                "fixture_class": fixture_class,
                "fixture_id": fixture_id,
                "origin_digest": ZERO_DIGEST,
            },
            "profile": profile(),
            "board": board(variant_token),
            "roster": roster,
            "groups": groups,
            "first_side": "S0",
        },
        "phase": {"kind": "Opening"},
        "clock": {"completed_rounds": 0, "event_cursor": 0},
        "sides": [{"side": "S0", "posture": "CONTESTING"}, {"side": "S1", "posture": "CONTESTING"}],
        "formations": formations,
        "authority": [[g["group"], "ACTIVE"] for g in groups],
        "personnel": personnel,
        "mounts": mounts,
        "ammunition": ammunition,
        "contacts": [],
        "ledger": None,
    }


def canonical(tree):
    return json.dumps(tree, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def seal(zeroed):
    """11.2 construction order: N from the zeroed document, insert N, then F."""
    assert zeroed["scenario"]["provenance"]["origin_digest"] == ZERO_DIGEST
    n = sha(canonical(zeroed))
    sealed = copy.deepcopy(zeroed)
    sealed["scenario"]["provenance"]["origin_digest"] = n
    f = sha(canonical(sealed))
    return sealed, n, f


def zeroed_documents():
    """The eight zeroed primitive genesis documents, in descriptor order."""
    docs = []
    for v, vt, o, ot in CANONICAL:
        docs.append((f"F01-v1-{v}-{o}", opening(vt, ot, "CANONICAL_OPENING", f"F01-v1-{v}-{o}")))
    shortfall = opening("OPEN", "STANDARD", "SUPPLIED_VALIDATION", SHORTFALL_ID)
    shortfall["mounts"] = [
        m for m in shortfall["mounts"] if m["formation"] != "S0.C1"
    ] + [
        {
            "lot": "S0.C1:M0", "formation": "S0.C1", "count": 70,
            "serviceability": "SERVICEABLE", "assignment": "ASSIGNED",
            "place": {"kind": "InFormation", "formation": "S0.C1"},
            "custodian": "S0", "custody": "OWN", "recovery": "NOT_APPLICABLE",
        },
        {
            "lot": "S0.C1:M1", "formation": "S0.C1", "count": 10,
            "serviceability": "UNSERVICEABLE", "assignment": "ASSIGNED",
            "place": {"kind": "InFormation", "formation": "S0.C1"},
            "custodian": "S0", "custody": "OWN", "recovery": "NOT_APPLICABLE",
        },
    ]
    shortfall["mounts"].sort(key=lambda m: m["lot"])
    docs.append((SHORTFALL_ID, shortfall))
    defensive = opening("OPEN", "STANDARD", "SUPPLIED_VALIDATION", DEFENSIVE_ID)
    defensive["phase"] = {
        "kind": "Terminal",
        "record": {
            "reason": "MUTUAL_CAPITULATION",
            "result": "UNRESOLVED",
            "winner": None,
            "defeat": ["CAPITULATED", "CAPITULATED"],
            "point": "INITIAL_CHECK",
            "charged_rounds": 0,
            "objective": {"kind": "UNHELD", "side": None},
            "postures": ["CONTESTING", "CONTESTING"],
            "viable": [8, 8],
            "onmap_available": [1640, 1640],
            "exit_available": [0, 0],
        },
    }
    docs.append((DEFENSIVE_ID, defensive))
    return docs


def sealed_documents():
    """``[(fixture_id, sealed_document, N, F), ...]`` in descriptor order."""
    out = []
    for fid, doc in zeroed_documents():
        sealed, n, f = seal(doc)
        out.append((fid, sealed, n, f))
    return out


if __name__ == "__main__":
    for fid, _, n, f in sealed_documents():
        print(fid, n, f)
