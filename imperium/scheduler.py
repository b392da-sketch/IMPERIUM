"""Open-information, individual-action EF09-RH1 resolver."""

from collections import Counter
from dataclasses import asdict, dataclass

from .condition import assess, exert
from .displacement import FrozenField, arbitrate
from .events import Event, state_digest
from .fixture import FIXTURE_VERSION, ROUND_LIMIT, Encounter, Formation, initial_encounter
from .geometry import HEIGHT, OBJECTIVE, Hex, distance, front, in_bounds, mirror, rear, step
from .participation import allocate
from .pressure import directed_packet
from .profiles import Profile
from .randomness import DrawKey, melee_stage


@dataclass(frozen=True)
class Action:
    kind: str
    actor: int | None = None
    path: tuple[Hex, ...] = ()
    turn: int = 0
    target: int | None = None


class Battle:
    def __init__(self, profile: Profile, seed: int, mirrored: bool = False,
                 *, encounter: Encounter | None = None, journal: bool = True, legacy: bool = False):
        self.profile, self.seed, self.mirrored = profile, seed, mirrored
        self.encounter = encounter if encounter is not None else initial_encounter(profile, mirrored)
        self.units = {f.identity.formation_id: f for f in self.encounter.formations}
        self.round = 1
        self.side = 0
        self.used = [0, 0]
        self.passed = [False, False]
        self.effort = {}
        self.terminal = None
        self.root = 0
        self.events = []
        self.actions = []
        self.rejections = []
        self.details = []
        self.journal, self.legacy = journal, legacy
        self.metrics = Counter()
        self.objectives = []
        self.observations = []
        self.exhaustion = None
        self.open_round()

    def ordered(self):
        return [self.units[i] for i in sorted(self.units)]

    def links(self, unit):
        return [link for link in self.encounter.contacts if unit in link]

    def unlink(self, unit):
        self.encounter.contacts.difference_update(self.links(unit))

    def enemies(self, unit):
        return [f for f in self.ordered()
                if f.physical_side != unit.physical_side and f.position is not None]

    def safe(self, unit, field=None):
        if unit.position is None or self.links(unit.identity.formation_id):
            return False
        if field is None:
            field = FrozenField.capture(self.encounter)
        return (unit.position not in field.threatened_by_side[1 - unit.physical_side]
                and all(distance(unit.position, f.position) != 1 for f in self.enemies(unit)))

    def checkpoint(self):
        field = FrozenField.capture(self.encounter)
        for unit in self.ordered():
            if unit.full_interval_safety and not self.safe(unit, field):
                unit.full_interval_safety = False

    def open_round(self):
        self.used[:] = [0, 0]
        self.passed[:] = [False, False]
        self.side = (self.round - 1) % 2
        field = FrozenField.capture(self.encounter)
        for unit in self.ordered():
            i = unit.identity.formation_id
            unit.principal_eligibility = self.viable(unit)
            self.effort[i] = self.profile.formation_effort if unit.principal_eligibility else 0
            unit.mandatory_displacement_attempted = unit.forced_stop = False
            unit.incoming_effect_flag = unit.pending_rest = False
            unit.activity_marks = 0
            unit.full_interval_safety = self.safe(unit, field)
            if not self.profile.carry_exertion:
                unit.exertion_remainder = 0

    @staticmethod
    def viable(unit):
        return (unit.position is not None and unit.available_personnel > 0
                and unit.disposition in ("organized", "reforming"))

    def mark(self, unit, marks):
        unit.fatigue, unit.exertion_remainder = exert(
            unit.fatigue, unit.exertion_remainder, marks, self.profile
        )
        unit.activity_marks += marks
        unit.full_interval_safety = False
        self.metrics["exertion"] += marks

    @staticmethod
    def exit_distance(side, cell):
        return HEIGHT - 1 - cell[1] if side == 0 else cell[1]

    def displace(self, triggered):
        field = FrozenField.capture(self.encounter)
        candidates, exits = {}, []
        for identifier in sorted(triggered):
            unit = self.units[identifier]
            if unit.mandatory_displacement_attempted or unit.position is None:
                continue
            unit.mandatory_displacement_attempted = unit.forced_stop = True
            unit.principal_eligibility = False
            side, position = unit.physical_side, unit.position
            routing = unit.disposition == "routing"
            remaining = self.exit_distance(side, position)
            if routing and remaining == 0 and self.safe(unit, field):
                exits.append(identifier)
                continue
            directions = tuple((d + 3 * side) % 6 for d in (1, 2, 0, 3, 4, 5))
            cells = (step(position, d) for d in directions if routing or d in rear(unit.facing))
            threats = field.threatened_by_side[1 - side]
            valid = tuple(cell for cell in cells if in_bounds(cell) and cell not in threats)
            if routing:
                valid = tuple(cell for cell in valid if self.exit_distance(side, cell) < remaining)
            candidates[identifier] = tuple(sorted(valid, key=lambda cell: self.exit_distance(side, cell)))
        arbitration = arbitrate(self.arbitration_occupancy(field, exits), candidates)
        for identifier, destination in arbitration.assignments:
            unit = self.units[identifier]
            unit.position = destination
            self.unlink(identifier)
            self.mark(unit, 1)
        for identifier in exits:
            unit = self.units[identifier]
            unit.position = None
            unit.disposition = "withdrawn"
            self.unlink(identifier)
            self.mark(unit, 1)
        self.metrics["routing_exits"] += len(exits)
        self.metrics["blocked"] += len(candidates) - len(arbitration.assignments)
        def normalized(cell):
            return mirror(cell) if self.mirrored else cell

        if exits or candidates:
            self.details.append({
                "displacement": {"exits": exits, "assignments": [(i, normalized(cell)) for i, cell in arbitration.assignments],
                                 "blocked": sorted(set(candidates) - dict(arbitration.assignments).keys()),
                                 "proposals": [[(i, normalized(cell)) for i, cell in p.proposals]
                                               for p in arbitration.rounds],
                                 "conflicts": [sorted(map(normalized, p.conflicts)) for p in arbitration.rounds]},
            })
        self.checkpoint()
        return arbitration

    def arbitration_occupancy(self, field, exits):
        return field.occupied

    def incoming(self, i):
        unit = self.units[i]
        unit.incoming_effect_flag = True
        unit.full_interval_safety = False

    def pressure_stage(self, effects, *, melee):
        triggered, breaks = [], []
        for i, (dc, dm) in sorted(effects.items()):
            unit = self.units[i]
            outcome = assess(unit.available_personnel, unit.disposition, unit.cohesion,
                             unit.morale, dc, dm, melee=melee)
            unit.cohesion, unit.morale = outcome.cohesion, outcome.morale
            if outcome.transition == "depleted":
                unit.disposition = "depleted"
                unit.position = None
                unit.principal_eligibility = False
                self.unlink(i)
            elif outcome.transition in ("rout", "repulse"):
                unit.forced_stop = True
                unit.principal_eligibility = False
                triggered.append(i)
                self.metrics[outcome.transition] += 1
                if outcome.transition == "rout":
                    unit.disposition = "routing"
                    breaks.append(i)
                    self.metrics.setdefault("first_rout", self.round)
                    self.unlink(i)
        witnesses = {
            i: [f.identity.formation_id for f in self.ordered()
                if self.viable(f) and f.physical_side == self.units[i].physical_side
                and distance(self.units[i].position, f.position) == 1]
            for i in breaks
        }
        self.checkpoint()
        self.displace(triggered)
        return witnesses

    def exchange(self, a, b, draws):
        attacker, defender = self.units[a], self.units[b]
        link = tuple(sorted((a, b)))
        if defender.disposition != "routing":
            self.encounter.contacts.add(link)
        self.checkpoint()
        temporary = int(defender.disposition == "routing")
        allocations = {
            i: allocate(self.units[i].available_personnel, len(self.links(i)) + temporary,
                        self.profile.allocation, routing=self.units[i].disposition == "routing")[0]
            for i in (a, b)
        }
        self.metrics["multi"] += any(len(self.links(i)) > 1 for i in (a, b))
        packets = {}
        for source, target in ((a, b), (b, a)):
            stage = melee_stage(self.round, self.side, self.used[self.side], a, b, source)

            def draw(channel):
                if self.legacy:
                    from .legacy import legacy_draw
                    tag = (f"r{self.round}|s{self.side}|o{self.used[self.side]}"
                           f"|{a}|{b}|{source}")
                    integer = legacy_draw(self.seed, tag, channel)
                    draws.append((tag, channel, integer))
                    return integer / 2**32
                key = DrawKey(self.seed, FIXTURE_VERSION, self.seed, stage, channel)
                integer = key.integer()
                draws.append((stage, channel, integer))
                return integer / 2**53

            recipient = self.units[target]
            packets[target] = directed_packet(allocations[source], recipient.available_personnel,
                                              recipient.disposition == "routing", self.profile, draw)
        self.metrics["zero_contribution"] += sum(v == 0 for v in allocations.values())
        self.metrics["zero_exchange"] += all(
            not (p.casualties.killed or p.casualties.wounded or p.cohesion or p.morale)
            for p in packets.values()
        )
        effects = {}
        for i, packet in sorted(packets.items()):
            unit = self.units[i]
            losses = packet.casualties
            unit.available_personnel -= losses.killed + losses.wounded
            unit.killed_personnel += losses.killed
            unit.wounded_unavailable_personnel += losses.wounded
            self.incoming(i)
            effects[i] = (packet.cohesion, packet.morale)
        self.details.append({"packets": [
            (i, allocations[b if i == a else a], p.casualties.killed, p.casualties.wounded,
             p.cohesion, p.morale) for i, p in sorted(packets.items())
        ]})
        self.mark(attacker, 2)
        if allocations[b]:
            self.mark(defender, 1)
        witnesses = self.pressure_stage(effects, melee=True)
        seen = set()
        while witnesses:
            candidates = set().union(*map(set, witnesses.values()))
            recipients = sorted(i for i in candidates - seen if self.viable(self.units[i]))
            self.details.append({"shock": {"witnesses": sorted(witnesses.items()),
                                           "deduplicated": sorted(candidates & seen),
                                           "recipients": recipients}})
            if not recipients:
                break
            seen.update(recipients)
            for i in recipients:
                self.incoming(i)
            witnesses = self.pressure_stage(dict.fromkeys(recipients, (0, 1)), melee=False)

    def cost(self, action, field=None):
        """Validate the public declaration without changing canonical state."""
        if self.terminal or self.passed[self.side] or self.used[self.side] >= self.profile.opportunities:
            raise ValueError("no side opportunity")
        if action == Action("pass"):
            return 0
        unit = self.units.get(action.actor)
        if (unit is None or unit.identity.logical_side != self.side
                or not unit.principal_eligibility or unit.forced_stop):
            raise ValueError("formation unavailable")
        kind = action.kind
        if field is None:
            field = FrozenField.capture(self.encounter)
        threat = field.threatened_by_side[1 - unit.physical_side]
        engaged = bool(self.links(action.actor))
        organized = unit.disposition == "organized"
        pos = unit.position
        if kind == "hold":
            cost = 0
        elif kind in ("rally", "rest") and self.safe(unit, field):
            if (kind == "rally" and not (unit.cohesion or unit.morale)
                    or kind == "rest" and not unit.fatigue):
                raise ValueError("no eligible recovery")
            cost = 2
        elif kind == "assault" and organized and max(unit.cohesion, unit.morale, unit.fatigue) <= 1:
            target = self.units.get(action.target)
            if (target is None or target.physical_side == unit.physical_side
                    or target.position not in [step(pos, d) for d in front(unit.facing)]):
                raise ValueError("invalid assault target")
            cost = 2
        elif kind == "pivot" and organized and not engaged and action.turn in (-1, 1):
            if pos in threat:
                sources = sum(f.disposition == "organized" and f.available_personnel > 0
                              and max(f.cohesion, f.morale) <= 1
                              and pos in [step(f.position, d) for d in front(f.facing)]
                              for f in self.enemies(unit))
                if sources != 1:
                    raise ValueError("pivot has multiple threat sources")
            cost = 1
        elif kind == "withdraw" and organized and len(action.path) == 1:
            cell = action.path[0]
            if (cell not in [step(pos, d) for d in rear(unit.facing)]
                    or not field.destinations(unit.physical_side, (cell,))):
                raise ValueError("blocked withdrawal")
            cost = 2
        elif kind == "move" and organized and not engaged:
            cap = 1 if max(unit.cohesion, unit.fatigue) == 2 else 2
            if not 1 <= len(action.path) <= cap or pos in threat:
                raise ValueError("illegal move origin or length")
            fatigue, remainder = unit.fatigue, unit.exertion_remainder
            for index, cell in enumerate(action.path, 1):
                if (cell not in [step(pos, d) for d in front(unit.facing)]
                        or not in_bounds(cell) or cell in field.occupied):
                    raise ValueError("illegal movement step")
                fatigue, remainder = exert(fatigue, remainder, 1, self.profile)
                if index < len(action.path) and (cell in threat or fatigue == 2):
                    raise ValueError("move extends past mandatory stop")
                pos = cell
            cost = len(action.path)
        else:
            raise ValueError("unsupported or illegal action")
        if cost > self.effort[action.actor]:
            raise ValueError("insufficient effort")
        payload = {"move": {"path": action.path}, "withdraw": {"path": action.path},
                   "pivot": {"turn": action.turn}, "assault": {"target": action.target}}
        if action != Action(kind, action.actor, **payload.get(kind, {})):
            raise ValueError("unexpected action fields")
        return cost

    def digest(self):
        return state_digest(self.encounter, round_state={
            "round": self.round, "side": self.side, "used": self.used,
            "passed": self.passed, "effort": self.effort, "terminal": self.terminal,
        }, mirrored=self.mirrored)

    def resolve(self, action):
        try:
            cost = self.cost(action)
        except ValueError as error:
            self.rejections.append({"round": self.round, "side": self.side,
                                    "order": asdict(action), "reason": str(error)})
            raise
        observation_start = len(self.objectives)
        before = self.digest() if self.journal else ""
        stage_round = self.round
        self.root += 1
        self.actions.append(action)
        self.details = []
        for unit in self.ordered():
            if unit.identity.logical_side != self.side or not unit.principal_eligibility:
                continue
            adjacent_front = {step(unit.position, d) for d in front(unit.facing)}
            targets = sum(f.position in adjacent_front for f in self.enemies(unit))
            if unit.disposition != "organized" or max(unit.cohesion, unit.morale) > 1:
                self.metrics["assault_denied_other_condition"] += targets
            elif unit.fatigue == 2:
                self.metrics["assault_denied_exhaustion_only"] += targets
        draws = []
        if action.kind == "pass":
            self.passed[self.side] = True
        else:
            unit = self.units[action.actor]
            self.used[self.side] += 1
            unit.principal_eligibility = False
            self.effort[action.actor] -= cost
            self.metrics[action.kind] += 1
            if action.kind == "move":
                for cell in action.path:
                    unit.position = cell
                    self.mark(unit, 1)
                    self.metrics["steps"] += 1
                    self.checkpoint()
            elif action.kind == "withdraw":
                unit.position = action.path[0]
                self.unlink(action.actor)
                self.mark(unit, 2)
                self.checkpoint()
            elif action.kind == "pivot":
                unit.facing = (unit.facing + action.turn) % 6
                self.mark(unit, 1)
                self.checkpoint()
            elif action.kind == "assault":
                self.exchange(action.actor, action.target, draws)
            elif action.kind == "rally":
                unit.cohesion = max(0, unit.cohesion - 1)
                unit.morale = max(0, unit.morale - 1)
                unit.incoming_effect_flag = False
                self.checkpoint()
            elif action.kind == "rest":
                unit.pending_rest = True
        self.observe("root")
        self.check_terminal()
        self.assert_invariants()
        if not self.terminal:
            for side in (0, 1):
                if self.passed[side] or self.used[side] == self.profile.opportunities:
                    for f in self.ordered():
                        if f.identity.logical_side == side:
                            f.principal_eligibility = False
            for side in (1 - self.side, self.side):
                if not self.passed[side] and self.used[side] < self.profile.opportunities:
                    self.side = side
                    break
            else:
                self.close_round()
        if self.journal:
            if self.mirrored:
                action = Action(action.kind, action.actor, tuple(map(mirror, action.path)),
                                action.turn, action.target)
            self.events.append(Event(
                self.profile.name, self.seed, stage_round, self.root, 0, "principal",
                before, self.digest(), action.actor, action.target,
                data={"action": asdict(action), "draws": draws, "details": self.details,
                      "objectives": self.objectives[observation_start:],
                      "conditions": self.observations[observation_start:]},
            ))

    def objective(self):
        occupant = next((f for f in self.ordered() if f.position == OBJECTIVE), None)
        if occupant is None:
            return {"classification": "empty", "secure": None}
        i = occupant.identity.formation_id
        field = FrozenField.capture(self.encounter)
        condition = occupant.disposition != "organized" or max(occupant.cohesion, occupant.morale) > 1
        contact = bool(self.links(i))
        threat = OBJECTIVE in field.threatened_by_side[1 - occupant.physical_side]
        classification = ("condition" if condition else "contact" if contact else
                          "threat" if threat else "secure")
        return {"classification": classification, "secure": occupant.identity.logical_side
                if classification == "secure" else None, "occupant": i, "contact": contact,
                "threat": threat, "condition": condition, "disposition": occupant.disposition,
                "cohesion": occupant.cohesion, "morale": occupant.morale, "fatigue": occupant.fatigue}

    def observe(self, stage):
        self.objectives.append({"stage": stage, "round": self.round, **self.objective()})
        self.observations.append([
            (f.identity.formation_id, f.disposition, f.available_personnel,
             f.cohesion, f.morale, f.fatigue)
            for f in self.ordered()
        ])

    def check_terminal(self):
        sides = {f.identity.logical_side for f in self.ordered() if self.viable(f)}
        if len(sides) < 2:
            self.terminal = (next(iter(sides), None), "military" if sides else "mutual")

    def close_round(self):
        field = FrozenField.capture(self.encounter)
        routers = [i for i, f in self.units.items() if f.disposition == "routing"
                   and (not self.safe(f, field) or self.exit_distance(f.physical_side, f.position) == 0)]
        self.displace(routers)
        self.check_terminal()
        if not self.terminal:
            field = FrozenField.capture(self.encounter)
            for f in self.ordered():
                if f.pending_rest:
                    if f.full_interval_safety and self.safe(f, field):
                        f.fatigue -= 1
                        if self.profile.carry_exertion:
                            f.exertion_remainder = 0
                        self.metrics["rest_completed"] += 1
                    else:
                        self.metrics["rest_interrupted"] += 1
                    f.pending_rest = False
                if f.disposition == "routing" and f.full_interval_safety and self.safe(f, field):
                    f.disposition = "reforming"
                    self.metrics["refuge"] += 1
                elif (f.disposition == "reforming" and max(f.cohesion, f.morale) <= 1
                      and not f.incoming_effect_flag and self.safe(f, field)):
                    f.disposition = "organized"
                    self.metrics["reorganized"] += 1
            self.observe("closure")
            if self.round == 3:
                self.exhaustion = []
                for side in (0, 1):
                    group = [f for f in self.ordered() if f.identity.logical_side == side
                             and f.disposition == "organized" and f.position is not None]
                    self.exhaustion.append((sum(f.fatigue == 2 for f in group), len(group)))
            if self.round == ROUND_LIMIT:
                winner = self.objectives[-1]["secure"]
                self.terminal = (winner, "objective" if winner is not None else "unresolved")
            else:
                self.round += 1
                self.open_round()
        self.assert_invariants()

    def assert_invariants(self):
        positions = set()
        for f in self.ordered():
            partitions = (f.available_personnel, f.killed_personnel, f.wounded_unavailable_personnel)
            assert all(type(n) is int and n >= 0 for n in partitions)
            assert sum(partitions) == f.initial_personnel
            assert all(0 <= value <= 2 for value in (f.cohesion, f.morale, f.fatigue))
            assert 0 <= f.exertion_remainder < self.profile.threshold
            if f.position is not None:
                assert in_bounds(f.position) and f.position not in positions and f.available_personnel > 0
                positions.add(f.position)
        for a, b in self.encounter.contacts:
            left, right = self.units[a], self.units[b]
            assert a < b and self.viable(left) and self.viable(right)
            assert left.physical_side != right.physical_side and distance(left.position, right.position) == 1
        if len(self.units) == 12:
            assert sum(f.initial_personnel for f in self.ordered()) == 2880
