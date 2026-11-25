"""D4.7 deterministic preferred-action subset using the public resolver."""

from .displacement import FrozenField
from .geometry import OBJECTIVE, distance, front, mirror, rear, step
from .scheduler import Action


def choose(battle, policy, released):
    if policy == "PASS":
        return Action("pass"), 0, released
    units = battle.ordered()
    allies = [f for f in units if f.identity.logical_side == battle.side]
    foes = [f for f in units if f.identity.logical_side != battle.side and f.position is not None]
    viable = [f for f in foes if battle.viable(f)]
    released = released or any(
        not battle.viable(f) or f.cohesion or f.morale or f.fatigue == 2 for f in allies[:4]
    ) or any(distance(f.position, OBJECTIVE) <= 1 for f in viable)
    ranks = {
        "AGG": ("assault", "move", "pivot", "rally", "rest", "withdraw"),
        "ADV": ("centre_recovery", "centre_assault", "move", "assault", "rally", "rest", "withdraw", "pivot"),
        "RES": ("withdraw", "rally", "rest", "centre_assault", "move", "assault", "pivot"),
    }[policy]
    choices = []
    field = FrozenField.capture(battle.encounter)
    for unit in allies:
        if not unit.principal_eligibility:
            continue
        i, role, origin = unit.identity.formation_id, unit.identity.local_role, unit.position
        reserve = policy == "RES" and role >= 4 and not released
        directions = front(unit.facing)
        destinations = [f.position for f in viable] if policy == "AGG" and viable else [OBJECTIVE]

        def score(cell):
            return min(distance(cell, target) for target in destinations)

        def add(action, category, ranking, endpoint=origin):
            try:
                battle.cost(action, field)
            except ValueError:
                return
            normalized = mirror(endpoint) if unit.physical_side else endpoint
            choices.append(((ranks.index(category), *ranking, role, normalized), action))

        for kind, severity in (("rally", unit.cohesion + unit.morale), ("rest", unit.fatigue)):
            category = "centre_recovery" if policy == "ADV" and origin == OBJECTIVE else kind
            rank = (-severity, distance(origin, OBJECTIVE))
            if category == "centre_recovery":
                rank = (int(kind == "rest"), *rank)
            add(Action(kind, i), category, rank)
        if reserve:
            continue
        for target in foes:
            category = "centre_assault" if policy != "AGG" and target.position == OBJECTIVE else "assault"
            add(Action("assault", i, target=target.identity.formation_id), category,
                (distance(target.position, OBJECTIVE), -min(unit.available_personnel, 24),
                 -target.available_personnel, target.identity.local_role))
        for d in directions:
            first = step(origin, d)
            for path in ((first,), *((first, step(first, e)) for e in directions)):
                end = path[-1]
                improvement = score(origin) - score(end)
                if improvement > 0:
                    add(Action("move", i, path), "move",
                        (-improvement, len(path), distance(end, OBJECTIVE)), end)
        if sum(distance(origin, f.position) == 1 for f in viable) <= 1:
            baseline = min(score(step(origin, d)) for d in directions)
            for turn in (-1, 1):
                best = min(score(step(origin, d)) for d in front(unit.facing + turn))
                if best < baseline:
                    add(Action("pivot", i, turn=turn), "pivot", (best, turn))
        if max(unit.cohesion, unit.morale, unit.fatigue) == 2:
            for d in rear(unit.facing):
                cell = step(origin, d)
                nearest = min((distance(cell, f.position) for f in foes), default=99)
                if nearest > 1:
                    add(Action("withdraw", i, (cell,)), "withdraw",
                        (-nearest, distance(cell, OBJECTIVE)), cell)
    return (min(choices, key=lambda item: item[0])[1] if choices else Action("pass"),
            len(choices), released)
