"""Independent structural verification of an audit journal (P3 contract
rev 0.3 section 8, errata ER01 and ER06).

The verifier rebuilds the registered genesis with P1 builders and refolds
each root's effects over the primitive document. It never loads the engine,
and it re-derives the rules it checks in ``rules``. Refold is structural:
replay is the rule-equivalence check.
"""

from imperium.battle.canon import canonical_bytes_of, sha256_hex
from imperium.battle.codec import decode_bytes, digest, encode_state
from imperium.battle.errors import DomainError
from imperium.battle.fixtures import f01_opening, f01_supplied
from imperium.battle.values import FixtureClass

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
        self.counts = dict.fromkeys(rules.STAGES, 0)
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
        for key, value in HEADER.items():
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
        bad = rules.command_shape(command)
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
        if trace not in rules.traces_for(kind) or rules.TRACES[trace][0] != phase["kind"]:
            self.fail("AU09", "/events", "stage sequence is not a P2 trace")
        doc = pre
        for i, e in enumerate(events):
            nxt = stages[i + 1] if i + 1 < len(stages) else None
            doc = self.event(i, e, doc, pre, command, trace, nxt, cursor)
        if _get(doc, "phase", "kind") != rules.TRACES[trace][1]:
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

    def identities(self, pre, command, events, stages):
        expected = None
        for i, e in enumerate(events):
            stage, sid = e["stage"], e["id"]
            if stage not in rules.STAGES:
                self.fail("AU05", f"/events/{i}/stage", "unknown stage")
            if rules.packet_id(sid) is not None:
                self.fail("AU05", f"/events/{i}/id", "reserved packet id in audit v1")
            if rules.p2_id_kind(sid) != stage:
                self.fail("AU05", f"/events/{i}/id", "malformed id or kind disagreement")
            if sid in self.ids or sid in (x["id"] for x in events[:i]):
                self.fail("AU05", f"/events/{i}/id", "repeated stage id")
            if expected is None:
                expected = rules.expected_ids(pre, command, stages)
            if sid != expected[i]:
                self.fail("AU05", f"/events/{i}/id", "wrong contextual id")
        self.ids.update(e["id"] for e in events)

    # ----------------------------------------------------------------- event

    def event(self, i, e, before, pre, command, trace, nxt, cursor):
        base = f"/events/{i}"
        stage = e["stage"]
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
            if not rules.permitted(stage, typed, trace, command, pre):
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
            if kind == "Capitulate":
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
        if type(stages) is not dict or set(stages) != set(rules.STAGES):
            self.fail("AU16", "/stages", "trailer stage keys")
        for name in rules.STAGE_ORDER:
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
        if expected_chain is not None and expected_chain != self.chain:
            self.fail("AU17", "", "final chain differs from the trusted commitment")
        run = self.header["run"]
        return AuditReport(
            fixture=self.header["fixture"], pair=self.header["pair"],
            run=None if run is None else (run["seed"], run["replicate"]),
            sealed=self.trailer, roots=self.roots, cursor=self.cursor, final=self.digest,
            terminal=self.terminal,
            stages=tuple((name, self.counts[name]) for name in rules.STAGE_ORDER),
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
