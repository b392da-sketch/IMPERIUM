"""Authoritative standalone F01 action and stage resolver."""

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import combinations, product

from ..condition import assess, exert
from ..displacement import arbitrate
from ..events import canonical_json
from ..geometry import HEIGHT, OBJECTIVE, Hex, distance, front, in_bounds, mirror, rear, step
from ..profiles import F6
from .combat import contribution, effect_key, packet
from .fixture import FIXTURE_VERSION, Formation, initial_formations, initial_groups
from .movement import group_translation, path_cost
from .terrain import BARRIER, OPEN, ROUGH, in_front_sector

TERRAINS = {"open": OPEN, "rough": ROUGH, "barrier": BARRIER}
SCHEMA = "F01-events-v1"


@dataclass(frozen=True)
class Order:
    kind: str
    members: tuple[int, ...] = ()
    path: tuple[Hex, ...] = ()
    turn: int = 0
    target: int | None = None


@dataclass(frozen=True)
class Reaction:
    kind: str
    source: int
    target: int
    turn: int = 0


@dataclass(frozen=True)
class Holding:
    cell: Hex
    custodian: int
    available: int
    mounts: int
    ammunition: int
    wounded_in_custody: int = 0


@dataclass(frozen=True)
class PublicFormation:
    identifier: int
    side: int
    position: Hex
    facing: int
    available: int
    mounts: int
    ammunition: int
    cohesion: int
    morale: int
    fatigue: int
    disposition: str


@dataclass(frozen=True)
class Observation:
    round: int
    side: int
    formations: tuple[PublicFormation, ...]
    own_effort: tuple[tuple[int, int], ...]
    own_ready: tuple[int, ...]
    own_response: tuple[int, ...]
    own_losses: tuple[tuple[int, int, int], ...]
    contacts: tuple[tuple[int, int], ...]
    posture: tuple[bool, bool]


class F01:
    def __init__(self, seed, variant="open", *, mirrored=False, formations=None):
        if type(seed) is not int or seed < 0 or 10000 <= seed <= 14095 or 30000 <= seed <= 31023:
            raise ValueError("invalid or reserved F01 seed")
        self.seed, self.variant, self.mirrored = seed, variant, mirrored
        self.terrain = TERRAINS[variant]
        roster = tuple(deepcopy(formations)) if formations is not None else initial_formations(mirrored)
        self.units = {u.identity.id: u for u in sorted(roster, key=lambda unit: unit.identity.id)}
        if len(self.units) != len(roster):
            raise ValueError("duplicate initial formation identity")
        self.population = {i: self.personnel(u) for i, u in self.units.items()}
        self.initial_stock = sum(u.ammunition for u in roster)
        self.initial_mounts = sum(u.mounts for u in roster)
        self.exits, self.custody, self.wound_custody, self.removed_assets = {}, {}, {}, {}
        self.contacts = set()
        self.withdrawing = [False, False]
        self.spent_ammunition = 0
        self.round = self.elapsed = self.root = self.side = 0
        self.terminal = None
        self.used, self.passed = [0, 0], [False, False]
        self.used_members, self.responded = set(), set()
        self.effort, self.ready = dict.fromkeys(self.units, 0), set()
        self.forced, self.displaced, self.resting, self.incoming, self.safe_interval = (
            set(), set(), set(), set(), set()
        )
        self.events, self.stages, self.waves = [], [], set()
        self.metrics = Counter()
        self.objectives = []
        self.round_three_exhaustion = None
        self._resolving = self._faulted = False
        self.rejections = []
        self.active_this_round = False
        before = self.digest()
        self.adjudicate()
        if not self.terminal:
            self.open_round()
        self.check_invariants()
        self.events.append({"schema": SCHEMA, "kind": "initial", "before": before,
                            "after": self.digest(), "terminal": self.terminal})

    @staticmethod
    def personnel(unit):
        return unit.available + sum(lot.casualties.killed + lot.casualties.wounded
                                    for lot in unit.losses)

    @staticmethod
    def viable(unit):
        return unit.position is not None and unit.available > 0 and unit.disposition in (
            "organized", "reforming"
        )

    def open_round(self):
        self.round += 1
        self.active_this_round = False
        self.side = (self.round - 1) % 2
        self.used, self.passed = [0, 0], [False, False]
        self.ready = {i for i, u in self.units.items() if self.viable(u)}
        self.effort = {i: 3 if i in self.ready else 0 for i in self.units}
        for ledger in (self.used_members, self.responded, self.forced, self.displaced,
                       self.resting, self.incoming):
            ledger.clear()
        self.safe_interval = {i for i in self.units if self.safe(i)}

    def links(self, i):
        return tuple(edge for edge in self.contacts if i in edge)

    def unlink(self, i):
        self.contacts.difference_update(self.links(i))

    @property
    def occupied(self):
        return frozenset(u.position for u in self.units.values() if u.position is not None)

    def enemies(self, i):
        side = self.units[i].identity.logical_side
        return tuple(j for j, u in self.units.items()
                     if u.position is not None and u.identity.logical_side != side)

    def projected(self, i):
        u = self.units[i]
        if u.position is None or u.disposition != "organized" or max(u.cohesion, u.morale) > 1:
            return frozenset()
        return frozenset(cell for d in front(u.facing) if (
            self.terrain.entry_cost(u, u.position, cell := step(u.position, d)) is not None
        ))

    def hostile_threat(self, side):
        return frozenset().union(*(self.projected(i) for i, u in self.units.items()
                                   if u.identity.logical_side != side))

    def adjacent_enemies(self, i):
        cell = self.units[i].position
        return tuple(j for j in self.enemies(i)
                     if cell is not None and distance(cell, self.units[j].position) == 1)

    def safe(self, i):
        return self.units[i].position is not None and not (self.links(i) or self.adjacent_enemies(i))

    def checkpoint(self):
        self.safe_interval.intersection_update(i for i in self.units if self.safe(i))

    def mark(self, i, amount):
        u = self.units[i]
        u.fatigue, u.exertion = exert(u.fatigue, u.exertion, amount, F6)
        self.safe_interval.discard(i)

    def observe(self, side):
        visible = tuple(PublicFormation(i, u.identity.logical_side, u.position, u.facing,
                                       u.available, u.mounts, u.ammunition, u.cohesion, u.morale,
                                       u.fatigue, u.disposition)
                        for i, u in self.units.items() if u.position is not None)
        own = tuple(i for i, u in self.units.items() if u.identity.logical_side == side)
        return Observation(self.round, side, visible, tuple((i, self.effort[i]) for i in own),
                           tuple(i for i in own if i in self.ready),
                           tuple(i for i in own if i not in self.responded and self.effort[i] > 0
                                 and self.units[i].position is not None
                                 and self.units[i].disposition == "organized"),
                           tuple((i, sum(lot.casualties.killed for lot in self.units[i].losses),
                                  sum(lot.casualties.wounded for lot in self.units[i].losses))
                                 for i in own),
                           tuple(sorted(self.contacts)), tuple(self.withdrawing))

    @staticmethod
    def exit_distance(unit, cell):
        return HEIGHT - 1 - cell[1] if unit.physical_side == 0 else cell[1]

    def missile_legal(self, i, j):
        u, v = self.units[i], self.units[j]
        return (u.position is not None and v.position is not None
                and u.identity.logical_side != v.identity.logical_side
                and u.disposition == "organized" and u.cohesion <= 1 and u.ammunition > 0
                and self.effort[i] >= 1 and not self.links(i) and not self.links(j)
                and distance(u.position, v.position) <= u.identity.template.missile_range
                and in_front_sector(u.position, v.position, u.facing)
                and self.terrain.line_of_sight(u.position, v.position, self.occupied))

    def assault_geometry(self, i, j):
        u, v = self.units[i], self.units[j]
        return (u.position is not None and v.position is not None
                and u.identity.logical_side != v.identity.logical_side
                and u.disposition == "organized" and max(u.cohesion, u.morale, u.fatigue) <= 1
                and i not in self.forced
                and v.position in (step(u.position, d) for d in front(u.facing))
                and self.terrain.entry_cost(u, u.position, v.position) is not None)

    def pivot_legal(self, i, turn):
        u = self.units[i]
        threats = sum(u.position in self.projected(j) for j in self.enemies(i))
        return (u.disposition == "organized" and not self.links(i) and 1 <= abs(turn) <= 3
                and (threats == 0 or threats == 1 and abs(turn) == 1))

    def validate(self, order):
        if self.terminal or self.passed[self.side] or self.used[self.side] >= 4:
            raise ValueError("no principal opportunity")
        k, members = order.kind, order.members
        if (type(order.turn) is not int or any(type(i) is not int for i in members)
                or order.target is not None and type(order.target) is not int
                or any(len(cell) != 2 or any(type(n) is not int for n in cell) for cell in order.path)):
            raise ValueError("invalid order field type")
        if k in ("pass", "declare-withdrawal", "capitulate"):
            if order != Order(k) or k == "declare-withdrawal" and self.withdrawing[self.side]:
                raise ValueError("invalid side order")
            return {}
        if any(i not in self.ready or self.units[i].identity.logical_side != self.side for i in members):
            raise ValueError("formation unavailable")
        if k in ("group-move", "group-pivot"):
            return self.validate_group(order)
        if len(members) != 1:
            raise ValueError("expected one formation")
        i, = members
        u = self.units[i]
        payload = {"move": {"path": order.path}, "withdraw": {"path": order.path},
                   "pivot": {"turn": order.turn}, "missile": {"target": order.target},
                   "assault": {"target": order.target}}
        if order != Order(k, members, **payload.get(k, {})):
            raise ValueError("unexpected order fields")
        if k == "hold":
            cost = 0
        elif k in ("rally", "rest") and self.safe(i) and (
            (u.cohesion or u.morale) if k == "rally" else u.fatigue
        ):
            cost = 2
        elif k == "evacuate" and u.disposition == "organized" and self.safe(i) and not (
            self.exit_distance(u, u.position)
        ):
            cost = 2
        elif k == "move":
            cost = path_cost(u, order.path, self.terrain, self.occupied,
                             self.hostile_threat(self.side), bool(self.links(i)), self.effort[i])
            if self.withdrawing[self.side]:
                self.require_exit_progress(u, order.path)
        elif k == "withdraw" and u.disposition == "organized" and len(order.path) == 1:
            cell = order.path[0]
            entry = self.terrain.entry_cost(u, u.position, cell)
            if (entry is None or cell in self.occupied or cell in self.hostile_threat(self.side)
                    or cell not in (step(u.position, d) for d in rear(u.facing))):
                raise ValueError("blocked rear withdrawal")
            cost = 1 + entry
        elif k == "pivot" and self.pivot_legal(i, order.turn):
            cost = abs(order.turn)
        elif k in ("missile", "assault") and order.target in self.units and not self.withdrawing[self.side]:
            if k == "missile" and self.missile_legal(i, order.target):
                cost = 1
            elif k == "assault" and self.assault_geometry(i, order.target):
                cost = 2
            else:
                raise ValueError("illegal attack")
        else:
            raise ValueError("illegal principal order")
        if cost > self.effort[i]:
            raise ValueError("insufficient effort")
        return {i: cost}

    def require_exit_progress(self, u, path):
        distances = [self.exit_distance(u, cell) for cell in (u.position, *path)]
        if any(after >= before for before, after in zip(distances, distances[1:])):
            raise ValueError("withdrawal posture requires exit progress")

    def validate_group(self, order):
        members = order.members
        if order != Order(order.kind, members, turn=order.turn) or tuple(sorted(set(members))) != members:
            raise ValueError("invalid group order fields")
        if order.kind == "group-move":
            moves = group_translation(self.side, members, order.turn, self.units, self.terrain,
                                      frozenset(self.ready), self.effort,
                                      frozenset(i for link in self.contacts for i in link),
                                      self.hostile_threat(self.side))
            if self.withdrawing[self.side]:
                for i, (cell, _) in moves.items():
                    self.require_exit_progress(self.units[i], (cell,))
            return moves
        if (len(members) not in (2, 3) or abs(order.turn) != 1
                or not any(group.logical_side == self.side and set(members) <= set(group.members)
                           for group in initial_groups())
                or any(not self.pivot_legal(i, order.turn) or self.effort[i] < 1
                       or max(self.units[i].cohesion, self.units[i].morale, self.units[i].fatigue) > 1
                       for i in members)):
            raise ValueError("ineligible group pivot")
        cells = {self.units[i].position for i in members}
        connected = {self.units[members[0]].position}
        for _ in members[1:]:
            connected |= {cell for cell in cells if any(distance(cell, neighbor) == 1
                                                       for neighbor in connected)}
        if cells != connected:
            raise ValueError("disconnected group pivot")
        return dict.fromkeys(members, 1)

    def legal_orders(self):
        if self.terminal:
            return ()
        candidates = [Order(k) for k in ("pass", "declare-withdrawal", "capitulate")]
        for i in sorted(self.ready):
            u = self.units[i]
            if u.identity.logical_side != self.side:
                continue
            member = (i,)
            candidates.extend(Order(k, member) for k in ("hold", "rally", "rest", "evacuate"))
            candidates.extend(Order("pivot", member, turn=t) for t in (-3, -2, -1, 1, 2, 3))
            candidates.extend(Order("withdraw", member, path=(step(u.position, d),))
                              for d in rear(u.facing))
            for count in range(1, u.movement_cap + 1):
                for directions in product(front(u.facing), repeat=count):
                    path = []
                    cell = u.position
                    for direction in directions:
                        cell = step(cell, direction)
                        path.append(cell)
                    candidates.append(Order("move", member, tuple(path)))
            for j in self.enemies(i):
                candidates.extend(Order(k, member, target=j) for k in ("missile", "assault"))
        for group in initial_groups():
            if group.logical_side != self.side:
                continue
            for count in (2, 3):
                for members in combinations(sorted(group.members), count):
                    candidates.extend(Order("group-move", members, turn=(d + 3 * int(self.mirrored)) % 6)
                                      for d in range(6))
                    candidates.extend(Order("group-pivot", members, turn=t) for t in (-1, 1))
        result = []
        for candidate in candidates:
            try:
                self.validate(candidate)
            except ValueError:
                continue
            result.append(candidate)
        return tuple(result)

    def reaction_options(self, moved, previous, assault_target=None):
        options = []
        for target in sorted(moved):
            attacker = self.units[target]
            if attacker.position is None:
                continue
            defenders = self.enemies(target) if assault_target is None else (assault_target,)
            for source in defenders:
                u = self.units[source]
                if (u.position is None or u.disposition != "organized" or u.cohesion > 1
                        or source in self.responded or self.effort[source] < 1 or self.links(source)):
                    continue
                if self.missile_legal(source, target):
                    options.append(Reaction("missile", source, target))
                if (self.adjacent_enemies(source) == (target,)
                        and (assault_target is not None or distance(u.position, previous[target]) != 1)
                        and attacker.position not in (step(u.position, d) for d in front(u.facing))):
                    for turn in (-1, 1):
                        if attacker.position in (step(u.position, d) for d in front(u.facing + turn)):
                            options.append(Reaction("pivot", source, target, turn))
        return tuple(options)

    def offer_response(self, moved, previous, choose, assault_target=None):
        if self.response_offered:
            return
        choices = self.reaction_options(moved, previous, assault_target)
        if not choices:
            return
        self.response_offered = True
        side = self.units[choices[0].source].identity.logical_side
        chosen = choose(self.observe(side), choices) if choose is not None else None
        if chosen is not None and (not isinstance(chosen, Reaction) or
                canonical_json(asdict(chosen)) not in {canonical_json(asdict(r)) for r in choices}):
            raise ValueError("invalid elective response")
        self.metrics["legal_responses"] += len(choices) + 1
        self.stage("reaction", decision=asdict(chosen) if chosen else None)
        if chosen is None:
            return
        self.responded.add(chosen.source)
        self.effort[chosen.source] -= 1
        self.metrics["responses"] += 1
        if chosen.kind == "missile":
            self.discharge(chosen.source, chosen.target, response=True)
        else:
            self.pivot(chosen.source, chosen.turn)

    def pivot(self, i, turn):
        self.units[i].facing = (self.units[i].facing + turn) % 6
        self.mark(i, abs(turn))
        self.stage("pivot", unit=i, turn=turn)
        self.metrics["pivots"] += 1
        self.checkpoint()

    def stage(self, kind, **data):
        self.stages.append({"kind": kind, "leg": len(self.stages), **data})

    def norm(self, cell):
        return mirror(cell) if cell is not None and self.mirrored else cell

    def translate(self, moves, choose, withdrawing=False):
        previous = {i: self.units[i].position for i in moves}
        for i, (cell, cost) in moves.items():
            self.effort[i] -= cost
            self.units[i].position = cell
            self.mark(i, 2 if withdrawing else 1)
            if withdrawing:
                self.unlink(i)
        self.stage("translation", moves=[(i, self.norm(cell), cost) for i, (cell, cost) in moves.items()])
        self.metrics["steps"] += len(moves)
        self.active_this_round = True
        self.checkpoint()
        self.offer_response(moves, previous, choose)

    def discharge(self, i, j, response=False):
        self.units[i].ammunition -= 1
        self.spent_ammunition += 1
        self.mark(i, 1)
        self.metrics["missiles"] += 1
        self.active_this_round = True
        self.packets(((i, j, contribution(self.units[i], "missile")),), "missile", response)

    def assault(self, i, j, choose):
        self.metrics["assaults"] += 1
        self.active_this_round = True
        target_origin = self.units[j].position
        self.offer_response((i,), {}, choose, assault_target=j)
        if not self.assault_geometry(i, j) or self.units[j].position != target_origin:
            self.mark(i, 2)
            self.stage("assault-interrupted", attacker=i, target=j)
            self.metrics["assault_interruptions"] += 1
            return
        temporary = self.units[j].disposition == "routing"
        if not temporary:
            self.contacts.add(tuple(sorted((i, j))))
        outgoing = [(source, target, contribution(self.units[source], "melee",
                                                  len(self.links(source)) + int(temporary)))
                    for source, target in ((i, j), (j, i))]
        self.mark(i, 2)
        if outgoing[1][2]:
            self.mark(j, 1)
        self.checkpoint()
        self.packets(outgoing, "melee")

    def packets(self, directions, kind, response=False):
        packets, draws = {}, []
        leg = len(self.stages)
        for i, j, allocated in directions:
            def draw(channel):
                key = effect_key(self.seed, f"{FIXTURE_VERSION}-{self.variant}", self.round,
                                 self.root, leg, kind, response, i, j, channel)
                numerator = key.integer()
                draws.append((key.stage, channel, numerator))
                return numerator / 2**53

            victim = self.units[j]
            result = packet(allocated, victim, kind, draw)
            template = victim.identity.template
            exposure = min(victim.available, template.slots if kind == "missile" else template.edge_capacity)
            killed, wounded = result.casualties.killed, result.casualties.wounded
            if (any(type(n) is not int or n < 0 for n in (killed, wounded))
                    or killed + wounded > exposure
                    or any(type(n) is not int or not 0 <= n <= 2 for n in (result.cohesion, result.morale))
                    or not allocated and any((killed, wounded, result.cohesion, result.morale))):
                raise AssertionError("invalid F01 directed packet")
            packets[j] = result
        self.metrics["zero_effect_exchanges"] += not any(
            p.casualties.killed or p.casualties.wounded or p.cohesion or p.morale
            for p in packets.values()
        )
        self.stage("packets", weapon=kind, response=response, allocations=list(directions),
                   packets={str(i): asdict(p) for i, p in packets.items()}, draws=draws)
        for i, result in packets.items():
            self.units[i].record_losses(f"r{self.round}/root{self.root}/leg{leg}", result.casualties)
            self.incoming.add(i)
            self.safe_interval.discard(i)
        effects = {i: (p.cohesion, p.morale) for i, p in packets.items()}
        witnesses = self.pressure(effects, melee=kind == "melee")
        while witnesses:
            targets = sorted(i for i in witnesses - self.waves if self.viable(self.units[i]))
            if not targets:
                break
            self.waves.update(targets)
            self.incoming.update(targets)
            self.safe_interval.difference_update(targets)
            self.stage("shock", recipients=targets)
            witnesses = self.pressure(dict.fromkeys(targets, (0, 1)), melee=False)

    def pressure(self, effects, melee):
        triggers, breaks = [], []
        for i, (cohesion, morale) in sorted(effects.items()):
            u = self.units[i]
            result = assess(u.available, u.disposition, u.cohesion, u.morale,
                            cohesion, morale, melee=melee)
            u.cohesion, u.morale = result.cohesion, result.morale
            if result.transition == "depleted":
                self.removed_assets[i] = Holding(u.position, u.identity.logical_side, 0,
                                                 u.mounts, u.ammunition)
                u.position, u.disposition = None, "depleted"
                u.mounts = u.ammunition = 0
                self.ready.discard(i)
                self.unlink(i)
            elif result.transition in ("rout", "repulse"):
                triggers.append(i)
                self.ready.discard(i)
                self.forced.add(i)
                if result.transition == "rout":
                    breaks.append(i)
                    u.disposition = "routing"
                    self.unlink(i)
                self.metrics[result.transition] += 1
            if result.transition != "none":
                self.stage("condition", unit=i, transition=result.transition)
        witnesses = {j for i in breaks for j, u in self.units.items()
                     if self.viable(u) and u.identity.logical_side == self.units[i].identity.logical_side
                     and distance(u.position, self.units[i].position) == 1}
        self.checkpoint()
        self.displace(triggers)
        return witnesses

    def leave(self, i, marks):
        u = self.units[i]
        self.exits[i] = Holding(u.position, u.identity.logical_side, u.available,
                               u.mounts, u.ammunition)
        self.stage("evacuation", unit=i, cell=self.norm(u.position), forced=marks == 1)
        u.position, u.disposition = None, "withdrawn"
        u.available = u.mounts = u.ammunition = 0
        self.ready.discard(i)
        self.unlink(i)
        self.mark(i, marks)
        self.metrics["evacuations"] += 1

    def displace(self, triggers):
        occupied = self.occupied
        threats = [self.hostile_threat(side) for side in (0, 1)]
        candidates, exits = {}, []
        for i in sorted(triggers):
            u = self.units[i]
            if i in self.displaced or u.position is None:
                continue
            self.displaced.add(i)
            self.forced.add(i)
            self.ready.discard(i)
            routing = u.disposition == "routing"
            remaining = self.exit_distance(u, u.position)
            if routing and remaining == 0 and self.safe(i):
                exits.append(i)
                continue
            rank = [(d + 3 * u.physical_side) % 6 for d in (1, 2, 0, 3, 4, 5)]
            legal = []
            for d in rank:
                cell = step(u.position, d)
                if ((routing and self.exit_distance(u, cell) < remaining or
                     not routing and d in rear(u.facing))
                        and cell not in threats[u.identity.logical_side]
                        and self.terrain.entry_cost(u, u.position, cell) is not None):
                    legal.append(cell)
            candidates[i] = tuple(sorted(legal, key=lambda cell: self.exit_distance(u, cell)))
        result = arbitrate(occupied, candidates)
        for i, cell in result.assignments:
            self.units[i].position = cell
            self.unlink(i)
            self.mark(i, 1)
        for i in exits:
            self.leave(i, 1)
        if candidates or exits:
            self.stage("displacement", assignments=[(i, self.norm(cell)) for i, cell in result.assignments],
                       exits=exits, attempts=sorted(candidates))
            self.metrics["blocked_displacements"] += len(candidates) - len(result.assignments)
        self.checkpoint()

    def surrender(self, side):
        for i, u in self.units.items():
            if u.identity.logical_side != side:
                continue
            wounded = sum(lot.casualties.wounded for lot in u.losses)
            if wounded:
                self.wound_custody[i] = 1 - side
            if u.position is not None:
                self.custody[i] = Holding(u.position, 1 - side, u.available, u.mounts, u.ammunition, wounded)
                self.stage("custody", unit=i, cell=self.norm(u.position), wounded=wounded)
                u.available = u.mounts = u.ammunition = 0
                u.position, u.disposition = None, "captured"
                self.ready.discard(i)
                self.unlink(i)
        self.finish(1 - side, "capitulation")

    def finish(self, winner, reason, defeat=None):
        self.terminal = {"winner": winner, "reason": reason, "defeat": defeat or {}}
        if self.round:
            self.elapsed = self.round * 10
        self.ready.clear()
        self.resting.clear()
        self.effort = dict.fromkeys(self.units, 0)

    def adjudicate(self):
        viable = {u.identity.logical_side for u in self.units.values() if self.viable(u)}
        if len(viable) == 2:
            return
        defeat = {}
        for side in {0, 1} - viable:
            dispositions = {u.disposition for u in self.units.values() if u.identity.logical_side == side}
            defeat[side] = ("collapse" if "routing" in dispositions else
                            "orderly_departure" if dispositions == {"withdrawn"} else
                            "depletion_or_mixed_loss")
        winner = next(iter(viable), None)
        if winner is None:
            self.finish(None, "mutual", defeat)
        elif self.withdrawing[winner]:
            self.finish(None, "mutual_abandonment", defeat)
        else:
            self.finish(winner, "military", defeat)

    def objective(self):
        occupant = next((i for i, u in self.units.items() if u.position == OBJECTIVE), None)
        if occupant is None:
            return {"classification": "empty", "secure": None}
        u = self.units[occupant]
        condition = u.disposition != "organized" or max(u.cohesion, u.morale) > 1
        contact = bool(self.links(occupant))
        threat = OBJECTIVE in self.hostile_threat(u.identity.logical_side)
        label = "condition" if condition else "contact" if contact else "threat" if threat else "secure"
        return {"classification": label, "secure": u.identity.logical_side if label == "secure" else None,
                "occupant": occupant, "condition": condition, "contact": contact, "threat": threat,
                "fatigue": u.fatigue}

    def observe_objective(self, stage):
        self.objectives.append({"round": self.round, "stage": stage, **self.objective()})

    def close_round(self):
        if not self.active_this_round and any(
            self.viable(u) and any(self.viable(self.units[j]) and
                                   distance(u.position, self.units[j].position) <= 2
                                   for j in self.enemies(i))
            for i, u in self.units.items()
        ):
            self.metrics["stalled_contest_rounds"] += 1
        self.displace(i for i, u in self.units.items() if u.disposition == "routing"
                      and (not self.safe(i) or self.exit_distance(u, u.position) == 0))
        self.adjudicate()
        if self.terminal:
            return
        for i, u in self.units.items():
            if i in self.resting:
                if i in self.safe_interval and self.safe(i):
                    u.fatigue -= 1
                    u.exertion = 0
                    self.metrics["rest_completed"] += 1
                else:
                    self.metrics["rest_interrupted"] += 1
            if u.disposition == "routing" and i in self.safe_interval:
                u.disposition = "reforming"
            elif u.disposition == "reforming" and i not in self.incoming and self.safe(i) and (
                max(u.cohesion, u.morale) <= 1
            ):
                u.disposition = "organized"
        self.elapsed = self.round * 10
        self.observe_objective("closure")
        if self.round == 3:
            self.round_three_exhaustion = []
            for side in (0, 1):
                organized = [u for u in self.units.values() if u.identity.logical_side == side
                             and u.disposition == "organized" and u.position is not None]
                self.round_three_exhaustion.append(
                    (sum(u.fatigue == 2 for u in organized), len(organized))
                )
        if self.round == 12:
            if all(self.withdrawing):
                self.finish(None, "mutual_withdrawal")
            elif any(self.withdrawing):
                self.finish(int(self.withdrawing[0]), "abandonment")
            else:
                winner = self.objective()["secure"]
                self.finish(winner, "objective" if winner is not None else "unresolved")
        else:
            self.open_round()

    def advance_side(self):
        for side in (0, 1):
            if self.passed[side] or self.used[side] >= 4:
                self.ready.difference_update(i for i, u in self.units.items()
                                             if u.identity.logical_side == side)
        for side in (1 - self.side, self.side):
            if not self.passed[side] and self.used[side] < 4:
                self.side = side
                return
        self.close_round()

    def count_assault_gates(self):
        if self.withdrawing[self.side]:
            return
        for i in self.ready:
            u = self.units[i]
            if u.identity.logical_side != self.side or self.effort[i] < 2:
                continue
            for cell in (step(u.position, d) for d in front(u.facing)):
                if cell not in {self.units[j].position for j in self.enemies(i)}:
                    continue
                if self.terrain.entry_cost(u, u.position, cell) is None:
                    continue
                if u.disposition != "organized" or max(u.cohesion, u.morale) > 1:
                    self.metrics["assaults_denied_condition"] += 1
                elif u.fatigue == 2:
                    self.metrics["assaults_denied_exhaustion_only"] += 1

    def normalized_order(self, order):
        data = asdict(order)
        data["path"] = tuple(map(self.norm, order.path))
        if order.kind == "group-move" and self.mirrored:
            data["turn"] = (order.turn + 3) % 6
        return data

    def resolve(self, order, choose_response=None):
        if self._resolving or self._faulted:
            raise ValueError("F01 resolver is busy or faulted")
        try:
            costs = self.validate(order)
        except ValueError as error:
            self.metrics["rejected_orders"] += 1
            self.rejections.append({"round": self.round, "side": self.side,
                                    "order": self.normalized_order(order), "reason": str(error)})
            raise
        self._resolving = True
        try:
            self.resolve_accepted(order, costs, choose_response)
        except BaseException:
            self._faulted = True
            raise
        finally:
            self._resolving = False

    def resolve_accepted(self, order, costs, choose):
        before = self.digest()
        opening_round, opening_side = self.round, self.side
        objective_start = len(self.objectives)
        self.root += 1
        self.count_assault_gates()
        self.stages, self.waves, self.response_offered = [], set(), False
        k, members = order.kind, order.members
        if k == "pass":
            self.passed[self.side] = True
        else:
            self.used[self.side] += 1
            self.ready.difference_update(members)
            self.used_members.update(members)
        self.metrics["accepted_orders"] += 1
        if k == "declare-withdrawal":
            self.withdrawing[self.side] = True
        elif k == "capitulate":
            self.surrender(self.side)
        elif k == "group-move":
            self.translate(costs, choose)
        elif k == "move":
            i, = members
            unit = self.units[i]
            for index, cell in enumerate(order.path, 1):
                cost = self.terrain.entry_cost(unit, unit.position, cell)
                if cost is None or cost > self.effort[i] or cell in self.occupied:
                    self.stage("movement-interrupted", unit=i)
                    break
                entered_threat = cell in self.hostile_threat(opening_side)
                self.translate({i: (cell, cost)}, choose)
                if (entered_threat or i in self.forced or unit.disposition != "organized"
                        or index >= unit.movement_cap or unit.position in self.hostile_threat(opening_side)):
                    if index < len(order.path):
                        self.stage("movement-interrupted", unit=i)
                    break
        elif k == "group-pivot":
            for i in members:
                self.effort[i] -= 1
                self.units[i].facing = (self.units[i].facing + order.turn) % 6
                self.mark(i, 1)
            self.metrics["pivots"] += len(members)
            self.stage("group-pivot", members=members, turn=order.turn)
        elif members:
            for i, cost in costs.items():
                if k != "withdraw":
                    self.effort[i] -= cost
                u = self.units[i]
                if k == "pivot":
                    self.pivot(i, order.turn)
                elif k == "withdraw":
                    self.translate({i: (order.path[0], cost)}, choose, withdrawing=True)
                    self.metrics["withdrawals"] += 1
                elif k == "missile":
                    self.discharge(i, order.target)
                elif k == "assault":
                    self.assault(i, order.target, choose)
                elif k == "rally":
                    u.cohesion, u.morale = max(0, u.cohesion - 1), max(0, u.morale - 1)
                    self.incoming.discard(i)
                elif k == "rest":
                    self.resting.add(i)
                elif k == "evacuate":
                    self.leave(i, 2)
        self.checkpoint()
        self.observe_objective("root")
        if not self.terminal:
            self.adjudicate()
        if not self.terminal:
            self.advance_side()
        self.check_invariants()
        self.events.append({"schema": SCHEMA, "kind": "root", "round": opening_round,
                            "side": opening_side, "root": self.root, "order": self.normalized_order(order),
                            "stages": self.stages, "before": before, "after": self.digest(),
                            "objectives": self.objectives[objective_start:], "terminal": self.terminal})

    def digest(self):
        units = []
        for u in self.units.values():
            data = asdict(u)
            data.update(position=self.norm(u.position), physical_side=u.identity.logical_side,
                        facing=(u.facing + 3 * int(self.mirrored)) % 6)
            for lot in data["losses"]:
                lot["cell"] = self.norm(lot["cell"])
            units.append(data)
        holdings = [{i: {**asdict(holding), "cell": self.norm(holding.cell)}
                     for i, holding in ledger.items()}
                    for ledger in (self.exits, self.custody, self.removed_assets)]
        state = {"units": units, "holdings": holdings, "wound_custody": self.wound_custody,
                 "contacts": sorted(self.contacts), "withdrawing": self.withdrawing,
                 "round": self.round, "side": self.side, "elapsed": self.elapsed, "root": self.root,
                 "terminal": self.terminal, "used": self.used, "passed": self.passed,
                 "effort": self.effort, "spent_ammunition": self.spent_ammunition,
                 "active_this_round": self.active_this_round,
                 "ledgers": [sorted(x) for x in (self.ready, self.used_members, self.responded,
                                                 self.forced, self.displaced, self.resting,
                                                 self.incoming, self.safe_interval)]}
        return sha256(canonical_json(state).encode()).hexdigest()

    def check_invariants(self):
        positions = [u.position for u in self.units.values() if u.position is not None]
        if len(positions) != len(set(positions)) or any(not in_bounds(cell) for cell in positions):
            raise AssertionError("invalid F01 primary occupancy")
        if (self.ready & (self.used_members | self.forced) or not all(0 <= used <= 4 for used in self.used)
                or any(not 0 <= effort <= 3 for effort in self.effort.values())):
            raise AssertionError("invalid F01 allowance ledger")
        if self.elapsed != (self.round if self.terminal else max(0, self.round - 1)) * 10:
            raise AssertionError("invalid F01 interval accounting")
        holdings = (self.exits, self.custody, self.removed_assets)
        for i, u in self.units.items():
            if (u.position is None) != (u.disposition in ("withdrawn", "depleted", "captured")):
                raise AssertionError("invalid F01 disposition/location")
            if (u.position is not None) != (u.available > 0):
                raise AssertionError("invalid F01 available pool")
            if self.personnel(u) + sum(ledger[i].available for ledger in holdings if i in ledger) != self.population[i]:
                raise AssertionError("F01 personnel not conserved")
            if (u.disposition == "organized" and u.cohesion == u.morale == 2
                    or any(x not in (0, 1, 2) for x in (u.cohesion, u.morale, u.fatigue))
                    or not 0 <= u.exertion < 6 or min(u.ammunition, u.mounts) < 0):
                raise AssertionError("invalid F01 reserves or bands")
        units = tuple(self.units.values())
        inventories = [holding for ledger in holdings for holding in ledger.values()]
        if sum(u.mounts for u in (*units, *inventories)) != self.initial_mounts:
            raise AssertionError("F01 mounts not conserved")
        if sum(u.ammunition for u in (*units, *inventories)) + self.spent_ammunition != self.initial_stock:
            raise AssertionError("F01 ammunition not conserved")
        for a, b in self.contacts:
            if not (a < b and self.viable(self.units[a]) and self.viable(self.units[b])
                    and distance(self.units[a].position, self.units[b].position) == 1
                    and self.units[a].identity.logical_side != self.units[b].identity.logical_side):
                raise AssertionError("invalid F01 contact edge")
