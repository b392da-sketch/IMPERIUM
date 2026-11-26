"""Layer E2: the capitulation custody transform (P2 contract 9.3; R3.6-10,
P1 8.2 and 8.5, U2).

It maps candidate field values to new field values. Lot ids, lineage,
counts and origins never change; only status, captured condition,
custody and the FIT lots' place do.
"""

import dataclasses

from imperium.battle.queries import BATTLEFIELD, Fields
from imperium.battle.records import InFormation, OnCell
from imperium.battle.values import (
    Assignment, CapturedCondition, Custody, Disposition, PersonnelStatus, Recovery, opponent,
)


def capitulate(values, side):
    """New field values after ``side`` capitulates; ``values`` is a dict."""
    fields = Fields(**values)
    winner = opponent(side)
    scope = {
        f.formation: f for f in fields.formations
        if fields.roster[f.formation].side is side and f.disposition in BATTLEFIELD
    }
    formations = tuple(
        dataclasses.replace(f, disposition=Disposition.SURRENDERED) if f.formation in scope else f
        for f in fields.formations
    )
    personnel = []
    for lot in fields.personnel:
        entry = fields.roster[lot.lineage]
        if entry.side is side and lot.status is PersonnelStatus.AVAILABLE \
                and type(lot.place) is InFormation and lot.lineage in scope:
            lot = dataclasses.replace(
                lot, status=PersonnelStatus.CAPTURED, captured=CapturedCondition.FIT,
                place=OnCell(scope[lot.lineage].cell), custodian=winner)
        elif entry.side is side and lot.status is PersonnelStatus.WOUNDED \
                and type(lot.place) is OnCell and lot.custodian is side:
            lot = dataclasses.replace(
                lot, status=PersonnelStatus.CAPTURED, captured=CapturedCondition.WOUNDED,
                custodian=winner)
        personnel.append(lot)

    def surrender_asset(record):
        f = scope.get(record.formation)
        if f is None:
            return record
        return dataclasses.replace(
            record, assignment=Assignment.UNASSIGNED_RECORDED, place=OnCell(f.cell),
            custodian=winner, custody=Custody.SURRENDERED_INVENTORY,
            recovery=Recovery.NOT_APPLICABLE)

    out = dict(values)
    out["formations"] = formations
    out["personnel"] = tuple(personnel)
    out["mounts"] = tuple(surrender_asset(m) for m in fields.mounts)
    out["ammunition"] = tuple(surrender_asset(a) for a in fields.ammunition)
    out["contacts"] = tuple(
        c for c in fields.contacts if c.low not in scope and c.high not in scope)
    return out
