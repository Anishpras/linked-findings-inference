"""Post-review (v1.1) outputs: H2a seed runs, corrections, E versus D, exploratory controls, and
the delta against the frozen v1.0 outputs (Revisions v1.1; independent review of 2026-11-13).

Labels used throughout:
  "frozen v1.0"                      computed exactly as at the v1.0 freeze;
  "post-review correction (v1.1)"    a correction or relabelling of a v1.0 output;
  "exploratory, post-review (v1.1)"  new, not pre-specified, added after the test results were seen.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

from . import exact_utility, exploratory, metrics, spec
from .report import frac, paired_estimate, write_csv


def f4(x):
    """v1.1 outputs round first, so float noise such as -1e-17 prints as 0.0000 (the frozen v1.0
    outputs keep their original formatting)."""
    return "%.4f" % (round(float(x), 10) + 0.0)


def f6(x):
    return "%.6f" % (round(float(x), 12) + 0.0)

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "results_v1.0"
OUTPUTS = ("h2a_seed_runs.csv", "h2a_summary.md", "post_review_corrections.md", "utility_exact.csv",
           "e_vs_d.csv", "exploratory_e_vs_d.md", "exploratory_controls.csv", "learning_curve.csv",
           "exploratory_controls.md", "revision_v1.1_delta.md")
T_975_DF5 = 2.570582  # two-sided 95% Student t quantile, 5 degrees of freedom
Z_975 = 1.959964
DEFENSIBLE_CLAIM = ("releasing task outputs always dominates the linked fine release (same utility, 0.565 against "
                    "0.604 here) and still leaks (16.5 points over baseline, more than either single release); "
                    "against a coarsening it is not ordered in general.")


def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def seed_runs(runs):
    return [runs["main"]] + [runs["main_rep%d" % k] for k in range(1, spec.N_REPLICATES + 1)]


def seed_rows(runs, x, y, models=("nb", "nb_pair", "oracle")):
    """Per seed run and model: the paired X - Y estimate and intervals (accuracy, log-loss)."""
    out = []
    for k, r in enumerate(seed_runs(runs)):
        for m in models:
            e = paired_estimate(r, (x, m), (y, m))
            out.append(OrderedDict([("seed_run", k), ("master_seed", r["master_seed"]), ("model", m),
                                    ("comparison", "%s-%s" % (x, y)), ("acc", e["accuracy"]),
                                    ("logloss", e["logloss_bits"]), ("discordant", e["discordant"])]))
    return out


def _ci_excludes(lo, hi):
    return lo > 0 or hi < 0


def _mean_sd(xs):
    m = math.fsum(xs) / len(xs)
    sd = math.sqrt(math.fsum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return m, sd


# ---------------------------------------------------------------- checks
def checks(runs, pops, extras):
    from .validate import result
    out = []
    eu = extras[("exact_utility", "main")]
    wrong = [k for k, s in eu.items() if s["supported_wrong"] != 0]
    out.append(result("x_v1_1_exact_strict_renderer_never_wrong", not wrong,
                      "exact enumeration over every raw record: supported-wrong mass is 0 in every view"
                      if not wrong else "nonzero for %s" % wrong))
    bad = []
    for s, pop in pops.items():
        for v, (nl, npl) in extras[("nb_limits", s)].items():
            if nl > pop[v]["bayes_accuracy"] or npl > pop[v]["bayes_accuracy"]:
                bad.append("%s/%s" % (s, v))
    out.append(result("x_v1_1_nb_limit_not_above_bayes", not bad, "violations: %s" % bad if bad else ""))
    var = extras[("e_vs_d_variants", "main")]
    ok = (var["C (linked fine releases)"]["bayes_accuracy"] == pops["main"]["C"]["bayes_accuracy"]
          and var["D"]["bayes_accuracy"] == pops["main"]["D"]["bayes_accuracy"]
          and var["E"]["bayes_accuracy"] == pops["main"]["E"]["bayes_accuracy"])
    out.append(result("x_v1_1_e_vs_d_variants_match_oracle", ok, "C, D and E variants equal the oracle's exact values"))
    return out


# ---------------------------------------------------------------- H2a
def h2a(out, runs, pops, extras):
    rows = seed_rows(runs, "D", "C")
    csv_rows = []
    for r in rows:
        a, l_ = r["acc"], r["logloss"]
        csv_rows.append([r["seed_run"], r["master_seed"], r["model"], r["comparison"], f4(a[0]), f4(a[1]), f4(a[2]),
                         a[0] < 0 and a[2] < 0, f4(l_[0]), f4(l_[1]), f4(l_[2]), _ci_excludes(l_[1], l_[2]),
                         r["discordant"][0], r["discordant"][1], EXPLORATORY if r["seed_run"] else FROZEN_PRIMARY])
    write_csv(out / "h2a_seed_runs.csv",
              ["seed_run", "master_seed", "model", "comparison", "accuracy_diff", "accuracy_ci_low", "accuracy_ci_high",
               "meets_h2a_criterion", "logloss_diff_bits", "logloss_ci_low", "logloss_ci_high", "logloss_ci_excludes_0",
               "correct_D_only", "correct_C_only", "label"], csv_rows)

    nb = [r for r in rows if r["model"] == "nb"]
    accs = [float(r["acc"][0]) for r in nb]
    met = sum(1 for r in nb if r["acc"][0] < 0 and r["acc"][2] < 0)
    mean, sd = _mean_sd(accs)
    half = T_975_DF5 * sd / math.sqrt(len(accs))
    ses = sorted(float(r["acc"][2] - r["acc"][1]) / (2 * Z_975) for r in nb)
    se = (ses[2] + ses[3]) / 2  # median of six
    bayes_gap = pops["main"]["D"]["bayes_accuracy"] - pops["main"]["C"]["bayes_accuracy"]
    lim = extras[("nb_limits", "main")]
    nb_gap = lim["D"][0] - lim["C"][0]
    nbp_gap = lim["D"][1] - lim["C"][1]
    power_mean = _phi(abs(mean) / se - Z_975)
    power_lim = _phi(abs(float(nb_gap)) / se - Z_975)
    power_bayes = _phi(abs(float(bayes_gap)) / se - Z_975)
    ll_ex = sum(1 for r in nb if _ci_excludes(r["logloss"][1], r["logloss"][2]))
    ll_range = (min(float(r["logloss"][0]) for r in nb), max(float(r["logloss"][0]) for r in nb))
    p0 = nb[0]

    L = ["# H2a across seed runs (post-review, v1.1)", "",
         "Label: the primary result is **frozen v1.0 (confirmatory)**. Everything else on this page is "
         "**exploratory, post-review (v1.1)**, added after the test results were seen (independent review of "
         "2026-11-13, sections 2.1 and 4.3).", "",
         "## Confirmatory result (unchanged)", "",
         "nb accuracy D - C on the pre-specified seed: **%s [%s, %s]**, %s under the frozen criterion."
         % (f4(p0["acc"][0]), f4(p0["acc"][1]), f4(p0["acc"][2]),
            "supported" if (p0["acc"][0] < 0 and p0["acc"][2] < 0) else "not supported"), "",
         "## All six seed runs (nb)", "",
         "Seed run 0 is the primary run. Runs 1-5 are the seed replicates of protocol section 3.6, each with its own "
         "10,000 households, split and training. Intervals are paired 95% percentile bootstraps (2,000 resamples of "
         "the scored households), which cover test-sample uncertainty only.", "",
         "| Seed run | D - C accuracy | 95% CI | Meets criterion | D - C log-loss (bits) | 95% CI |", "|---|---|---|---|---|---|"]
    for r in nb:
        a, l_ = r["acc"], r["logloss"]
        L.append("| %d | %s | [%s, %s] | %s | %s | [%s, %s] |" % (r["seed_run"], f4(a[0]), f4(a[1]), f4(a[2]),
                                                                  "yes" if (a[0] < 0 and a[2] < 0) else "no",
                                                                  f4(l_[0]), f4(l_[1]), f4(l_[2])))
    L += ["", "**%d of 6 seed runs meet the H2a criterion.**" % met, "",
          "Across-seed mean (post hoc): **%s**, SD %s, t interval on 5 df [%s, %s]. This combines test-sample, "
          "training and generator variability, which the bootstrap does not; it is not a confirmatory test and "
          "the seeds are not pooled into one." % (f4(mean), f4(sd), f4(mean - half), f4(mean + half)), "",
          "## nb_pair and the sample oracle, per seed", "",
          "| Seed run | nb_pair D - C [95% CI] | sample oracle D - C [95% CI] |", "|---|---|---|"]
    for k in range(6):
        pr = [r for r in rows if r["seed_run"] == k and r["model"] == "nb_pair"][0]["acc"]
        orc = [r for r in rows if r["seed_run"] == k and r["model"] == "oracle"][0]["acc"]
        L.append("| %d | %s [%s, %s] | %s [%s, %s] |" % (k, f4(pr[0]), f4(pr[1]), f4(pr[2]), f4(orc[0]), f4(orc[1]), f4(orc[2])))
    n_pair = sum(1 for r in rows if r["model"] == "nb_pair" and r["acc"][2] < 0)
    n_orc = sum(1 for r in rows if r["model"] == "oracle" and r["acc"][2] < 0)
    note = (" Both attackers that can use the size x resolution interaction, which the coarsening removes, show "
            "D below C in every run; the fragility is specific to nb, which cannot." if n_pair == 6 and n_orc == 6 else
            " These attackers are not uniformly decisive either at this sample size.")
    L += ["", "Intervals excluding 0 (D below C): nb_pair %d of 6, sample oracle %d of 6.%s" % (n_pair, n_orc, note), "",
          "## Exact reference gaps (population, `main`)", "",
          "| Attacker | D - C accuracy (exact) |", "|---|---|",
          "| Bayes-optimal (oracle) | %s (%s) |" % (f4(bayes_gap), frac(bayes_gap)),
          "| nb with unlimited training data (nb_limit) | %s (%s) |" % (f4(nb_gap), frac(nb_gap)),
          "| nb_pair with unlimited training data | %s |" % f4(nbp_gap), "",
          "## The power analysis was wrong (study lead)", "",
          "The design-time power analysis in protocol section 3.9 was the study lead's, and it was wrong: it sized "
          "H2a from the Bayes-optimal gap (%s) when H2a is tested with nb, whose best possible gap is %s. "
          "Approximate realised power (normal approximation, paired SE %s = median across the six seed runs): "
          "%.2f at the across-seed mean, %.2f at nb's unlimited-data gap, against %.2f had the attacker been "
          "Bayes-optimal.%s"
          % (f4(bayes_gap), f4(nb_gap), f4(se), power_mean, power_lim, power_bayes,
             " The pre-specified seed happened to land on the passing side." if (p0["acc"][0] < 0 and p0["acc"][2] < 0)
             else ""), "",
          "## Log-loss (secondary, pre-specified under S9)", "",
          "nb's D - C log-loss difference is %s to %s bits, with the interval excluding 0 in %d of 6 runs. It was "
          "pre-specified as a secondary measure (S9) and is reported as such, not as a replacement test."
          % (f4(ll_range[0]), f4(ll_range[1]), ll_ex), "",
          "## How to read H2a", "",
          "- Report the frozen primary result as the confirmatory result, with this table beside it.",
          "- Do not replace the primary seed, pool the seeds into a new test, or describe H2a as robust or replicated.", ""]
    (out / "h2a_summary.md").write_text("\n".join(L), encoding="utf-8")
    return OrderedDict([("met", met), ("mean", mean), ("ci", (mean - half, mean + half)), ("bayes_gap", bayes_gap),
                        ("nb_gap", nb_gap), ("power_mean", power_mean), ("power_lim", power_lim)])


FROZEN_PRIMARY = "frozen v1.0 (primary seed)"
EXPLORATORY = "exploratory, post-review (v1.1)"
CORRECTION = "post-review correction (v1.1)"


# ---------------------------------------------------------------- corrections
def corrections(out, runs, pops, extras):
    eu = extras[("exact_utility", "main")]
    rows = []
    for (v, r), s in eu.items():
        for it in spec.ITEMS + ("ALL",):
            c = s if it == "ALL" else s["per_item"][it]
            rows.append([v, r, it, f6(c["action"]), f6(c["action_conveyed"])]
                        + [f6(c[k] / (9 if it == "ALL" else 1)) for k in exact_utility.CLASSES]
                        + [frac(c["action_conveyed"] / c["action"]) if c["action"] else "NA"])
    write_csv(out / "utility_exact.csv", ["view", "renderer", "item", "action_items_per_household",
                                          "action_items_conveyed_supported_per_household"]
              + ["share_%s" % k for k in exact_utility.CLASSES] + ["conveyed_share_exact"], rows)

    main = runs["main"]
    L = ["# Post-review corrections (v1.1)", "",
         "Each item is labelled **post-review correction (v1.1)**. Frozen v1.0 numbers are unchanged unless "
         "`revision_v1.1_delta.md` says otherwise. Scenario `main`, scored split; exact values by full enumeration.", "",
         "## H2b is descriptive, not a test", "",
         "Which views convey more action items is fixed by the generator and the strict renderer, so H2b cannot "
         "fail by chance. It is relabelled **descriptive (deterministic)**.", "",
         "| View | Observed share (scored split) | Exact expected share |", "|---|---|---|"]
    for v in spec.VIEWS:
        u = main["utility"][(v, "strict")]
        e = eu[(v, "strict")]
        L.append("| %s | %s (%d / %d) | %s |" % (v, f4(Fraction(u["action_conveyed"], u["action_total"])),
                                                u["action_conveyed"], u["action_total"],
                                                f4(e["action_conveyed"] / e["action"])))
    L += ["", "## Utility split three ways", "",
          "v1.0 counted a default that happened to be right as correct, and as an action item conveyed. v1.1 splits "
          "every output: **supported-correct** (the view entails the answer), **unsupported-correct** (a lucky "
          "default), **unsupported-wrong**, and omission. Only supported outputs earn action-item credit. Exact "
          "shares of all item outputs:", "",
          "| View | Renderer | Supported-correct | Unsupported-correct (lucky) | Unsupported-wrong | Omission | "
          "Action items conveyed, v1.0 credit -> supported only (scored split) |", "|---|---|---|---|---|---|---|"]
    for v in spec.VIEWS:
        for r in spec.RENDERERS:
            e = eu[(v, r)]
            u = main["utility"][(v, r)]
            L.append("| %s | %s | %s | %s | %s | %s | %s -> %s |" % (
                v, r, f4(e["supported_correct"] / 9), f4(e["unsupported_correct"] / 9), f4(e["unsupported_wrong"] / 9),
                f4(e["omission"] / 9), f4(Fraction(u["action_conveyed"], u["action_total"])),
                f4(Fraction(u["action_conveyed_supported"], u["action_total"]))))
    uns_v10 = {v: main["utility"][(v, "default_fill")]["unsupported"] for v in spec.VIEWS}
    uns_v11 = {v: main["utility"][(v, "default_fill")]["unsupported_correct"]
               + main["utility"][(v, "default_fill")]["unsupported_wrong"] for v in spec.VIEWS}
    L += ["", "**S6 recomputed.** Default-filling outputs made with no evidence (scored split): "
          + ", ".join("%s %d (v1.0 counted %d)" % (v, uns_v11[v], uns_v10[v]) for v in spec.VIEWS)
          + ". %s v1.0 understated unsupported claims by the lucky defaults." % (
              "The predicted pattern of S6 (positive in A, B and D; zero in C and E) still holds."
              if all(uns_v11[v] > 0 for v in "ABD") and uns_v11["C"] == 0 and uns_v11["E"] == 0
              else "The predicted pattern of S6 does not hold under the corrected count."), ""]
    s_c = eu[("C", "strict")]
    pt = sum((s_c["per_item"][it]["action"] for it in exact_utility.PASS_THROUGH_ITEMS), Fraction(0))
    s_d = eu[("D", "strict")]
    aff = [it for it in spec.ITEMS if s_d["per_item"][it]["omission"] > 0]
    a_act = sum((s_d["per_item"][it]["action"] for it in aff), Fraction(0))
    a_conv = sum((s_d["per_item"][it]["action_conveyed"] for it in aff), Fraction(0))
    L += ["## Pass-through items and D's utility", "",
          "- **Verbatim pass-throughs.** `%s` copy one field each. They make up %s of %s action items per household "
          "(**%s**)." % ("`, `".join(exact_utility.PASS_THROUGH_ITEMS), f4(pt), f4(s_c["action"]), f4(pt / s_c["action"])),
          "- **D on the items coarsening touches.** The items D's strict renderer can fail to settle are `%s`. On "
          "those, D conveys %s of %s action items per household (**%s**). D's overall %s is mostly items that "
          "coarsening never touched." % ("`, `".join(aff), f4(a_conv), f4(a_act), f4(a_conv / a_act),
                                        f4(s_d["action_conveyed"] / s_d["action"])), ""]
    L += ["## S7 wording", "",
          "The population gains shrink as lambda falls by construction (mixing toward the marginal shrinks every gap). "
          "The four nb estimates have intervals, and their ordering is weak evidence; see the S7 rows of "
          "`hypotheses.csv`, which now give the exact population gains, then the four estimates with intervals.", "",
          "## S1", "",
          "S1 is not confirmed on accuracy. The log-loss gain of nb_pair over nb on C is reported as a **secondary "
          "measure** (pre-specified under S9), not as a replacement for the accuracy criterion; see row "
          "`S1-logloss` of `hypotheses.csv`.", ""]
    (out / "post_review_corrections.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------- E vs D
def e_vs_d(out, runs, pops, extras):
    var = extras[("e_vs_d_variants", "main")]
    rob = [extras[("robustness", i)] for i in range(len(exploratory.ROBUSTNESS_SETTINGS))]
    rows = []
    for s in spec.SCENARIOS:
        if s == "positive_control":
            continue
        lim = extras[("nb_limits", s)]
        for v in ("C", "D", "E"):
            p = pops[s][v]
            rows.append(["exact", s, "", v, "", f6(p["bayes_accuracy"]), f6(p["mi_bits"]), f6(lim[v][0]), "", "", "", "", "", ""])
    for name, val in var.items():
        rows.append(["exact_variant", "main", "", name, "", f6(val["bayes_accuracy"]), f6(val["mi_bits"]),
                     f6(val["nb_limit"]), "", "", "", "", "", ""])
    seed = seed_rows(runs, "E", "D")
    for r in seed:
        a, l_ = r["acc"], r["logloss"]
        rows.append(["seed_run", "main", r["seed_run"], "E-D", r["model"], "", "", "", f4(a[0]), f4(a[1]), f4(a[2]),
                     f4(l_[0]), f4(l_[1]), f4(l_[2])])
    write_csv(out / "e_vs_d.csv", ["kind", "scenario", "seed_run", "view_or_comparison", "model", "bayes_accuracy",
                                   "mi_bits", "nb_limit", "accuracy_diff", "accuracy_ci_low", "accuracy_ci_high",
                                   "logloss_diff", "logloss_ci_low", "logloss_ci_high"], rows)
    L = ["# E (checklist answers only) versus D (coarsened linked releases): exploratory, post-review (v1.1)", "",
         "Label: **exploratory, post-review (v1.1)**. E - D was not a pre-specified comparison (it is absent from "
         "protocol section 6). It was raised after the test results were seen and examined in the independent "
         "review (section 4.4).", "",
         "## The defensible claim (review section 4.4, verbatim)", "", "> " + DEFENSIBLE_CLAIM, "",
         "## Exact values", "", "| Scenario | View | Bayes accuracy | MI (bits) | nb_limit |", "|---|---|---|---|---|"]
    for s in spec.SCENARIOS:
        if s == "positive_control":
            continue
        lim = extras[("nb_limits", s)]
        for v in ("C", "D", "E"):
            p = pops[s][v]
            L.append("| %s | %s | %s | %s | %s |" % (s, v, f4(p["bayes_accuracy"]), f4(p["mi_bits"]), f4(lim[v][0])))
    gm = pops["main"]["E"]["bayes_accuracy"] - pops["main"]["D"]["bayes_accuracy"]
    gs = pops["prev_skewed"]["E"]["bayes_accuracy"] - pops["prev_skewed"]["D"]["bayes_accuracy"]
    L += ["", "Exact E - D Bayes accuracy: %s in `main`, %s in `prev_skewed`. \"E keeps full utility\" holds by "
          "definition (utility is the checklist and E is the checklist), for any generator." % (f4(gm), f4(gs)), "",
          "## Per seed run (`main`)", "", "| Seed run | Model | E - D accuracy [95% CI] | E - D log-loss [95% CI] |",
          "|---|---|---|---|"]
    for r in seed:
        a, l_ = r["acc"], r["logloss"]
        L.append("| %d | %s | %s [%s, %s] | %s [%s, %s] |" % (r["seed_run"], r["model"], f4(a[0]), f4(a[1]), f4(a[2]),
                                                              f4(l_[0]), f4(l_[1]), f4(l_[2])))
    ex = {m: sum(1 for r in seed if r["model"] == m and _ci_excludes(r["acc"][1], r["acc"][2])) for m in ("nb", "nb_pair", "oracle")}
    L += ["", "Accuracy intervals excluding 0: nb %d of 6, nb_pair %d of 6, sample oracle %d of 6. nb is misspecified on "
          "E (its unlimited-data accuracy is %s against an exact %s), so it overstates the gap."
          % (ex["nb"], ex["nb_pair"], ex["oracle"], f4(extras[("nb_limits", "main")]["E"][0]),
             f4(pops["main"]["E"]["bayes_accuracy"])), "",
          "## Variants (review section 4.4 table, exact, `main`)", "",
          "| View | Bayes accuracy | MI (bits) | nb_limit |", "|---|---|---|---|"]
    for name, val in var.items():
        L.append("| %s | %s | %s | %s |" % (name, f4(val["bayes_accuracy"]), f4(val["mi_bits"]), f4(val["nb_limit"])))
    L += ["", "D keeps `income_pattern`, which the checklist never uses, while coarsening the fields the checklist "
          "needs at fine grain. One more checklist item and E leaks more than D.", "",
          "## Robustness to the generator's probabilities (port of the reviewer's script)", "",
          "Same schema, checklist and coarsening; %d random generators per setting. Ported from the reviewer's "
          "`a4.py` with attribution in `lfi/exploratory.py`; random draws use only `Random.random()`, so they differ "
          "from the reviewer's (who reported 93%%, 90%%, 91%% and 93%% for Bayes accuracy and 93%% to 96%% for MI)."
          % exploratory.ROBUSTNESS_N, "",
          "| Setting | P(Bayes acc E < D) | P(MI E < D) | E - D accuracy gap: median [5%, 95%] |", "|---|---|---|---|"]
    for r in rob:
        L.append("| %s | %.3f | %.3f | %s [%s, %s] |" % (r["setting"], r["p_bayes_acc_E_below_D"], r["p_mi_E_below_D"],
                                                         f4(r["acc_gap_median"]), f4(r["acc_gap_p05"]), f4(r["acc_gap_p95"])))
    L += ["", "The ordering is fairly robust to the probabilities and not robust to the checklist or to the choice "
          "of D (variants above). Against a coarsening, E and D are not ordered in general.", ""]
    (out / "exploratory_e_vs_d.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------- exploratory controls
def controls(out, runs, pops, extras):
    main = runs["main"]
    ex = main["exploratory"]
    pt, boot, n = ex["point"], ex["boot"], ex["n"]
    base = main["point"][("C", "baseline")]["accuracy"]
    rows = []
    for (kind, v, a), p in pt.items():
        if kind.startswith("lc"):
            continue
        lo, hi = metrics.ci_accuracy(boot[(kind, v, a)]["correct"], n)
        rows.append([kind, v, a, f4(p["accuracy"]), f4(lo), f4(hi), f4(base), f4(p["accuracy"] - base),
                     f4(p["mean_logloss_bits"]), f4(pops["main"]["baseline"]["h_band_bits"])])
    write_csv(out / "exploratory_controls.csv",
              ["control", "view", "attacker", "accuracy", "accuracy_ci_low", "accuracy_ci_high", "baseline_accuracy",
               "accuracy_minus_baseline", "mean_logloss_bits", "prior_entropy_bits"], rows)
    lim = extras[("nb_limits", "main")]
    lc_rows = []
    for size in exploratory.LEARNING_CURVE_SIZES:
        kind = "lc%d" % size
        for v in spec.VIEWS:
            for a in ("nb", "nb_pair", "lookup"):
                p = pt[(kind, v, a)]
                lo, hi = metrics.ci_accuracy(boot[(kind, v, a)]["correct"], n)
                llo, lhi = metrics.percentile_ci(boot[(kind, v, a)]["logloss"])
                info = ex["extra"].get((kind, v), {}) if size != 6000 else main["extras"][v]
                lc_rows.append([size, v, a, f4(p["accuracy"]), f4(lo), f4(hi), f4(p["macro_recall"]),
                                f4(p["mean_logloss_bits"]), f4(llo), f4(lhi),
                                f6(lim[v][1] if a == "nb_pair" else lim[v][0]) if a != "lookup" else "",
                                f6(pops["main"][v]["bayes_accuracy"])])
    write_csv(out / "learning_curve.csv", ["n_train", "view", "attacker", "accuracy", "accuracy_ci_low",
                                           "accuracy_ci_high", "macro_recall", "mean_logloss_bits", "logloss_ci_low",
                                           "logloss_ci_high", "unlimited_training_accuracy", "bayes_accuracy"], lc_rows)
    perm = [r for r in rows if r[0] == "permuted"]
    idr = [r for r in rows if r[0] == "id_order"]
    L = ["# Exploratory controls (post-review, v1.1)", "",
         "Label: **exploratory, post-review (v1.1)** (review section 4.6). Scenario `main`, scored split; intervals "
         "use main's bootstrap resamples. Each input went through the same isolated attacker once.", "",
         "## Label-permutation control", "",
         "Training labels shuffled among the training rows (seeded); features unchanged. Any accuracy above the "
         "frequency baseline would mean leakage from somewhere other than the features. Baseline accuracy %s." % f4(base), "",
         "| View | Attacker | Accuracy [95% CI] | Minus baseline |", "|---|---|---|---|"]
    for r in perm:
        L.append("| %s | %s | %s [%s, %s] | %s |" % (r[1], r[2], r[3], r[4], r[5], r[7]))
    worst = max(perm, key=lambda r: float(r[7]))
    L += ["", "Largest accuracy above baseline: %s (%s, %s)." % (worst[7], worst[1], worst[2]), "",
          "## Id-and-row-order-only attacker", "",
          "Features: two leading and the last character of the opaque id, and the row's position decile in the "
          "attacker's input. Labels are the true training labels.", "",
          "| Attacker | Accuracy [95% CI] | Minus baseline |", "|---|---|---|"]
    for r in idr:
        L.append("| %s | %s [%s, %s] | %s |" % (r[2], r[3], r[4], r[5], r[7]))
    L += ["", "## nb learning curve", "",
          "Nested training subsets (the first n rows in the attacker's seeded order). The 6,000-label point is the "
          "primary run. A weaker attacker is a fairer picture than the protocol's strong, upper-bound one.", "",
          "| n_train | " + " | ".join("%s nb [95%% CI]" % v for v in spec.VIEWS) + " |", "|---|" + "---|" * len(spec.VIEWS)]
    for size in exploratory.LEARNING_CURVE_SIZES:
        cells = []
        for v in spec.VIEWS:
            r = [x for x in lc_rows if x[0] == size and x[1] == v and x[2] == "nb"][0]
            cells.append("%s [%s, %s]" % (r[3], r[4], r[5]))
        L.append("| %d | %s |" % (size, " | ".join(cells)))
    L.append("| unlimited (exact) | %s |" % " | ".join(f4(lim[v][0]) for v in spec.VIEWS))
    L.append("| Bayes ceiling | %s |" % " | ".join(f4(pops["main"][v]["bayes_accuracy"]) for v in spec.VIEWS))
    gains = []
    for size in exploratory.LEARNING_CURVE_SIZES:
        acc = {v: pt[("lc%d" % size, v, "nb")]["accuracy"] for v in spec.VIEWS}
        gains.append("%d: C-A %s, D-C %s" % (size, f4(acc["C"] - acc["A"]), f4(acc["D"] - acc["C"])))
    L += ["", "nb gains by training size: " + "; ".join(gains) + ".", ""]
    (out / "exploratory_controls.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------- delta against v1.0
DELTA_KEYS = {
    "summary_inference.csv": 3, "summary_paired.csv": 4, "summary_utility.csv": 3, "utility_by_item.csv": 4,
    "tradeoff.csv": 2, "confusion.csv": 4, "controls.csv": 4, "exposure_and_deduction.csv": 2,
    "lookup_coverage.csv": 2, "seed_replicates.csv": 4, "seed_replicates_paired.csv": 3, "population_oracle.csv": 2,
    "generator_check.csv": 2, "hypotheses.csv": None,
}


def _read_csv(path):
    with open(str(path), newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def _hyp_key(header, row):
    d = dict(zip(header, row))
    return (d["id"], d["scenario"], d["statement"])


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _projected_report_checks_sha(path, n_cols=8):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    with open(str(path), newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            w.writerow(row[:n_cols])
    return _sha(buf.getvalue().encode("utf-8"))


def delta(out, split, data_dir):
    snap = SNAPSHOT / split
    L = ["# Revision v1.1: delta against the frozen v1.0 outputs (%s split)" % split, "",
         "Generated by the pipeline. It compares every v1.0 output committed at `edb8928` (snapshot in "
         "`results_v1.0/%s/`) with this run, cell by cell, matching rows on their key columns." % split, ""]
    if not snap.exists():
        (out / "revision_v1.1_delta.md").write_text("\n".join(L + ["No v1.0 snapshot for this split."]) + "\n",
                                                    encoding="utf-8")
        return
    changed_numbers = 0
    sections = []
    for name in sorted(DELTA_KEYS):
        if not (snap / name).exists() or not (out / name).exists():
            continue
        h0, r0 = _read_csv(snap / name)
        h1, r1 = _read_csv(out / name)
        k = DELTA_KEYS[name]
        key0 = (lambda row: _hyp_key(h0, row)) if k is None else (lambda row: tuple(row[:k]))
        key1 = (lambda row: _hyp_key(h1, row)) if k is None else (lambda row: tuple(row[:k]))
        m0 = OrderedDict((key0(r), dict(zip(h0, r))) for r in r0)
        m1 = OrderedDict((key1(r), dict(zip(h1, r))) for r in r1)
        added_cols = [c for c in h1 if c not in h0]
        removed_cols = [c for c in h0 if c not in h1]
        added_rows = [kk for kk in m1 if kk not in m0]
        removed_rows = [kk for kk in m0 if kk not in m1]
        cells = []
        for kk, d0 in m0.items():
            d1 = m1.get(kk)
            if d1 is None:
                continue
            for c in h0:
                if c in d1 and d0[c] != d1[c]:
                    cells.append((kk, c, d0[c], d1[c]))
        numeric = [c for c in cells if _is_number(c[2]) and _is_number(c[3])]
        changed_numbers += len(numeric)
        lines = ["### %s" % name, "",
                 "- Rows compared: %d; changed cells: %d (numeric: %d); added columns: %s; removed columns: %s; "
                 "added rows: %d; removed rows: %d." % (len(m0), len(cells), len(numeric),
                                                        ", ".join("`%s`" % c for c in added_cols) or "none",
                                                        ", ".join(removed_cols) or "none", len(added_rows), len(removed_rows))]
        for kk, c, a, b in cells:
            lines.append("- changed: `%s` / `%s`: `%s` -> `%s`" % (" | ".join(kk), c, a, b))
        for kk in added_rows:
            lines.append("- added row: `%s`" % " | ".join(kk))
        for kk in removed_rows:
            lines.append("- removed row: `%s`" % " | ".join(kk))
        sections += lines + [""]
    # large files: compare against the v1.0 manifest hashes
    man0 = json.loads((snap / "output_manifest.json").read_text(encoding="utf-8"))
    big = ["### Large files (compared with the v1.0 output_manifest.json hashes)", ""]
    label = out.name
    pred = out / "per_case_predictions.csv"
    rep = out / "per_case_report_checks.csv"
    e0 = man0.get("%s/per_case_predictions.csv" % label)
    if e0 and pred.exists():
        same = _sha(pred.read_bytes()) == e0["sha256"]
        big.append("- `per_case_predictions.csv`: %s." % ("byte-identical to v1.0" if same else "DIFFERS from v1.0"))
        changed_numbers += 0 if same else 1
    e0 = man0.get("%s/per_case_report_checks.csv" % label)
    if e0 and rep.exists():
        same = _projected_report_checks_sha(rep) == e0["sha256"]
        big.append("- `per_case_report_checks.csv`: two columns appended (`evidence_v1_1`, `outcome_v1_1`); the "
                   "first eight columns are %s." % ("byte-identical to v1.0" if same else "NOT identical to v1.0"))
        changed_numbers += 0 if same else 1
    n_data = n_same = 0
    for key, e in man0.items():
        if key.startswith("data/"):
            n_data += 1
            p = Path(data_dir) / key[len("data/"):]
            n_same += p.exists() and _sha(p.read_bytes()) == e["sha256"]
    big.append("- `data/`: %d of %d files byte-identical to v1.0." % (n_same, n_data))
    changed_numbers += n_data - n_same
    other = []
    for name in ("worked_cases.md",):
        if (snap / name).exists() and (out / name).exists():
            same = (snap / name).read_bytes() == (out / name).read_bytes()
            other.append("- `%s`: %s." % (name, "byte-identical to v1.0" if same else "changed"))
    other.append("- `run_info.json`, `validation.json` and `output_manifest.json` change by design (new fixture "
                 "version, file hashes, freeze label and checks).")
    L += ["## Summary", "",
          "**Changed frozen numbers: %d.** Changes that are not numbers (labels, wording, added columns and rows) are "
          "listed below. Every v1.1 addition is labelled in its file." % changed_numbers, ""]
    L += sections + big + [""] + ["### Other files", ""] + other + [""]
    (out / "revision_v1.1_delta.md").write_text("\n".join(L), encoding="utf-8")
    return changed_numbers


def _is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- all
def write_all(out, split, runs, pops, extras):
    out = Path(out)
    h = h2a(out, runs, pops, extras)
    corrections(out, runs, pops, extras)
    e_vs_d(out, runs, pops, extras)
    controls(out, runs, pops, extras)
    n_changed = delta(out, split, ROOT / "data")
    return ("Post-review (v1.1): H2a met in %d of 6 seed runs; across-seed mean %s (post hoc t interval [%s, %s]); "
            "exact gaps Bayes %s, nb_limit %s. Changed frozen numbers vs v1.0: %s."
            % (h["met"], f4(h["mean"]), f4(h["ci"][0]), f4(h["ci"][1]), f4(h["bayes_gap"]), f4(h["nb_gap"]), n_changed))
