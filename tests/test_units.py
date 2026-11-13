"""Unit tests (standard-library unittest). Run: python3 -m unittest discover -s tests -t ."""
import hashlib
import json
import unittest
from fractions import Fraction
from pathlib import Path

from lfi import attacker, checklist, exposure, generator, metrics, oracle, spec, views

ROOT = Path(__file__).resolve().parent.parent
SMALL = (("train", 180), ("dev", 60), ("test", 60))

# Protocol section 11, copied verbatim: the exact input to each condition for hand example H1.
SECTION_11 = {
    "A": '{"r1.contact_channel":"phone","r1.essential_share":"50_70","r1.event_code":"medical_major","r1.income_pattern":"regular","r1.payment_flag":"overdraft_fee"}',
    "B": '{"r2.document_status":"missing_income_proof","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"instalment_plan"}',
    "C": '{"r1.contact_channel":"phone","r1.essential_share":"50_70","r1.event_code":"medical_major","r1.income_pattern":"regular","r1.payment_flag":"overdraft_fee","r2.document_status":"missing_income_proof","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"instalment_plan"}',
    "D": '{"r1.contact_channel":"phone","r1.essential_share_coarse":"up_to_70","r1.event_type":"medical","r1.income_pattern":"regular","r1.payment_difficulty":"any","r2.document_status":"missing_income_proof","r2.goal":"build_buffer","r2.payment_difficulty":"none","r2.resolution_coarse":"arranged"}',
    "E": '{"e.budget_session":"yes","e.contact_channel":"phone","e.documents_request":"income_proof","e.essential_cost_review":"no","e.expense_referral":"medical","e.goal_module":"build_buffer","e.hardship_review":"no","e.overdraft_guidance":"yes","e.plan_monitoring":"yes"}',
}
H1_RAW = json.loads(SECTION_11["C"])


class Seeds(unittest.TestCase):
    def test_subseed_formula(self):
        want = int.from_bytes(hashlib.sha256(b"20261113:main:generate").digest()[:8], "big")
        self.assertEqual(generator.subseed(20261113, "main", "generate"), want)

    def test_generation_is_deterministic_and_seed_dependent(self):
        a = generator.generate("main", n=300, split_sizes=SMALL)
        b = generator.generate("main", n=300, split_sizes=SMALL)
        c = generator.generate("main", master=1, n=300, split_sizes=SMALL)
        self.assertEqual(a["households"], b["households"])
        self.assertNotEqual(a["households"], c["households"])

    def test_split_sizes_and_disjointness(self):
        s = generator.assign_splits(10000, 123)
        self.assertEqual([s.count(n) for n, _ in spec.SPLIT_SIZES], [6000, 1000, 3000])


class Sampling(unittest.TestCase):
    def test_hard_zero_never_sampled(self):
        table = generator._table(spec.RESOLUTIONS, spec.RESOLUTION["major"]["low"])
        for u in (0.0, 1e-300, 0.2, 0.4499999, 0.45, 0.9999999999):
            self.assertNotEqual(generator.draw(table, u), "settled_in_full")

    def test_inverse_cdf_boundaries(self):
        table = generator._table(("a", "b", "c"), (Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)))
        self.assertEqual([generator.draw(table, u) for u in (0.0, 0.2499, 0.25, 0.7499, 0.75, 0.999)],
                         ["a", "a", "b", "b", "c", "c"])

    def test_mixing(self):
        ind, main, half = (generator.distributions(s) for s in ("independence", "main", "dep_050"))
        for field in spec.BAND_DEPENDENT:
            self.assertEqual(ind[field]["low"], ind[field]["high"])
            self.assertEqual(main[field]["low"], spec.BAND_DEPENDENT[field][1]["low"])
            for i in range(len(main[field]["low"])):
                self.assertEqual(half[field]["low"][i], (ind[field]["low"][i] + main[field]["low"][i]) / 2)
        self.assertEqual(main["resolution"][("major", "low")][0], 0)
        self.assertGreater(half["resolution"][("major", "low")][0], 0)
        skewed = generator.distributions("prev_skewed")
        self.assertEqual(skewed["r2.goal"], main["r2.goal"])  # prevalence variants keep lambda = 1


class Views(unittest.TestCase):
    def test_section_11_bytes(self):
        for v in spec.VIEWS:
            self.assertEqual(views.canonical(views.make_view(v, H1_RAW, "medium")), SECTION_11[v], v)

    def test_positive_control_band_field_survives_coarsening(self):
        d = views.make_view("D", H1_RAW, "high", band_field=True)
        self.assertEqual((d["r1.reserve_band"], d["r2.reserve_band"]), ("high", "high"))
        self.assertNotIn("r2.reserve_band", views.make_view("A", H1_RAW, "high", band_field=True))

    def test_coarsening_keeps_every_field(self):
        self.assertEqual(len(views.make_view("D", H1_RAW, None)), len(spec.RAW_FIELDS))
        raw = dict(H1_RAW, **{"r1.event_code": "none", "r2.resolution": "not_applicable"})
        d = views.make_view("D", raw, None)
        self.assertEqual((d["r1.event_type"], d["r2.resolution_coarse"]), ("none", "not_applicable"))


class Renderers(unittest.TestCase):
    def test_partial_evidence_settles_budget_session(self):
        self.assertEqual(checklist.render_strict({"r1.payment_flag": "late_utility"})["budget_session"], "yes")
        self.assertIsNone(checklist.render_strict({"r1.payment_flag": "none"})["budget_session"])

    def test_coarse_any_cannot_settle_overdraft(self):
        x = {"r1.payment_difficulty": "any", "r2.payment_difficulty": "none"}
        self.assertIsNone(checklist.render_strict(x)["overdraft_guidance"])
        x = {"r1.payment_difficulty": "none", "r2.payment_difficulty": "none"}
        self.assertEqual(checklist.render_strict(x)["overdraft_guidance"], "no")

    def test_default_fill(self):
        out = checklist.render_default({"r2.goal": "none"})
        self.assertEqual(out["contact_channel"], "email")
        self.assertEqual(out["expense_referral"], "none")
        self.assertEqual(out["hardship_review"], "no")

    def test_view_c_and_e_never_abstain_and_strict_never_wrong(self):
        data = generator.generate("main", n=300, split_sizes=SMALL)
        for h in data["households"]:
            ans = checklist.correct_answers(h["raw"])
            for v in spec.VIEWS:
                out = checklist.render_strict(views.make_view(v, h["raw"], h["band"]))
                for it in spec.ITEMS:
                    self.assertNotEqual(checklist.outcome(ans[it], out[it]), "unsupported")
                    if v in ("C", "E"):
                        self.assertEqual(out[it], ans[it])


class Attacker(unittest.TestCase):
    def test_unseen_value_is_skipped(self):
        nb = attacker.NaiveBayes([{"f": "a"}, {"f": "a"}, {"f": "b"}], ["low", "low", "high"])
        post, skipped, fallbacks = nb.posterior({"f": "zzz"})
        self.assertEqual((skipped, fallbacks), (1, 0))
        self.assertEqual(post, {b: nb.prior[b] for b in spec.BANDS})

    def test_optional_field_denominator_counts_rows_carrying_the_field(self):  # v1.1, review 2.6
        nb = attacker.NaiveBayes([{"f": "a", "g": "p"}, {"f": "a"}, {"f": "b", "g": "q"}], ["low", "low", "high"])
        self.assertEqual(nb.likelihood("g", "p", "low"), (2, 1 + 3))  # one low row carries g; K = 2, +1 slot
        self.assertEqual(nb.likelihood("f", "a", "low"), (3, 2 + 3))

    def test_nb_pair_falls_back_to_marginals_for_unseen_joint_value(self):  # v1.1, review 2.6
        rows = [{"id": "r1", "x": {"r1.event_code": "home_minor", "r2.resolution": "settled_in_full"}, "y": "low"},
                {"id": "r2", "x": {"r1.event_code": "home_major", "r2.resolution": "outstanding"}, "y": "high"},
                {"id": "s1", "x": {"r1.event_code": "home_minor", "r2.resolution": "outstanding"}}]
        out = attacker.run(rows)[0]
        self.assertEqual(out["nb_pair"]["p"], out["nb"]["p"])
        self.assertEqual((out["nb_pair"]["pair_fallbacks"], out["nb_pair"]["skipped"]), (1, 0))

    def test_lookup_threshold(self):
        rows = [{"x": {"f": "a"}, "y": "high"}] * 4 + [{"x": {"f": "b"}, "y": "high"}] * 5
        rows = [dict(r, id="r%d" % i) for i, r in enumerate(rows)] + [{"id": "s1", "x": {"f": "a"}},
                                                                        {"id": "s2", "x": {"f": "b"}}]
        out = attacker.run(rows)
        self.assertEqual([o["lookup"]["covered"] for o in out], [False, True])
        self.assertEqual(out[1]["lookup"]["p"], [0.125, 0.125, 0.75])

    def test_pair_feature(self):
        x = {"r1.event_type": "home", "r2.resolution_coarse": "arranged", "r2.goal": "none"}
        self.assertEqual(attacker.pair_features(x),
                         {"r2.goal": "none", "r1.event_type+r2.resolution_coarse": "home|arranged"})

    def test_ties_break_low_medium_high(self):
        self.assertEqual(attacker.argmax({"low": 1, "medium": 2, "high": 2}), "medium")
        self.assertEqual(attacker.argmax({"low": 2, "medium": 2, "high": 2}), "low")


class Oracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = oracle.build("main")
        cls.pop = oracle.population(cls.main)

    def test_exact_sums_and_exclusion(self):
        self.assertTrue(all(r["band_sums_ok"] for r in self.pop.values()))
        # P(major, settled_in_full) = 0.5 * 0.4 * (0.35 * 0.25 + 0.25 * 0.80) exactly
        self.assertEqual(self.pop["C"]["p_exclusion"], Fraction(1, 2) * Fraction(2, 5) * (
            Fraction(35, 100) * Fraction(1, 4) + Fraction(1, 4) * Fraction(4, 5)))
        for v in ("A", "B", "D", "E"):
            self.assertEqual(self.pop[v]["p_exclusion"], 0)

    def test_independence_has_no_information(self):
        pop = oracle.population(oracle.build("independence"))
        for v in spec.VIEWS:
            self.assertEqual(pop[v]["bayes_accuracy"], Fraction(2, 5))
            self.assertLess(abs(pop[v]["mi_bits"]), 1e-9)


class Metrics(unittest.TestCase):
    def test_percentile_positions(self):
        self.assertEqual(metrics.percentile_ci(list(range(2000))), (50, 1949))

    def test_macro_recall_reports_absent_band(self):
        pt = metrics.point(["low", "low", "high"], ["low", "medium", "high"], [0.5, 0.2, 0.9])
        self.assertEqual(pt["bands_absent"], ["medium"])
        self.assertAlmostEqual(pt["macro_recall"], 0.75)

    def test_bootstrap_paired_difference_of_identical_series_is_zero(self):
        s = {"a": ([1, 0, 1, 1], [0.1, 2.0, 0.3, 0.4]), "b": ([1, 0, 1, 1], [0.1, 2.0, 0.3, 0.4])}
        boot = metrics.bootstrap(5, [0, 1, 2, 0], s, n_resamples=50)
        ci = metrics.paired(boot, "a", "b", 4)
        self.assertEqual(ci["accuracy"], (0, 0))
        self.assertEqual(ci["logloss"], (0.0, 0.0))


class Exposure(unittest.TestCase):
    def test_scan(self):
        stdin = b"\n".join([views.training_line("t1", {"r1.goal": "none"}, "low"),
                            views.scored_line("s1", {"r2.reserve_band": "high"}),
                            views.scored_line("s2", {"r2.goal": "medium"}),
                            views.scored_line("s3", {"r2.goal": "none"})]) + b"\n"
        s = exposure.scan(stdin)
        self.assertEqual((s["train_exposed"], s["scored_exposed"], s["exposed_scored_ids"]), (0, 2, ["s1", "s2"]))

    def test_scan_is_structural_not_substring(self):  # v1.1, review 2.5
        stdin = b"\n".join([views.scored_line("s1", {"r1.broadband_bill": "paid"}),
                            views.scored_line("s2", {"r1.husband_income": "regular"}),
                            views.scored_line("s3", {"r2.goal": "LOW"})]) + b"\n"
        self.assertEqual(exposure.scan(stdin)["scored_exposed"], 0)  # documented scope: literal only


if __name__ == "__main__":
    unittest.main()
