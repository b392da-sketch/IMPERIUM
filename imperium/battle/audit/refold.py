"""Independent structural verification of an audit journal (P3 contract
rev 0.3 section 8, errata ER01 and ER06).

The verifier rebuilds the registered genesis with P1 builders and refolds
each root's effects over the primitive document. It never loads the engine,
and it re-derives the rules it checks in ``rules``. Refold is structural:
replay is the rule-equivalence check.
"""

from imperium.battle.board import entry_cost
from imperium.battle.canon import canonical_bytes_of, sha256_hex
from imperium.battle.codec import decode_bytes, digest, encode_state
from imperium.battle.errors import DomainError
from imperium.battle.fixtures import f01_opening, f01_supplied
from imperium.battle.values import FixtureClass, Hex, TemplateKind

from . import rules, wire
from .errors import AuditError, AuditReport

AUDIT_SCHEMA = "imperium.battle-audit/1"
HEADER = {
    "schema": AUDIT_SCHEMA, "state_schema": "imperium.battle-state/1",
    "command_schema": rules.COMMAND_SCHEMA, "event_schema": "imperium.battle-event/1",
    "rng": "D4-SHA256-v1", "registry": "IMPERIUM-BK-1",
}
HEADER_KEYS = {"kind", "chain", "fixture", "pair", "genesis", "run", *HEADER}
ROOT_KEYS = {"kind", "cursor", "command", "command_digest", "previous", "current", "events",
             "chain"}
EVENT_KEYS = {"stage", "id", "data", "effects", "draws"}
EFFECT_KEYS = {"path", "old", "new"}
TRAILER_KEYS = {"kind", "roots", "cursor", "final", "terminal", "stages", "draws", "chain"}
RUN_MAX = 2 ** 63 - 1


def _exact_int(value):
    return type(value) is int


_ABSENT = object()


def _get(tree, *keys):
    """A nested object member, or ``_ABSENT`` if any container is the wrong type."""
    for k in keys:
        if type(tree) is not dict or k not in tree:
            return _ABSENT
        tree = tree[k]
    return tree


def _lots(doc):
    """(lot, origin) per personnel record, or None for a malformed container."""
    personnel = doc.get("personnel")
    if type(personnel) is not list or any(type(p) is not dict or "lot" not in p
                                          or "origin" not in p for p in personnel):
        return None
    return [(p["lot"], p["origin"]) for p in personnel]


def _genesis(token):
    d = rules.DESCRIPTOR_OF[token]
    if d.fixture_class is FixtureClass.CANONICAL_OPENING:
        state = f01_opening(d.variant, d.orientation)
    else:
        state = f01_supplied(d.fixture_id)
    return d, state


class _Verifier:

    def __init__(self, require_sealed):
        self.require_sealed = require_sealed
        self.chain = None
        self.doc = None
        self.digest = None
        self.cursor = 0
        self.terminal = False
        self.roots = 0
        self.ids = set()
        self.version = 1
        self.stage_names = rules.STAGES
        self.counts = dict.fromkeys(rules.STAGES, 0)
        self.p4_roots = 0
        self.board = None
        self.trailer = False
        self.header = None
        self.line = 0

    def fail(self, code, path, detail):
        raise AuditError(code, self.line, path, detail)

    # ---------------------------------------------------------------- header

    def header_line(self, tree):
        if tree.get("kind") != "header":
            self.fail("AU02", "/kind", "the first line is the header")
        if set(tree) != HEADER_KEYS:
            self.fail("AU02", "", "header keys")
        # ER05/E04: the envelope version is selected by ``schema`` before
        # anything else is interpreted; the event schema must pair with it.
        expected = dict(HEADER)
        if tree["schema"] == rules.AUDIT_SCHEMA_V2 and type(tree["schema"]) is str:
            expected["schema"] = rules.AUDIT_SCHEMA_V2
            expected["event_schema"] = rules.EVENT_SCHEMA_V2
            self.version = 2
            self.stage_names = rules.STAGES_V2
            self.counts = dict.fromkeys(rules.STAGES_V2, 0)
        for key, value in expected.items():
            if tree[key] != value or type(tree[key]) is not str:
                self.fail("AU02", f"/{key}", "unsupported schema token")
        token = tree["fixture"]
        if type(token) is not str or token not in rules.DESCRIPTOR_OF:
            self.fail("AU02", "/fixture", "unregistered fixture")
        d, state = _genesis(token)
        full = digest(state)
        if full != d.full_genesis_digest or tree["genesis"] != full:
            self.fail("AU02", "/genesis", "genesis digest disagrees with the descriptor")
        if tree["pair"] != rules.PAIR_OF[token]:
            self.fail("AU02", "/pair", "pair disagrees with the fixture")
        run = tree["run"]
        if run is not None:
            if (type(run) is not dict or set(run) != {"seed", "replicate"}
                    or any(not _exact_int(run[k]) or not 0 <= run[k] <= RUN_MAX for k in run)):
                self.fail("AU02", "/run", "malformed run")
        self.header = tree
        self.board = state.scenario.board
        self.doc = encode_state(state)
        self.digest = full
        self.cursor = state.clock.event_cursor
        self.terminal = self.doc["phase"]["kind"] == "Terminal"

    # ------------------------------------------------------------------ root

    def root_line(self, tree):
        if set(tree) != ROOT_KEYS:
            self.fail("AU04", "", "root keys")
        cursor = tree["cursor"]
        if not _exact_int(cursor) or cursor != self.cursor + 1:
            self.fail("AU04", "/cursor", "wrong root cursor")
        command = tree["command"]
        bad = rules.command_shape(command) if self.version == 1 else rules.command_shape_v2(command)
        if bad is not None:
            self.fail("AU04", bad, "malformed command")
        if tree["command_digest"] != sha256_hex(canonical_bytes_of(command)):
            self.fail("AU04", "/command_digest", "command digest mismatch")
        for key in ("previous", "current"):
            if not wire.is_digest(tree[key]):
                self.fail("AU04", f"/{key}", "malformed digest")
        events = tree["events"]
        if type(events) is not list or not events:
            self.fail("AU04", "/events", "expected a nonempty event array")
        for i, e in enumerate(events):
            if type(e) is not dict or set(e) != EVENT_KEYS:
                self.fail("AU04", f"/events/{i}", "event keys")
            for key, t in (("stage", str), ("id", str), ("data", dict), ("effects", list),
                           ("draws", list)):
                if type(e[key]) is not t:
                    self.fail("AU04", f"/events/{i}/{key}", "event field type")
        if tree["previous"] != self.digest:
            self.fail("AU06", "/previous", "predecessor digest mismatch")
        if self.terminal:
            self.fail("AU11", "", "root after a terminal state")
        pre = self.doc
        phase = pre["phase"]
        kind = command["kind"]
        if kind == "OpenBattle":
            if phase["kind"] != "Opening":
                self.fail("AU04", "/command/kind", "OpenBattle requires Opening")
        else:
            if phase["kind"] != "AwaitingPrincipal":
                self.fail("AU04", "/command/kind", "principal command requires AwaitingPrincipal")
            if phase["side"] != command["side"]:
                self.fail("AU04", "/command/side", "not the acting side")
        stages = [e["stage"] for e in events]
        self.identities(pre, command, events, stages)
        trace = tuple(stages)
        p4 = kind in rules.P4_ORDERS
        if p4:
            successor = self.p4_trace(command, events, stages)
            doc = self.p4_root(tree, events, stages, pre, command, cursor)
        else:
            if trace not in rules.traces_for(kind) or rules.TRACES[trace][0] != phase["kind"]:
                self.fail("AU09", "/events", "stage sequence is not a P2 trace")
            successor = rules.TRACES[trace][1]
            doc = pre
            for i, e in enumerate(events):
                nxt = stages[i + 1] if i + 1 < len(stages) else None
                doc = self.event(i, e, doc, pre, command, trace, nxt, cursor)
        if _get(doc, "phase", "kind") != successor:
            self.fail("AU09", "/events", "successor phase disagrees with the trace")
        if _lots(doc) is None or _lots(doc) != _lots(pre):
            self.fail("AU12", "/events", "personnel lot ids or origins changed")
        body = canonical_bytes_of(doc)
        if sha256_hex(body) != tree["current"]:
            self.fail("AU14", "/current", "current digest mismatch")
        try:
            decode_bytes(body)
        except DomainError as exc:
            self.fail("AU15", "", f"not a valid stable state: {exc}")
        for s in stages:
            self.counts[s] += 1
        self.doc = doc
        self.digest = tree["current"]
        self.cursor = cursor
        self.terminal = doc["phase"]["kind"] == "Terminal"
        self.roots += 1
        if p4:
            self.p4_roots += 1

    def identities(self, pre, command, events, stages):
        expected = None
        id_kind = rules.p2_id_kind if self.version == 1 else rules.id_kind_v2
        for i, e in enumerate(events):
            stage, sid = e["stage"], e["id"]
            if stage not in self.stage_names:
                self.fail("AU05", f"/events/{i}/stage", "unknown stage")
            if rules.packet_id(sid) is not None:
                self.fail("AU05", f"/events/{i}/id", "reserved packet id in audit v1")
            if id_kind(sid) != stage:
                self.fail("AU05", f"/events/{i}/id", "malformed id or kind disagreement")
            if sid in self.ids or sid in (x["id"] for x in events[:i]):
                self.fail("AU05", f"/events/{i}/id", "repeated stage id")
            if expected is None:
                expected = rules.expected_ids(pre, command, stages)
            if sid != expected[i]:
                self.fail("AU05", f"/events/{i}/id", "wrong contextual id")
        self.ids.update(e["id"] for e in events)

    # ----------------------------------------------------------------- event

    def event(self, i, e, before, pre, command, trace, nxt, cursor, ctx=None):
        base = f"/events/{i}"
        stage = e["stage"]
        p4 = ctx is not None and stage in ctx["p4_stages"]
        typed_paths = []
        for j, eff in enumerate(e["effects"]):
            at = f"{base}/effects/{j}"
            if type(eff) is not dict or set(eff) != EFFECT_KEYS:
                self.fail("AU07", at, "effect keys")
            raw = rules.split(eff["path"])
            typed = None if raw is None else rules.resolve(before, raw)
            if typed is None or rules.pointer(typed) != eff["path"]:
                self.fail("AU07", f"{at}/path", "not an existing canonical location")
            if typed_paths:
                prev = typed_paths[-1]
                if not rules.order_key(prev) < rules.order_key(typed) or typed[:len(prev)] == prev:
                    self.fail("AU07", f"{at}/path", "effects unordered or overlapping")
            if p4:
                ok = rules.p4_permitted(stage, typed, ctx)
            else:
                ok = rules.permitted(stage, typed, trace, command, pre)
            if not ok:
                self.fail("AU07", f"{at}/path", "path not permitted for this stage and command")
            typed_paths.append(typed)
        # ER01 step 4: typed old-value agreement precedes any no-op or diff judgement.
        for j, (eff, typed) in enumerate(zip(e["effects"], typed_paths)):
            if rules.cbytes(rules.get(before, typed)) != rules.cbytes(eff["old"]):
                self.fail("AU08", f"{base}/effects/{j}/old", "old value disagrees")
        for j, eff in enumerate(e["effects"]):
            if rules.cbytes(eff["old"]) == rules.cbytes(eff["new"]):
                self.fail("AU07", f"{base}/effects/{j}/new", "no-op replacement")
        after = before
        for eff, typed in zip(e["effects"], typed_paths):
            after = rules.put(after, typed, eff["new"])
        listed = [(rules.pointer(t), rules.cbytes(eff["old"]), rules.cbytes(eff["new"]))
                  for eff, t in zip(e["effects"], typed_paths)]
        recomputed = [(rules.pointer(t), rules.cbytes(a), rules.cbytes(b))
                      for t, a, b in rules.canonical_diff(before, after)]
        if listed != recomputed:
            self.fail("AU07", f"{base}/effects", "not the canonical diff")
        # E03 step 3: forbidden value transitions (no flag restoration).
        for j, (eff, typed) in enumerate(zip(e["effects"], typed_paths)):
            leaf = typed[-1] if typed else None
            if p4 and leaf == "safe_latch" and eff["new"] is not False:
                self.fail("AU07", f"{base}/effects/{j}/path", "safe latch may only turn false")
            if p4 and leaf == "exerted" and eff["new"] is not True:
                self.fail("AU07", f"{base}/effects/{j}/path", "exerted may only turn true")
        if p4:
            self.p4_facts(i, e, before, after, ctx)
        else:
            self.facts(i, e, before, after, pre, command, nxt, cursor, typed_paths)
        if e["draws"]:
            self.fail("AU13", f"{base}/draws", "audit v1 events carry no draws")
        return after

    def facts(self, i, e, before, after, pre, command, nxt, cursor, typed_paths):
        base = f"/events/{i}"
        stage, data = e["stage"], e["data"]
        if i == 0:
            moves = [eff for eff, t in zip(e["effects"], typed_paths) if tuple(t) == rules.CURSOR]
            if (len(moves) != 1 or not _exact_int(moves[0]["new"])
                    or not _exact_int(moves[0]["old"])
                    or moves[0]["old"] != cursor - 1 or moves[0]["new"] != cursor):
                self.fail("AU10", f"{base}/effects", "missing or wrong cursor delta")
        if stage in rules.CHECK_POINT:
            want = {"point": rules.CHECK_POINT[stage],
                    "result": "TERMINAL" if nxt == "TERMINAL" else "CONTINUE"}
        elif stage == "ROOT":
            kind = command["kind"]
            want = {"kind": kind, "side": command["side"],
                    "formation": command.get("formation"), "use": rules.USE_KIND[kind]}
            if kind in rules.P4_ORDERS:
                pass  # ER01: the cursor is the only effect (whitelist)
            elif kind == "Capitulate":
                if rules.cbytes(after["ledger"]) != rules.cbytes(before["ledger"]):
                    self.fail("AU10", f"{base}/effects", "Capitulate records no ledger use")
            else:
                uses = _get(before, "ledger", "uses")
                got = _get(after, "ledger", "uses")
                if type(uses) is not list or type(got) is not list or rules.cbytes(got) != \
                        rules.cbytes(uses + [rules.expected_use(command)]):
                    self.fail("AU10", f"{base}/effects", "ledger use does not match the command")
            if kind == "DeclareWithdrawal":
                sides = after["sides"]
                posture = ([s.get("posture") for s in sides
                            if type(s) is dict and s.get("side") == command["side"]]
                           if type(sides) is list else None)
                if posture != ["WITHDRAWING"]:
                    self.fail("AU10", f"{base}/effects", "withdrawal posture not recorded")
        elif stage in ("CLOSURE_DISPLACEMENT", "RECOVERY"):
            want = {"applied": []}
        elif stage == "ADVANCE":
            c = _get(before, "clock", "completed_rounds")
            n = _get(after, "clock", "completed_rounds")
            if not _exact_int(c) or not _exact_int(n) or n != c + 1:
                self.fail("AU10", f"{base}/effects", "missing or wrong round advance")
            want = {"completed": c + 1}
        elif stage == "OPEN_ROUND":
            phase, ledger = after["phase"], after["ledger"]
            if (type(phase) is not dict or phase.get("kind") != "AwaitingPrincipal"
                    or type(ledger) is not dict or ledger.get("uses") != []
                    or not _exact_int(_get(after, "clock", "completed_rounds"))):
                self.fail("AU10", f"{base}/effects", "OPEN_ROUND installs no fresh round")
            want = {"round": after["clock"]["completed_rounds"] + 1, "first": phase.get("side")}
        else:  # TERMINAL
            phase = after["phase"]
            if type(phase) is not dict or phase.get("kind") != "Terminal" \
                    or after["ledger"] is not None:
                self.fail("AU10", f"{base}/effects", "TERMINAL installs no terminal phase")
            want = {"record": phase.get("record")}
        if rules.cbytes(data) != rules.cbytes(want):
            self.fail("AU10", f"{base}/data", "event data disagrees")

    # ------------------------------------------------------------- P4 roots

    def p4_trace(self, command, events, stages):
        """Static AU09 (E03): the selected family and the decision branch."""
        if not rules.p4_family(command["kind"], stages):
            self.fail("AU09", "/events", "stage sequence is not a P4 trace")
        for i, s in enumerate(stages):
            if s != "WINDOW":
                continue
            decision = _get(events[i]["data"], "decision")
            responded = i + 1 < len(stages) and stages[i + 1] == "RESPONSE"
            pivot = type(decision) is dict and decision.get("kind") == "RespondPivot"
            if responded != pivot:
                self.fail("AU09", "/events", "RESPONSE must follow exactly a RespondPivot")
        return rules.TAILS[tuple(stages[stages.index("IMMEDIATE_CHECK"):])]

    def p4_root(self, tree, events, stages, pre, command, cursor):
        kind = command["kind"]
        side = command["side"]
        members = command.get("members") or [command["formation"]]
        formations = pre["formations"]
        rounds = pre["ledger"]["formations"]
        lots = pre["personnel"]
        ctx = {
            "p4_stages": frozenset(("ROOT",) + rules.P4_STAGE_NAMES),
            "first": rules.FIRST_PHYSICAL[kind],
            "use_index": len(pre["ledger"]["uses"]),
            "formation_at": lambda i: formations[i]["formation"] if i < len(formations) else None,
            "round_at": lambda j: rounds[j]["formation"] if j < len(rounds) else None,
            "command": command, "side": side, "members": members, "tree": tree, "pre": pre,
            "events": events,
        }
        actors = frozenset(members)

        def evacuable(container, k, field):
            if container == "personnel":
                lot = lots[k] if k < len(lots) else None
                return (field == "place" and lot is not None and lot["lineage"] in actors
                        and lot["status"] == "AVAILABLE")
            items = pre[container]
            return (k < len(items) and items[k]["formation"] in actors
                    and field in ("assignment", "place", "custodian", "custody", "recovery"))

        ctx["evacuable"] = evacuable
        continuation = stages[-1] == "IMMEDIATE_CHECK"
        doc = pre
        for i, e in enumerate(events):
            stage = e["stage"]
            if stage == "RESPONSE":
                decision = _get(events[i - 1]["data"], "decision")
                who = decision.get("formation") if type(decision) is dict else None
                ctx["actors"] = frozenset((who,)) if type(who) is str else frozenset()
                ctx["decision"] = decision
            else:
                ctx["actors"] = actors
            nxt = stages[i + 1] if i + 1 < len(stages) else None
            trace = rules.T_ROOT if continuation else None
            doc = self.event(i, e, doc, pre, command, trace, nxt, cursor, ctx)
        return doc

    def _index(self, doc, token):
        for i, f in enumerate(doc["formations"]):
            if f["formation"] == token:
                return i
        self.fail("AU10", "", "unknown formation")

    def _round(self, doc, token):
        for fr in doc["ledger"]["formations"]:
            if fr["formation"] == token:
                return fr
        self.fail("AU10", "", "unknown ledger formation")

    @staticmethod
    def _template(doc, token):
        for entry in doc["scenario"]["roster"]:
            if entry["formation"] == token:
                return entry["template"]
        return None

    @staticmethod
    def _side_of(doc, token):
        for entry in doc["scenario"]["roster"]:
            if entry["formation"] == token:
                return entry["side"]
        return None

    def _mode(self, doc, token):
        """Present movement mode re-derived from the document (P1 8.3)."""
        if self._template(doc, token) != "MOUNTED":
            return "FOOT"
        avail = sum(p["count"] for p in doc["personnel"]
                    if p["lineage"] == token and p["status"] == "AVAILABLE")
        mounts = sum(m["count"] for m in doc["mounts"] if m["formation"] == token
                     and m["serviceability"] == "SERVICEABLE" and m["assignment"] == "ASSIGNED")
        return "MOUNTED" if avail <= mounts else "MIXED_FOOT"

    def _entry(self, doc, token, origin, destination):
        template = self._template(doc, token)
        mode = self._mode(doc, token)
        kind = {"FOOT": template, "MOUNTED": "MOUNTED", "MIXED_FOOT": "HEAVY"}[mode]
        return entry_cost(self.board, Hex(*origin), Hex(*destination), TemplateKind[kind])

    def _marked(self, base, before, after, token, marks):
        i = self._index(before, token)
        c0 = before["formations"][i]["condition"]
        c1 = after["formations"][i]["condition"]
        f, e = rules.map_marks(c0, marks, before["scenario"]["profile"]["exertion_threshold"])
        if (c1["fatigue"], c1["exertion"]) != (f, e):
            self.fail("AU10", f"{base}/effects", "exertion marks disagree with MP21")
        if self._round(after, token)["exerted"] is not True:
            self.fail("AU10", f"{base}/effects", "exerted flag not set")

    @staticmethod
    def _step(cell, direction):
        dq, dr = rules.DIRS[direction]
        return [cell[0] + dq, cell[1] + dr]

    @staticmethod
    def _direction(a, b):
        delta = (b[0] - a[0], b[1] - a[1])
        return rules.DIRS.index(delta) if delta in rules.DIRS else None

    def p4_facts(self, i, e, before, after, ctx):
        base = f"/events/{i}"
        stage, data = e["stage"], e["data"]
        command = ctx["command"]
        side = command["side"]
        uses_before = _get(before, "ledger", "uses")
        uses_after = _get(after, "ledger", "uses")
        bad = lambda detail: self.fail("AU10", f"{base}/effects", detail)  # noqa: E731
        if stage == "ROOT":
            # The cursor delta (AU10) is checked at i == 0 by the P3 rule.
            moves = [eff for eff in e["effects"] if eff["path"] == "/clock/event_cursor"]
            if len(moves) != 1 or moves[0]["new"] != ctx["tree"]["cursor"]:
                bad("missing or wrong cursor delta")
            kind = command["kind"]
            want = {"kind": kind, "side": side,
                    "formation": command.get("formation"), "use": rules.USE_KIND[kind]}
        elif stage in rules.STEPS or stage == "WITHDRAW":
            fid = command["formation"]
            k = rules.STEPS.index(stage) + 1 if stage in rules.STEPS else 1
            f = before["formations"][self._index(before, fid)]
            origin = f["cell"]
            dest = command["path"][k - 1] if stage in rules.STEPS else command["destination"]
            d = self._direction(origin, dest)
            first = 3 if stage == "WITHDRAW" else 0   # rear pair f+3, f+4; front f, f+1
            allowed = ((f["facing"] + first) % 6, (f["facing"] + first + 1) % 6)
            if d is None or d not in allowed:
                bad("leg is not a legal unit step")
            entry = self._entry(before, fid, origin, dest)
            if entry is None:
                bad("directed entry is not traversable")
            mode = self._mode(before, fid)
            leg = {"origin": origin, "destination": dest, "facing": f["facing"], "mode": mode}
            if stage == "WITHDRAW":
                work = {"kind": "Withdraw", "leg": leg}
                cost, marks = 2 + (entry - 1), 2
            else:
                path = command["path"]
                end = "COMPLETED" if k == len(path) else "STOPPED"
                cost, marks = entry, 1
                if k == 1:
                    work = {"kind": "Move", "declared": path, "legs": [leg], "end": end}
                else:
                    prior = uses_before[-1]["work"][0]
                    work = dict(prior, legs=prior["legs"] + [leg], end=end)
            if stage in ("STEP1", "WITHDRAW"):
                want_uses = uses_before + [{"side": side, "kind": "INDIVIDUAL", "group": None,
                                            "members": [fid], "work": [work]}]
            else:
                want_uses = uses_before[:-1] + [dict(uses_before[-1], work=[work])]
            if rules.cbytes(uses_after) != rules.cbytes(want_uses):
                bad("ledger work does not match the initiated step")
            if after["formations"][self._index(after, fid)]["cell"] != dest:
                bad("mover not on the declared cell")
            self._marked(base, before, after, fid, marks)
            threatened = data.get("threatened") if type(data) is dict else None
            if type(threatened) is not bool:
                self.fail("AU10", f"{base}/data", "event data disagrees")
            want = {"formation": fid, "from": origin, "to": dest, "mode": mode, "cost": cost,
                    "marks": marks, "threatened": threatened}
        elif stage == "GROUP_STEP":
            direction = command["direction"]
            members = command["members"]
            work, moves = [], []
            occupied = {tuple(g["cell"]) for g in before["formations"]
                        if g["disposition"] in ("ORGANIZED", "REFORMING", "ROUTING")
                        and g["formation"] not in members}
            for fid in members:
                f = before["formations"][self._index(before, fid)]
                dest = self._step(f["cell"], direction)
                entry = self._entry(before, fid, f["cell"], dest)
                if direction not in (f["facing"], (f["facing"] + 1) % 6) or entry is None:
                    bad("group leg is not a legal unit step")
                if tuple(dest) in occupied:
                    bad("group step enters a stationary primary")
                mode = self._mode(before, fid)
                work.append({"kind": "GroupStep", "leg": {"origin": f["cell"], "destination": dest,
                                                          "facing": f["facing"], "mode": mode}})
                moves.append({"formation": fid, "from": f["cell"], "to": dest, "mode": mode,
                              "cost": entry})
                if after["formations"][self._index(after, fid)]["cell"] != dest:
                    bad("member not on its translated cell")
                self._marked(base, before, after, fid, 1)
            want_uses = uses_before + [{"side": side, "kind": "GROUP", "group": command["group"],
                                        "members": members, "work": work}]
            if rules.cbytes(uses_after) != rules.cbytes(want_uses):
                bad("ledger work does not match the group step")
            want = {"direction": direction, "moves": moves}
        elif stage in ("PIVOT", "GROUP_PIVOT"):
            members = ctx["members"]
            turn = command["turn"]
            steps = command.get("steps", 1)
            work = []
            for fid in members:
                f0 = before["formations"][self._index(before, fid)]["facing"]
                f1 = after["formations"][self._index(after, fid)]["facing"]
                if f1 != (f0 + turn * steps) % 6:
                    bad("pivot facing disagrees with the order")
                if stage == "PIVOT":
                    work.append({"kind": "Pivot", "facing_before": f0, "turn": turn,
                                 "steps": steps})
                    want = {"formation": fid, "from": f0, "to": f1, "steps": steps}
                else:
                    work.append({"kind": "GroupPivot", "facing_before": f0, "turn": turn})
                self._marked(base, before, after, fid, steps)
            if stage == "GROUP_PIVOT":
                want = {"turn": turn, "members": members}
            group = command.get("group")
            want_uses = uses_before + [{"side": side, "kind": "GROUP" if group else "INDIVIDUAL",
                                        "group": group, "members": members, "work": work}]
            if rules.cbytes(uses_after) != rules.cbytes(want_uses):
                bad("ledger work does not match the pivot")
        elif stage == "EVACUATE":
            fid = command["formation"]
            i0 = self._index(before, fid)
            f = before["formations"][i0]
            mirrored = before["scenario"]["provenance"]["orientation"] == "MIRRORED"
            red = (side == "S0") != mirrored
            row = 8 if red else 0
            if f["cell"][1] != row or f["disposition"] != "ORGANIZED":
                bad("evacuation off the own exit row")
            if after["formations"][i0]["disposition"] != "WITHDRAWN":
                bad("evacuated formation not withdrawn")
            at_exit = {"kind": "AtExit", "side": side}
            for k, lot in enumerate(before["personnel"]):
                if lot["lineage"] == fid and lot["status"] == "AVAILABLE" \
                        and after["personnel"][k]["place"] != at_exit:
                    bad("available lot not transferred to the own exit")
            for name in ("mounts", "ammunition"):
                for k, item in enumerate(before[name]):
                    if item["formation"] != fid:
                        continue
                    got = after[name][k]
                    if (got["assignment"], got["place"], got["custodian"], got["custody"],
                            got["recovery"]) != ("ASSIGNED", at_exit, side, "OWN",
                                                 "NOT_APPLICABLE"):
                        bad("asset record disagrees with table 8.5")
            self._marked(base, before, after, fid, 2)
            want_uses = uses_before + [{"side": side, "kind": "INDIVIDUAL", "group": None,
                                        "members": [fid],
                                        "work": [{"kind": "Evacuate", "cell": f["cell"]}]}]
            if rules.cbytes(uses_after) != rules.cbytes(want_uses):
                bad("ledger work does not match the evacuation")
            want = {"formation": fid, "cell": f["cell"], "exit_side": side, "exit_row": row,
                    "round": before["clock"]["completed_rounds"] + 1}
        elif stage == "WINDOW":
            want = self._window_want(i, e, before, ctx)
        else:  # RESPONSE
            decision = ctx["decision"]
            fid, target = decision["formation"], decision["target"]
            i0 = self._index(before, fid)
            f0 = before["formations"][i0]["facing"]
            f1 = after["formations"][i0]["facing"]
            d = self._direction(before["formations"][i0]["cell"],
                                before["formations"][self._index(before, target)]["cell"])
            if f1 not in ((f0 + 1) % 6, (f0 - 1) % 6) or d is None \
                    or d not in (f1, (f1 + 1) % 6) or d in (f0, (f0 + 1) % 6):
                bad("defensive pivot geometry disagrees")
            if self._round(before, fid)["response"] is not None or self._round(after, fid)[
                    "response"] != {"kind": "DEFENSIVE_PIVOT", "target": target}:
                bad("response not recorded exactly once")
            self._marked(base, before, after, fid, 1)
            want = {"formation": fid, "kind": "DEFENSIVE_PIVOT", "target": target,
                    "from": f0, "to": f1}
        if rules.cbytes(data) != rules.cbytes(want):
            self.fail("AU10", f"{base}/data", "event data disagrees")

    def _window_want(self, i, e, before, ctx):
        """WINDOW (ER02, ER06): context hash, canonical options, bound decision."""
        at = f"/events/{i}/data"
        data = e["data"]
        command = ctx["command"]
        if set(data) != {"after", "window_id", "options", "decision"}:
            self.fail("AU10", at, "event data disagrees")
        after_id = ctx["events"][i - 1]["id"]
        token = rules.window_id(ctx["tree"]["previous"], command, after_id)
        defender = "S1" if command["side"] == "S0" else "S0"
        trigger = ctx["events"][i - 1]["stage"]
        movers = command["members"] if trigger == "GROUP_STEP" else [command["formation"]]
        options = data["options"]
        if (type(options) is not list or not options
                or any(type(o) is not dict or set(o) != {"formation", "kind", "target"}
                       for o in options)):
            self.fail("AU10", at, "malformed window options")
        keys = [(o["formation"], o["kind"], o["target"]) for o in options]
        if any(type(x) is not str for key in keys for x in key) \
                or any(a >= b for a, b in zip(keys, keys[1:])):
            self.fail("AU10", at, "window options not canonical")
        for f, kind, target in keys:
            if (self._side_of(before, f) != defender or target not in movers
                    or kind not in ("DEFENSIVE_PIVOT", "DEFENSIVE_MISSILE")):
                self.fail("AU10", at, "window option outside the window")
        decision = data["decision"]
        if rules.decision_shape(decision) is not None or decision["side"] != defender:
            self.fail("AU10", at, "malformed window decision")
        if decision["kind"] == "RespondMissile":
            self.fail("AU10", at, "an accepted journal carries no missile decision")
        if decision["kind"] == "RespondPivot" and \
                (decision["formation"], "DEFENSIVE_PIVOT", decision["target"]) not in keys:
            self.fail("AU10", at, "decision is not an offered option")
        return {"after": after_id, "window_id": token, "options": options,
                "decision": dict(decision, window_id=token)}

    # --------------------------------------------------------------- trailer

    def trailer_line(self, tree):
        if set(tree) != TRAILER_KEYS:
            self.fail("AU16", "", "trailer keys")
        own = {"roots": self.roots, "cursor": self.cursor, "final": self.digest,
               "terminal": self.terminal, "draws": 0}
        for key, value in own.items():
            if type(tree[key]) is not type(value) or tree[key] != value:
                self.fail("AU16", f"/{key}", "trailer count disagrees")
        stages = tree["stages"]
        if type(stages) is not dict or set(stages) != set(self.stage_names):
            self.fail("AU16", "/stages", "trailer stage keys")
        for name in sorted(self.stage_names):
            if not _exact_int(stages[name]) or stages[name] != self.counts[name]:
                self.fail("AU16", f"/stages/{name}", "trailer stage count disagrees")
        self.trailer = True

    # ------------------------------------------------------------------ main

    def run(self, data, expected_chain):
        for number, raw in wire.lines(data):
            self.line = number
            tree = wire.parse(number, raw)
            if self.trailer:
                self.fail("AU16", "", "data after the trailer")
            body = wire.body(tree)
            link = sha256_hex(body if self.chain is None else self.chain.encode("ascii") + body)
            if link != tree["chain"]:
                self.fail("AU03", "/chain", "chain mismatch")
            self.chain = link
            if number == 1:
                self.header_line(tree)
            elif tree.get("kind") == "root":
                self.root_line(tree)
            elif tree.get("kind") == "trailer":
                self.trailer_line(tree)
            else:
                self.fail("AU04", "/kind", "expected a root or trailer line")
        if self.require_sealed and not self.trailer:
            self.line += 1
            self.fail("AU16", "", "sealed journal required: no trailer")
        if self.version == 2 and self.p4_roots == 0:
            # ER05/E04: v2 is selected only by a completed P4 root.
            self.line += 1
            self.fail("AU16", "", "audit v2 without a completed P4 root")
        if expected_chain is not None and expected_chain != self.chain:
            self.fail("AU17", "", "final chain differs from the trusted commitment")
        run = self.header["run"]
        return AuditReport(
            fixture=self.header["fixture"], pair=self.header["pair"],
            run=None if run is None else (run["seed"], run["replicate"]),
            sealed=self.trailer, roots=self.roots, cursor=self.cursor, final=self.digest,
            terminal=self.terminal,
            stages=tuple((name, self.counts[name]) for name in sorted(self.stage_names)),
            draws=0, final_chain=self.chain)


def preflight(data, require_sealed, expected_chain):
    if type(data) is not bytes:
        raise TypeError("data must be bytes")
    if type(require_sealed) is not bool:
        raise TypeError("require_sealed must be a bool")
    if expected_chain is not None and not wire.is_digest(expected_chain):
        raise ValueError("expected_chain must be 64 lowercase hexadecimal characters")


def verify(data, *, require_sealed=True, expected_chain=None):
    """Structurally verify one audit v1 journal; return an ``AuditReport``
    or raise ``AuditError`` at the first fault (8.2, 8.3)."""
    preflight(data, require_sealed, expected_chain)
    return _Verifier(require_sealed).run(data, expected_chain)
