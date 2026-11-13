"""Tests for the release_audit toolkit, including the acceptance tests against the frozen pilot."""
import io
import json
import math
import shutil
import tempfile
import unittest
from collections import OrderedDict
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path

from release_audit import __main__ as cli
from release_audit import audit_spec, budget, measures, model, realdata, search, viewdefs

ROOT = Path(__file__).resolve().parent.parent
HOUSEHOLD = ROOT / "examples" / "household" / "spec.json"
GROCERY = ROOT / "examples" / "grocery" / "spec.json"


def tiny_spec(**over):
    s = {"name": "tiny", "target": {"name": "t", "values": ["a", "b"], "prior": ["1/2", "1/2"]},
         "fields": [{"name": "s1.x", "stage": "s1", "values": ["p", "q"], "parents": ["t"],
                     "cpt": {"a": ["3/4", "1/4"], "b": ["1/4", "3/4"]}}],
         "items": [{"name": "copy_x", "no_action": ["p"], "rules": [{"value": {"field": "s1.x"}}]}]}
    s.update(over)
    return s


class Acceptance(unittest.TestCase):
    """examples/household/spec.json must reproduce the frozen oracle (protocol section 3.9 / R1)."""

    @classmethod
    def setUpClass(cls):
        from lfi import oracle
        cls.m = model.load(HOUSEHOLD)
        cls.joint = model.enumerate_joint(cls.m)
        cls.ev = measures.Evaluator(cls.joint)
        cls.orc = oracle.build("main")
        cls.pop = oracle.population(cls.orc)
        cls.oracle = oracle

    def test_raw_space(self):
        self.assertEqual(len(self.joint), 65664)

    def test_bayes_accuracy_exact_and_mi(self):
        for v in "ABCDE":
            lk = self.ev.leakage(self.m.views[v])
            self.assertEqual(lk["bayes_accuracy"], self.pop[v]["bayes_accuracy"], v)
            self.assertLess(abs(lk["mi_bits"] - self.pop[v]["mi_bits"]), 1e-12, v)
            self.assertEqual(lk["p_exclusion"], self.pop[v]["p_exclusion"], v)
            self.assertEqual(lk["nb_limit"], self.oracle.nb_limit(self.orc, v), v)

    def test_entailment_equals_frozen_strict_renderer_on_every_record(self):
        from lfi import checklist, spec as lspec, views as lviews
        self.assertEqual([it.name for it in self.m.items], list(lspec.ITEMS))
        for v in "ABCDE":
            ent = self.ev.entailed_outputs(self.m.views[v])
            for rec, e in zip(self.joint.records, ent):
                st = checklist.render_strict(lviews.make_view(v, self.m.record_dict(rec), None))
                self.assertEqual(tuple(st[i] for i in lspec.ITEMS), e)

    def test_budget_finds_the_interaction_unaided(self):
        b = budget.budget(self.ev)
        top = b["pairs"][0]
        self.assertEqual(top["fields"], ("r1.event_code", "r2.resolution"))
        self.assertGreater(top["synergy_bits"], 0.03)
        self.assertTrue(top["exclusion_only_when_linked"])
        self.assertEqual([p["fields"] for p in b["pairs"] if p["exclusion_only_when_linked"]],
                         [("r1.event_code", "r2.resolution")])
        ev_alone = [r for r in b["fields"] if r["field"] == "r1.event_code"][0]
        self.assertLess(abs(ev_alone["mi_alone"]), 1e-12)          # size carries nothing alone
        self.assertGreater(ev_alone["mi_loss_if_dropped"], 0.02)   # ... but matters in the linked view


class Spec(unittest.TestCase):
    def test_tiny_by_hand(self):
        ev = measures.Evaluator(model.enumerate_joint(model.load(tiny_spec())))
        m = ev.model
        lk = ev.leakage(m.views["linked"])
        self.assertEqual(lk["bayes_accuracy"], Fraction(3, 4))
        h = -(0.75 * math.log2(0.75) + 0.25 * math.log2(0.25))
        self.assertAlmostEqual(lk["mi_bits"], 1 - h, places=12)
        ut = ev.utility(m.views["linked"])
        self.assertEqual(ut["share"], 1)
        none = viewdefs.make_view(m, "nothing", {})
        self.assertEqual(ev.utility(none)["share"], 0)
        self.assertEqual(ev.leakage(none)["bayes_accuracy"], Fraction(1, 2))

    def test_rejects_bad_specs(self):
        bad = [
            {"fields": [{"name": "s1.x", "stage": "s1", "values": ["p", "q"], "parents": ["t"],
                         "cpt": {"a": ["0.5", "0.4"], "b": ["0.5", "0.5"]}}]},           # row does not sum to 1
            {"fields": [{"name": "s1.x", "stage": "s1", "values": ["p", "q"], "parents": ["zz"],
                         "cpt": {"a": ["1", "0"]}}]},                                       # unknown parent
            {"fields": [{"name": "s1.x", "stage": "s1", "values": ["p", "q"], "parents": ["t"],
                         "cpt": {"a": ["1", "0"]}}]},                                       # missing parent value
            {"items": [{"name": "leaky", "rules": [{"value": {"field": "t"}}]}]},            # item reads the target
        ]
        for over in bad:
            with self.assertRaises(model.SpecError):
                model.load(tiny_spec(**over))

    def test_hard_zero_gives_exclusion_and_determination(self):
        s = tiny_spec(fields=[{"name": "s1.x", "stage": "s1", "values": ["p", "q"], "parents": ["t"],
                               "cpt": {"a": ["1", "0"], "b": ["1/2", "1/2"]}}])
        ev = measures.Evaluator(model.enumerate_joint(model.load(s)))
        lk = ev.leakage(ev.model.views["linked"])
        self.assertEqual(lk["p_exclusion"], Fraction(1, 4))
        self.assertEqual(lk["p_determined"], Fraction(1, 4))


class MonteCarlo(unittest.TestCase):
    def test_fallback_is_close_to_exact(self):
        m = model.load(GROCERY)
        exact = measures.Evaluator(model.enumerate_joint(m))
        joint = model.build_joint(m, max_records=100, mc_samples=40000, seed=5)
        self.assertFalse(joint.exact)
        mc = measures.Evaluator(joint)
        for v in ("linked", "coarsened"):
            a = exact.leakage(m.views[v])
            b = mc.leakage(m.views[v])
            self.assertLess(abs(float(a["bayes_accuracy"]) - b["bayes_accuracy_heldout"]), 5 * b["bayes_accuracy_heldout_se"] + 0.01)
            self.assertLess(abs(a["mi_bits"] - b["mi_bits_miller_madow"]), 0.02)

    def test_sampling_is_deterministic(self):
        m = model.load(GROCERY)
        self.assertEqual(model.sample(m, 50, 3), model.sample(m, 50, 3))


class Search(unittest.TestCase):
    def test_frontier_is_monotone_and_contains_items_only(self):
        m = model.load(GROCERY)
        ev = measures.Evaluator(model.enumerate_joint(m))
        res = search.run(ev, workers=1)
        self.assertTrue(res["exhaustive"])
        fr = sorted([r for r in res["results"] if r["frontier_mi"]], key=lambda r: r["mi_bits"])
        us = [float(r["utility"]) for r in fr]
        self.assertEqual(us, sorted(us))
        self.assertIn("items only", [r["label"] for r in fr])


class RealData(unittest.TestCase):
    def test_runs_and_is_deterministic(self):
        rows = realdata.load_csv(ROOT / "examples" / "grocery" / "records.csv", "young_children")[:200]
        m = model.load(GROCERY)
        a = realdata.run(rows, "young_children", m, k=4, seed=1, fractions=(0.5, 1.0), lr_iterations=20)
        b = realdata.run(rows, "young_children", m, k=4, seed=1, fractions=(0.5, 1.0), lr_iterations=20)
        self.assertEqual(a, b)
        self.assertEqual(a["views"]["linked"]["observed_utility"], 1)
        for v in a["views"].values():
            self.assertTrue(0.4 < v["attackers"]["nb"]["accuracy"] < 1.0)


class CommittedOutputs(unittest.TestCase):
    """The example outputs in the repository are what the tool produces now."""

    def _regen(self, spec, extra):
        tmp = Path(tempfile.mkdtemp(prefix="ra-test-"))
        try:
            with redirect_stdout(io.StringIO()):
                cli.main([str(spec), "--out", str(tmp), "--workers", "1"] + extra)
            return {p.name: p.read_bytes() for p in tmp.iterdir()}
        finally:
            shutil.rmtree(str(tmp))

    def test_grocery_report_is_current(self):
        got = self._regen(GROCERY, [])
        for name, data in got.items():
            self.assertEqual(data, (ROOT / "examples" / "grocery" / "output" / name).read_bytes(), name)

    def test_household_views_and_budget_are_current(self):
        got = self._regen(HOUSEHOLD, ["--no-search"])
        for name in ("views.csv", "items.csv", "budget_fields.csv", "budget_pairs.csv"):
            self.assertEqual(got[name], (ROOT / "examples" / "household" / "output" / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
