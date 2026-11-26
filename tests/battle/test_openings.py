"""14.1 openings, descriptors and provenance; 11.4 oracle; restored P, B and M rows."""

import copy
import hashlib

import imperium.battle as B
from imperium.battle import canon as canon_module
from tests.battle import oracle
from tests.battle.common import (
    BattleCase, a1, canon, fi, individual,
)
from tests.support.battle_builder import as_adversarial, build, edit, opening_document

ORACLE = oracle.sealed_documents()
VARIANTS = [B.Variant.OPEN, B.Variant.ROUGH, B.Variant.BARRIER]


def fixture_state(fid):
    d = B.descriptor(B.FixtureId(fid))
    if d.fixture_class is B.FixtureClass.CANONICAL_OPENING:
        return B.f01_opening(d.variant, d.orientation)
    return B.f01_supplied(B.FixtureId(fid))


class OracleTests(BattleCase):
    """AT-O01, AT-O16, C08, M06: the independent oracle procedure of 11.4."""

    def test_at_o01_oracle_equality(self):
        self.assertEqual(len(ORACLE), 8)
        for (fid, doc, n, full), d in zip(ORACLE, B.DESCRIPTORS):
            with self.subTest(fid):
                self.assertEqual(d.fixture_id, B.FixtureId(fid))
                state = B.decode_bytes(canon(doc))
                self.assertEqual(B.canonical_bytes(state), canon(doc))
                self.assertEqual(B.decode_state(B.encode_state(state)), state)
                self.assertEqual(fixture_state(fid), state)
                self.assertEqual(d.normalized_genesis_digest, n)
                self.assertEqual(d.full_genesis_digest, full)

    def test_at_o16_two_digests(self):
        for fid, doc, n, full in ORACLE:
            with self.subTest(fid):
                zeroed = copy.deepcopy(doc)
                zeroed["scenario"]["provenance"]["origin_digest"] = "0" * 64
                self.assertEqual(hashlib.sha256(canon(zeroed)).hexdigest(), n)
                self.assertEqual(hashlib.sha256(canon(doc)).hexdigest(), full)
                self.assertNotEqual(n, full)
                state = fixture_state(fid)
                self.assertEqual(state.scenario.provenance.origin_digest, n)
                self.assertEqual(B.normalized_digest(state), n)
                self.assertEqual(B.digest(state), full)

    def test_at_o16_swapped_descriptor_fails_comparison(self):
        # A test-local descriptor with N and F swapped, passed to the comparisons
        # under test (P10(a) uses N, P10(b) uses F); no runtime registration.
        for fid, doc, n, full in ORACLE:
            state = fixture_state(fid)
            values = tuple(getattr(state, name) for name in canon_module.STATE_FIELDS)
            swapped_n, swapped_f = full, n
            with self.subTest(fid):
                self.assertNotEqual(canon_module.normalized_digest(values), swapped_n)
                self.assertNotEqual(canon_module.full_digest(values), swapped_f)
                self.assertEqual(canon_module.normalized_digest(values), n)
                self.assertEqual(canon_module.full_digest(values), full)

    def test_m06_descriptor_shape(self):
        for d in B.DESCRIPTORS:
            self.assertIs(type(d), B.FixtureDescriptor)
            self.assertEqual(d.scenario_version, "F01-v1")
            self.assertEqual(d.rules_baseline, "D3-v0.2+A01-A25")
            self.assertEqual(d.profile_id, "D4-RP-0.1")
        self.assertEqual(B.DESCRIPTORS[7].genesis_phase, "TERMINAL")
        self.assertIs(B.DESCRIPTORS[7].genesis_point, B.TerminationPoint.INITIAL_CHECK)
        for d in B.DESCRIPTORS[:7]:
            self.assertEqual(d.genesis_phase, "OPENING")
            self.assertIsNone(d.genesis_point)


class DescriptorApiTests(BattleCase):
    def test_at_o15(self):
        ids = [d.fixture_id.token for d in B.DESCRIPTORS]
        self.assertEqual(ids, [fid for fid, _, _, _ in ORACLE])
        for d in B.DESCRIPTORS:
            self.assertIs(B.descriptor(d.fixture_id), d)
        self.assertEqual([i.token for i in B.canonical_ids()], ids[:6])
        self.assertEqual([i.token for i in B.supplied_ids()], ids[6:])
        for fid in B.supplied_ids():
            self.assertIs(type(B.f01_supplied(fid)), B.BattleState)
        with self.assertRaises(B.UnknownId):
            B.descriptor(B.FixtureId("F01-v1-nope"))
        with self.assertRaises(B.UnknownId):
            B.f01_supplied(B.FixtureId("F01-v1-open-standard"))
        for fn in (B.descriptor, B.f01_supplied):
            with self.assertRaises(B.InvalidValue) as cm:
                fn("F01-v1-open-standard")
            self.assertEqual(cm.exception.clause, "T07")


class MirrorTests(BattleCase):
    def test_at_o02_m01(self):
        for v in VARIANTS:
            with self.subTest(v):
                standard = B.f01_opening(v, B.Orientation.STANDARD)
                mirrored = B.f01_opening(v, B.Orientation.MIRRORED)
                self.assertEqual(B.mirror_state(standard), mirrored)
                self.assertEqual(B.mirror_state(mirrored), standard)
                self.assertEqual(B.mirror_state(B.mirror_state(standard)), standard)

    def test_mirror_domain(self):
        with self.assertRaises(B.InvalidValue) as cm:
            B.mirror_state(B.f01_supplied(B.supplied_ids()[0]))
        self.assertEqual(cm.exception.clause, "P10")
        with self.assertRaises(B.InvalidValue) as cm:
            B.mirror_state(build(a1()))
        self.assertEqual(cm.exception.clause, "P10")
        with self.assertRaises(B.InvalidValue) as cm:
            B.mirror_state(object())
        self.assertEqual(cm.exception.clause, "V00")

    def test_m02_m03_m04(self):
        for v in VARIANTS:
            for o in B.Orientation:
                s = B.f01_opening(v, o)
                for side in B.Side:
                    t = B.side_totals(s, side)
                    self.assertEqual((t.available, t.mounts, t.ammunition_carried), (1640, 80, 16))
                cells = {(x.cell.q, x.cell.r) for x in s.formations}
                self.assertEqual(len(cells), 16)
                self.assertNotIn((5, 4), cells)
                self.assertEqual(B.objective_status(s).kind, B.ObjectiveKind.UNHELD)
        for o in ("STANDARD", "MIRRORED"):
            base = opening_document("OPEN", o)
            for v in ("ROUGH", "BARRIER"):
                other = opening_document(v, o)
                diff = {k for k in base if base[k] != other[k]}
                self.assertEqual(diff, {"scenario"})
                sb, so = base["scenario"], other["scenario"]
                self.assertEqual({k for k in sb if sb[k] != so[k]}, {"board", "provenance"})
                pb, po = sb["provenance"], so["provenance"]
                self.assertEqual({k for k in pb if pb[k] != po[k]},
                                 {"variant", "fixture_id", "origin_digest"})

    def test_mirror_cells_and_facings(self):
        s = B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)
        m = B.f01_opening(B.Variant.OPEN, B.Orientation.MIRRORED)
        self.assertEqual(B.formation(s, B.FormationId("S1.H1")).cell, B.Hex(8, 2))
        self.assertEqual(B.formation(m, B.FormationId("S1.H1")).cell, B.Hex(2, 6))
        self.assertEqual(B.formation(s, B.FormationId("S0.H1")).facing, 4)
        self.assertEqual(B.formation(m, B.FormationId("S0.H1")).facing, 1)
        self.assertIs(B.end_of(s.scenario, B.Side.S0), B.End.RED)
        self.assertIs(B.end_of(m.scenario, B.Side.S0), B.End.BLUE)


class ProvenanceTests(BattleCase):
    def test_at_o03_first_side(self):
        self.reject(edit(a1(), "/scenario/first_side", "S1"), "P06")

    def test_at_o04_mirrored_round1(self):
        d = a1(orientation="MIRRORED")
        d["ledger"]["uses"] = [individual("S0", "S0.H1", {"kind": "Hold"})]
        d["phase"]["side"] = "S1"
        s = self.accept(d)
        self.assertIs(B.next_side(s), B.Side.S1)
        self.assertIs(B.end_of(s.scenario, B.Side.S0), B.End.BLUE)

    def test_at_o05_r11c_round2_first_use_by_s0(self):
        d = a1()
        d["clock"]["completed_rounds"] = 1
        d["ledger"]["uses"] = [individual("S0", "S0.H1", {"kind": "Hold"})]
        d["phase"]["side"] = "S1"
        self.reject(d, "R11")
        ok = a1()
        ok["clock"]["completed_rounds"] = 1
        ok["ledger"]["uses"] = [individual("S1", "S1.H1", {"kind": "Hold"})]
        ok["phase"]["side"] = "S0"
        self.accept(ok)

    def test_at_o06_edited_canonical(self):
        self.reject(edit(opening_document(), "/formations/1/facing", 3), "P10")

    def test_at_o07_edited_adversarial(self):
        self.accept(as_adversarial(edit(opening_document(), "/formations/1/facing", 3), "O07"))

    def test_at_o08_p09(self):
        d = as_adversarial(opening_document(), "X")
        self.reject(edit(d, "/scenario/provenance/fixture_id", "NOPE-1"), "P09")
        self.reject(edit(d, "/scenario/provenance/fixture_id", "F01-v1-open-standard"), "P09")

    def test_at_o09(self):
        shortfall = B.encode_state(B.f01_supplied(B.supplied_ids()[0]))
        # (a) S1.C1 split too
        a = copy.deepcopy(shortfall)
        lots = [m for m in a["mounts"] if m["formation"] != "S1.C1"]
        base = [m for m in a["mounts"] if m["formation"] == "S1.C1"][0]
        m0 = dict(base, count=70)
        m1 = dict(base, lot="S1.C1:M1", count=10, serviceability="UNSERVICEABLE")
        a["mounts"] = sorted(lots + [m0, m1], key=lambda m: m["lot"])
        self.reject(a, "P10")
        defensive = B.encode_state(B.f01_supplied(B.supplied_ids()[1]))
        # (b) two separately modified defensive carriers
        self.reject(edit(defensive, f"/formations/{fi('S0.H1')}/facing", 3), "P10")
        self.reject(edit(defensive, "/clock/event_cursor", 1), "P10")
        # (c) the defensive contents under the shortfall id with the shortfall N
        c = copy.deepcopy(defensive)
        c["scenario"]["provenance"]["fixture_id"] = shortfall["scenario"]["provenance"]["fixture_id"]
        c["scenario"]["provenance"]["origin_digest"] = shortfall["scenario"]["provenance"]["origin_digest"]
        clauses = [v.clause for v in self.violations(c)]
        self.assertIn("P10", clauses)
        self.assertIn("X05", clauses)
        # (d) an unregistered supplied id
        self.reject(edit(shortfall, "/scenario/provenance/fixture_id", "F01-v1-supplied-nope"), "P08")

    def test_x_p01_defensive_switches(self):
        defensive = B.encode_state(B.f01_supplied(B.supplied_ids()[1]))
        self.reject(edit(defensive, "/scenario/provenance/orientation", "MIRRORED"), "P08")
        self.reject(edit(defensive, "/scenario/provenance/fixture_class", "CANONICAL_OPENING"), "P07")
        self.reject(edit(defensive, "/phase", {"kind": "Opening"}), "P10")

    def test_at_o10_p07_digest_of_other_opening(self):
        other = opening_document("ROUGH")["scenario"]["provenance"]["origin_digest"]
        self.reject(edit(opening_document(), "/scenario/provenance/origin_digest", other), "P07")

    def test_at_o11_barrier_rules(self):
        board = B.f01_board(B.Variant.BARRIER)
        self.assertEqual(
            [((e.source.q, e.source.r), (e.destination.q, e.destination.r), e.traversable,
              e.opaque, e.surcharge) for e in board.edges],
            [((3, 4), (4, 4), False, False, 0), ((4, 4), (3, 4), False, False, 0),
             ((6, 4), (7, 4), False, False, 0), ((7, 4), (6, 4), False, False, 0)])

    def test_at_o12_p03a(self):
        rule = {"source": [0, 0], "destination": [1, 0], "traversable": True, "opaque": False,
                "surcharge": 0}
        for v in ("OPEN", "ROUGH"):
            d = as_adversarial(opening_document(v), "O12")
            self.reject(edit(d, "/scenario/board/edges", [rule]), "P03")
        rough = as_adversarial(opening_document("ROUGH"), "P03")
        self.reject(edit(rough, "/scenario/board", opening_document("OPEN")["scenario"]["board"]), "P03")
        barrier = as_adversarial(opening_document("BARRIER"), "P03")
        self.reject(edit(barrier, "/scenario/board/edges", barrier["scenario"]["board"]["edges"][1:]), "P03")
        opaque = dict(rule, opaque=True)
        self.reject(edit(barrier, "/scenario/board/edges",
                         [opaque] + barrier["scenario"]["board"]["edges"]), "P03")

    def test_at_o13_b01a(self):
        d = as_adversarial(opening_document(), "B01")
        self.reject(edit(d, f"/formations/{fi('S0.H1')}/cell", [11, 4]), "B01")
        self.reject(edit(d, f"/formations/{fi('S0.H1')}/cell", [-1, 0]), "B01")
        l = a1()
        l["ledger"]["uses"] = [individual("S0", "S0.H1", {
            "kind": "Move", "declared": [[-1, 0]],
            "legs": [{"origin": [0, 0], "destination": [-1, 0], "facing": 3, "mode": "FOOT"}],
            "end": "COMPLETED"})]
        l["phase"]["side"] = "S1"
        self.reject(l, "B01")

    def test_at_o17_dormant_initial_branch(self):
        record = {"kind": "Terminal", "record": {
            "reason": "ZERO_VIABILITY_UNILATERAL", "result": "VICTORY", "winner": "S0",
            "defeat": [None, "COLLAPSE"], "point": "INITIAL_CHECK", "charged_rounds": 0,
            "objective": {"kind": "UNHELD", "side": None},
            "postures": ["CONTESTING", "CONTESTING"], "viable": [8, 0],
            "onmap_available": [1640, 1640], "exit_available": [0, 0]}}
        for doc in (opening_document(), B.encode_state(B.f01_supplied(B.supplied_ids()[0]))):
            clauses = [v.clause for v in self.violations(edit(doc, "/phase", record))]
            self.assertTrue({"X01", "X03"} & set(clauses))
            # Only the phase differs from the genesis, so the P10(c) projection
            # equals N: the branch is dormant and other clauses reject.
            self.assertNotIn("P10", clauses)
            changed = edit(edit(doc, "/phase", record), "/formations/1/facing", 3)
            self.assertIn("P10", [v.clause for v in self.violations(changed)])

    def test_at_o18_templates_triple(self):
        d = opening_document()
        templates = d["scenario"]["profile"]["templates"]
        self.decode_code(edit(d, "/scenario/profile/templates", templates[:2]), "JSON_TYPE",
                         "/scenario/profile/templates")
        profile = B.f01_scenario(B.Variant.OPEN, B.Orientation.STANDARD).profile
        with self.assertRaises(B.InvalidValue) as cm:
            B.Profile(*[profile.templates[:2] if n == "templates" else getattr(profile, n)
                        for n in profile.__dataclass_fields__])
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T04", "templates"))
        swapped = [templates[1], templates[0], templates[2]]
        self.reject(as_adversarial(edit(d, "/scenario/profile/templates", swapped), "O18"), "P01")

    def test_p01a_profile_values(self):
        d = as_adversarial(opening_document(), "P01")
        for pointer, value in [
            ("/scenario/profile/profile_id", "D4-RP-0.2"),
            ("/scenario/profile/exertion_threshold", 3),
            ("/scenario/profile/exertion_cleared_by", "RALLY"),
            ("/scenario/profile/packet/allocation", "B2"),
            ("/scenario/profile/packet/missile_pressure/0", "3/26"),
        ]:
            with self.subTest(pointer):
                self.reject(edit(d, pointer, value), "P01")
        templates = d["scenario"]["profile"]["templates"]
        self.reject(edit(d, "/scenario/profile/templates", [templates[1], templates[0], templates[2]]), "P01")

    def test_p01b_profile_from_d4(self):
        for v in VARIANTS:
            for o in B.Orientation:
                p = B.f01_opening(v, o).scenario.profile
                self.assertEqual(B.encode_state(B.f01_opening(v, o))["scenario"]["profile"], oracle.profile())
                self.assertEqual((p.opportunities, p.effort, p.exertion_threshold, p.rounds,
                                  p.round_minutes, p.hex_pitch_m), (4, 3, 6, 12, 10, 65))

    def test_p02a(self):
        d = as_adversarial(opening_document(), "P02")
        sources = d["scenario"]["provenance"]["sources"]
        bad = sources[0][:-1] + ("0" if sources[0][-1] != "0" else "1")
        self.reject(edit(d, "/scenario/provenance/sources/0", bad), "P02")
        self.reject(edit(d, "/scenario/provenance/sources", [sources[1], sources[0], sources[2]]), "P02")
        for key, value in [("scenario_id", "F02"), ("scenario_version", "F01-v2"),
                           ("profile_id", "D4-RP-0.2"), ("rules_baseline", "D3-v0.3")]:
            self.reject(edit(d, f"/scenario/provenance/{key}", value), "P02")

    def test_p04a(self):
        d = as_adversarial(opening_document(), "P04")
        roster = d["scenario"]["roster"]
        self.reject(edit(d, "/scenario/roster", roster[:-1]), "P04")
        self.reject(edit(d, f"/scenario/roster/{fi('S0.H1')}/template", "MOUNTED"), "P04")
        self.reject(edit(d, f"/scenario/roster/{fi('S0.L1')}/side", "S1"), "P04")

    def test_p05a(self):
        d = as_adversarial(opening_document(), "P05")
        self.reject(edit(d, "/scenario/groups/0/members", ["S0.H1", "S0.H2", "S0.H3"]), "P05")

    def test_at_r01(self):
        d = edit(opening_document(), f"/formations/{fi('S0.H1')}/condition/fatigue", 2)
        self.reject(d, "P10")
        self.accept(as_adversarial(d, "R01"))


class CanonicalAcceptTests(BattleCase):
    def test_all_eight_round_trip(self):
        for fid, doc, _, _ in ORACLE:
            with self.subTest(fid):
                self.accept(doc)



