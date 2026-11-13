"""Controls, hypothesis evaluation and every output file (PROTOCOL.md sections 6, 7 and 10).

All CSVs have rows in a fixed order (scenario order of spec.SCENARIOS, then view, model, ...)
and fixed float formatting, so outputs are byte-reproducible. Nothing here records wall-clock
time or absolute paths.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

from . import generator, metrics, spec

ATTACKER_CONTRASTS = (("C", "nb_pair", "nb"), ("D", "nb_pair", "nb"), ("C", "lookup", "nb"))


# ---------------------------------------------------------------- helpers
def f4(x):
    return "%.4f" % (float(x) + 0.0)  # + 0.0 turns IEEE negative zero into 0.0


def f6(x):
    return "%.6f" % (float(x) + 0.0)


def frac(x):
    x = Fraction(x)
    return "%d/%d" % (x.numerator, x.denominator)


def write_csv(path, header, rows):
    with open(str(path), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def primary_runs(runs):
    return [r for r in runs.values() if r["primary"]]


def acc_ci(run, key):
    return metrics.ci_accuracy(run["boot"][key]["correct"], run["n_scored"])


def comparisons(run):
    """(model, label, key_x, key_y) for every paired comparison of one primary run."""
    vs = run["views"]
    out = []
    for m in spec.SCORED_MODELS:
        for x, y in spec.PAIRED_VIEW_COMPARISONS:
            if x in vs and y in vs:
                out.append((m, "%s-%s" % (x, y), (x, m), (y, m)))
        if "E" in vs and m != "baseline":
            out.append((m, "E-baseline", ("E", m), ("E", "baseline")))
    for v, a, b in ATTACKER_CONTRASTS:
        if v in vs:
            out.append(("%s-%s" % (a, b), "%s:%s-%s" % (v, a, b), (v, a), (v, b)))
    for v in vs:
        out.append(("oracle-nb", "%s:oracle-nb" % v, (v, "oracle"), (v, "nb")))
    return out


def paired_estimate(run, kx, ky):
    px, py = run["point"][kx], run["point"][ky]
    n = run["n_scored"]
    ci = metrics.paired(run["boot"], kx, ky, n)
    dx, dy = metrics.discordant(run["correct"][kx], run["correct"][ky])
    return OrderedDict([
        ("accuracy", (Fraction(px["correct"] - py["correct"], n),) + ci["accuracy"]),
        ("macro_recall", (px["macro_recall"] - py["macro_recall"],) + ci["macro_recall"]),
        ("logloss_bits", (px["mean_logloss_bits"] - py["mean_logloss_bits"],) + ci["logloss"]),
        ("discordant", (dx, dy)),
    ])


# ---------------------------------------------------------------- controls (check 6)
def controls(runs):
    """Rows (control, scenario, view, model, statistic, value, threshold, pass)."""
    rows = []
    for r in runs.values():
        s = r["run_key"]
        if r["scenario"] == "independence" and r["primary"]:
            for v in r["views"]:
                base = r["point"][(v, "baseline")]["accuracy"]
                for m in spec.SCORED_MODELS:
                    d = r["point"][(v, m)]["accuracy"] - base
                    rows.append(("independence", s, v, m, "|accuracy - baseline accuracy|", f4(abs(d)),
                                 "<= " + f4(spec.INDEPENDENCE_TOLERANCE), abs(d) <= spec.INDEPENDENCE_TOLERANCE))
        if r["positive_control"]:
            for v in r["views"]:
                acc = r["point"][(v, "nb")]["accuracy"]
                rows.append(("positive_control_nb_accuracy", s, v, "nb", "accuracy", f4(acc),
                             ">= " + f4(spec.POSITIVE_CONTROL_MIN_ACCURACY), acc >= spec.POSITIVE_CONTROL_MIN_ACCURACY))
                e = r["exposure"][v]["scored_exposed"]
                rows.append(("positive_control_exposure", s, v, "", "scored rows with direct exposure", str(e),
                             "= %d" % r["n_scored"], e == r["n_scored"]))
        else:
            for v in r["views"]:
                e = r["exposure"][v]
                n_e = e["scored_exposed"] + e["train_exposed"]
                rows.append(("no_exposure", s, v, "", "rows with direct exposure (scored + training)", str(n_e),
                             "= 0", n_e == 0))
    return rows


def controls_checks(runs):
    from .validate import result
    rows = controls(runs)
    out = []
    for name in ("independence", "positive_control_nb_accuracy", "positive_control_exposure", "no_exposure"):
        sel = [r for r in rows if r[0] == name]
        bad = ["%s/%s/%s=%s" % (r[1], r[2], r[3], r[5]) for r in sel if not r[7]]
        out.append(result("6_control_%s" % name, sel and not bad,
                          "%d/%d pass%s" % (len(sel) - len(bad), len(sel), (": fails " + "; ".join(bad[:8])) if bad else "")))
    return out


# ---------------------------------------------------------------- hypotheses (section 7)
def _ci_outcome(est, lo, hi, direction):
    if direction > 0:
        if lo > 0:
            return "as predicted; 95% CI excludes 0"
        return "positive point estimate; CI includes 0" if est > 0 else "not as predicted"
    if hi < 0:
        return "as predicted; 95% CI excludes 0"
    return "negative point estimate; CI includes 0" if est < 0 else "not as predicted"


def hypotheses(runs, pops):
    main = runs["main"]
    rows = []

    def acc_diff(run, x, y, m="nb"):
        return paired_estimate(run, (x, m), (y, m))["accuracy"]

    for hid, x, y, sign in (("H1a", "C", "A", 1), ("H1b", "C", "B", 1), ("H2a", "D", "C", -1)):
        est, lo, hi = acc_diff(main, x, y)
        ok = (est > 0 and lo > 0) if sign > 0 else (est < 0 and hi < 0)
        rows.append((hid, "confirmatory", "main", "nb accuracy %s - %s %s 0, 95%% CI excluding 0"
                     % (x, y, ">" if sign > 0 else "<"), "accuracy difference", f4(est), f4(lo), f4(hi),
                     "supported" if ok else "not supported"))
    conv = {v: main["utility"][(v, "strict")]["action_conveyed"] for v in main["views"]}
    tot = main["utility"][("C", "strict")]["action_total"]
    ok = conv["D"] > max(conv["A"], conv["B"]) and conv["D"] < conv["C"]
    rows.append(("H2b", "confirmatory", "main", "strict action items conveyed: D > max(A, B) and D < C",
                 "counts of %d action items" % tot,
                 "A=%d B=%d C=%d D=%d E=%d" % tuple(conv[v] for v in spec.VIEWS), "", "",
                 "supported" if ok else "not supported"))

    p = paired_estimate(main, ("C", "nb_pair"), ("C", "nb"))["accuracy"]
    rows.append(("S1", "secondary", "main", "nb_pair on C - nb on C > 0 (interaction value)", "accuracy difference",
                 f4(p[0]), f4(p[1]), f4(p[2]), _ci_outcome(p[0], p[1], p[2], 1)))
    p = paired_estimate(main, ("E", "nb"), ("E", "baseline"))["accuracy"]
    rows.append(("S2", "secondary", "main", "nb on E - baseline > 0 (checklist answers alone leak)",
                 "accuracy difference", f4(p[0]), f4(p[1]), f4(p[2]), _ci_outcome(p[0], p[1], p[2], 1)))
    ex = {v: main["extras"][v]["deduction"]["any"] for v in main["views"]}
    ok = ex["C"] > 0 and ex["A"] == ex["B"] == ex["D"] == 0
    rows.append(("S3", "secondary", "main", "logical exclusions > 0 in C; 0 in A, B, D",
                 "scored households with an excluded band",
                 "A=%d B=%d C=%d D=%d E=%d" % tuple(ex[v] for v in spec.VIEWS), "", "",
                 "as predicted" if ok else "not as predicted"))
    for comp in (("D", "A"), ("D", "B")):
        est, lo, hi = acc_diff(main, *comp)
        rows.append(("S4", "secondary", "main", "nb accuracy %s - %s (no directional prediction)" % comp,
                     "accuracy difference", f4(est), f4(lo), f4(hi), "reported"))
    lk = main["extras"]["C"]["lookup"]
    cov = Fraction(lk["covered"], lk["n"])
    rows.append(("S5", "secondary", "main", "lookup coverage in C is low (mostly falls back to nb)",
                 "share of scored households with >= 5 training occurrences", f4(cov), "", "",
                 "as predicted (coverage < 0.5)" if cov < Fraction(1, 2) else "not as predicted"))
    uns = {v: main["utility"][(v, "default_fill")]["unsupported"] for v in main["views"]}
    ok = all(uns[v] > 0 for v in "ABD") and uns["C"] == 0 and uns["E"] == 0
    rows.append(("S6", "secondary", "main", "default-filling unsupported outputs > 0 in A, B, D; 0 in C, E",
                 "unsupported outputs", "A=%d B=%d C=%d D=%d E=%d" % tuple(uns[v] for v in spec.VIEWS), "", "",
                 "as predicted" if ok else "not as predicted"))
    for x, y in (("C", "A"), ("C", "B")):
        seq, pop_seq = [], []
        for s in spec.DEP_SEQUENCE:
            seq.append(acc_diff(runs[s], x, y)[0])
            pop_seq.append(pops[s][x]["bayes_accuracy"] - pops[s][y]["bayes_accuracy"])
        mono = all(a <= b for a, b in zip(seq, seq[1:]))
        pop_mono = all(a <= b for a, b in zip(pop_seq, pop_seq[1:]))
        ind = acc_diff(runs["independence"], x, y)[0]
        rows.append(("S7", "secondary", "dep_025..main", "nb accuracy gain %s - %s shrinks as lambda falls" % (x, y),
                     "gain at lambda = 0 (independence), 0.25, 0.50, 0.75, 1",
                     " ".join([f4(ind)] + [f4(g) for g in seq]), "", "",
                     ("as predicted (monotone in lambda)" if mono else "not monotone in lambda")
                     + "; exact population gains %s: %s" % ("monotone" if pop_mono else "NOT monotone",
                                                            " ".join(f4(g) for g in pop_seq))))
    for s in ("prev_balanced", "prev_skewed"):
        r = runs[s]
        txt = " ".join("%s=%s/%s" % (v, f4(r["point"][(v, "nb")]["accuracy"]), f4(r["point"][(v, "nb")]["macro_recall"]))
                       for v in r["views"])
        rows.append(("S8", "secondary", s, "nb accuracy/macro recall per view (no further prediction)",
                     "accuracy/macro recall", txt, "", "", "reported"))
    txt = " ".join("%s=%s" % (v, f4(pops["main"][v]["mi_bits"])) for v in spec.VIEWS)
    rows.append(("S9", "secondary", "main", "exact population I(band; view) in bits (see population_oracle.csv; "
                 "attacker log-loss in summary_inference.csv / summary_paired.csv)", "mutual information (bits)",
                 txt, "", "", "reported"))
    return rows


# ---------------------------------------------------------------- worked cases (section 10)
def select_worked(run):
    w = run["worked"]
    ids, true = w["ids"], w["true"]
    nb = {v: [p for p, _ in w["preds"][(v, "nb")]] for v in run["views"]}
    picks = OrderedDict()
    rules = OrderedDict([
        ("1", "the first household whose nb prediction is correct in C but wrong in both A and B"),
        ("2", "the first household whose nb prediction in C is wrong while A or B was right"),
        ("3", "the first household with a logical exclusion in C"),
        ("4", "the first household whose strict D rendering omits an action item that C conveyed"),
    ])
    for i, (hid, t) in enumerate(zip(ids, true)):
        c, a, b = nb["C"][i] == t, nb["A"][i] == t, nb["B"][i] == t
        if "1" not in picks and c and not a and not b:
            picks["1"] = i
        if "2" not in picks and not c and (a or b):
            picks["2"] = i
        if "3" not in picks and w["excluded"][hid]:
            picks["3"] = i
        if "4" not in picks:
            ans = w["answers"][hid]
            rc, rd = w["renders"]["C"][hid], w["renders"]["D"][hid]
            from .checklist import is_action_item
            if any(is_action_item(it, ans[it]) and rc[it] == ans[it] and rd[it] is None for it in spec.ITEMS):
                picks["4"] = i
    return rules, picks


def worked_cases_md(run, split):
    rules, picks = select_worked(run)
    w = run["worked"]
    lines = ["# Worked cases (scenario `main`, %s split)" % split, "",
             "Selection rule fixed in PROTOCOL.md section 10: households of the scored split taken in sorted "
             "opaque-ID order. Inputs below are the exact scored-row bytes each attacker process received "
             "(training rows have the same shape plus `\"y\"`). Posteriors are (p_low, p_medium, p_high); "
             "the predicted band is the argmax with ties broken low, medium, high. `oracle` is the exact "
             "Bayes posterior under the true generator (a reference ceiling, not an attacker).", ""]
    for code, rule in rules.items():
        lines.append("## Case %s: %s" % (code, rule))
        lines.append("")
        if code not in picks:
            lines += ["No household in the scored split satisfies this rule.", ""]
            continue
        i = picks[code]
        hid, t = w["ids"][i], w["true"][i]
        lines += ["Household `%s`; true band **%s**." % (hid, t), "", "```"]
        for v in run["views"]:
            lines.append("%s: %s" % (v, w["lines"][v][hid].decode("ascii")))
        lines += ["```", "", "| View | " + " | ".join(spec.SCORED_MODELS) + " |",
                  "|---|" + "---|" * len(spec.SCORED_MODELS)]
        for v in run["views"]:
            cells = []
            for m in spec.SCORED_MODELS:
                p, probs = w["preds"][(v, m)][i]
                mark = "correct" if p == t else "wrong"
                cells.append("%s (%s) %s" % (p, "/".join("%.3f" % q for q in probs), mark))
            lines.append("| %s | %s |" % (v, " | ".join(cells)))
        lines += ["", "Oracle logical exclusion in C: %s." % (", ".join(w["excluded"][hid]) or "none"), ""]
        lines += ["Strict renderer (`-` = abstained):", "",
                  "| Item | correct | " + " | ".join(run["views"]) + " |", "|---|---|" + "---|" * len(run["views"])]
        ans = w["answers"][hid]
        for it in spec.ITEMS:
            outs = [w["renders"][v][hid][it] for v in run["views"]]
            lines.append("| %s%s | %s | %s |" % (it, " (action)" if _is_action(it, ans[it]) else "", ans[it],
                                                " | ".join("-" if o is None else o for o in outs)))
        lines.append("")
    return "\n".join(lines) + "\n"


def _is_action(item, ans):
    from .checklist import is_action_item
    return is_action_item(item, ans)


# ---------------------------------------------------------------- all outputs
def write_all(out, split, runs, pops, checks, freeze_info, all_ok):
    out = Path(out)
    prim = primary_runs(runs)

    rows = []
    for r in prim:
        for v in r["views"]:
            for m in spec.SCORED_MODELS:
                pt, b = r["point"][(v, m)], r["boot"][(v, m)]
                alo, ahi = acc_ci(r, (v, m))
                mlo, mhi = metrics.percentile_ci(b["macro_recall"])
                llo, lhi = metrics.percentile_ci(b["logloss"])
                sk = r["extras"][v]["skipped"].get(m, ("", ""))
                rec = pt["recall"]
                rows.append([r["scenario"], v, m, pt["n"], pt["correct"], f4(pt["accuracy"]), f4(alo), f4(ahi),
                             f4(pt["macro_recall"]), f4(mlo), f4(mhi)]
                            + ["NA" if rec[bd] is None else f4(rec[bd]) for bd in spec.BANDS]
                            + [pt["n_band"][bd] for bd in spec.BANDS]
                            + [";".join(pt["bands_absent"]), f4(pt["mean_p_true"]), f4(pt["mean_logloss_bits"]),
                               f4(llo), f4(lhi), sk[0], sk[1],
                               f6(pops[r["scenario"]][v]["bayes_accuracy"]) if m == "oracle" else ""])
    write_csv(out / "summary_inference.csv",
              ["scenario", "view", "model", "n", "correct", "accuracy", "accuracy_ci_low", "accuracy_ci_high",
               "macro_recall", "macro_recall_ci_low", "macro_recall_ci_high", "recall_low", "recall_medium",
               "recall_high", "n_low", "n_medium", "n_high", "bands_absent", "mean_p_true", "mean_logloss_bits",
               "logloss_ci_low", "logloss_ci_high", "nb_skipped_unseen_values", "nb_rows_with_skips",
               "population_bayes_accuracy"], rows)

    rows = []
    for r in prim:
        for m, label, kx, ky in comparisons(r):
            est = paired_estimate(r, kx, ky)
            dx, dy = est["discordant"]
            for metric in ("accuracy", "macro_recall", "logloss_bits"):
                e, lo, hi = est[metric]
                rows.append([r["scenario"], m, label, "%s/%s" % kx, "%s/%s" % ky, metric, f4(e), f4(lo), f4(hi),
                             dx if metric == "accuracy" else "", dy if metric == "accuracy" else ""])
    write_csv(out / "summary_paired.csv", ["scenario", "model", "comparison", "first", "second", "metric", "estimate",
                                           "ci_low", "ci_high", "correct_first_only", "correct_second_only"], rows)

    rows, item_rows = [], []
    for r in prim:
        for (v, rd), u in r["utility"].items():
            rows.append([r["scenario"], v, rd, u["action_conveyed"], u["action_total"],
                         f4(Fraction(u["action_conveyed"], u["action_total"])), u["correct"], u["items_total"],
                         f4(Fraction(u["correct"], u["items_total"])), u["omission"], u["unsupported"]])
            for it, pi_ in u["per_item"].items():
                item_rows.append([r["scenario"], v, rd, it, pi_["n"], pi_["action"], pi_["action_conveyed"],
                                  pi_["correct"], pi_["omission"], pi_["unsupported"]])
    write_csv(out / "summary_utility.csv", ["scenario", "view", "renderer", "action_items_conveyed", "action_items_total",
                                            "action_items_share", "items_correct", "items_total", "items_share",
                                            "omissions", "unsupported"], rows)
    write_csv(out / "utility_by_item.csv", ["scenario", "view", "renderer", "item", "n", "action_items",
                                            "action_items_conveyed", "correct", "omissions", "unsupported"], item_rows)

    rows = []
    for r in prim:
        for v in r["views"]:
            pt, u = r["point"][(v, "nb")], r["utility"][(v, "strict")]
            rows.append([r["scenario"], v, f4(pt["accuracy"]), f4(pt["macro_recall"]), f4(pt["mean_logloss_bits"]),
                         f6(pops[r["scenario"]][v]["bayes_accuracy"]), u["action_conveyed"], u["action_total"],
                         f4(Fraction(u["action_conveyed"], u["action_total"])), u["correct"], u["items_total"]])
    write_csv(out / "tradeoff.csv", ["scenario", "view", "nb_accuracy", "nb_macro_recall", "nb_mean_logloss_bits",
                                     "population_bayes_accuracy", "strict_action_items_conveyed",
                                     "strict_action_items_total", "strict_action_items_share",
                                     "strict_items_correct", "strict_items_total"], rows)

    rows = []
    for r in prim:
        for v in r["views"]:
            for m in spec.SCORED_MODELS:
                cm = r["point"][(v, m)]["confusion"]
                for t in spec.BANDS:
                    rows.append([r["scenario"], v, m, t] + [cm[t][p] for p in spec.BANDS])
    write_csv(out / "confusion.csv", ["scenario", "view", "model", "true_band", "pred_low", "pred_medium", "pred_high"],
              rows)

    write_csv(out / "controls.csv", ["control", "scenario", "view", "model", "statistic", "value", "threshold", "pass"],
              controls(runs))

    rows = []
    for r in runs.values():
        pop = pops[r["scenario"]]
        for v in r["views"]:
            e, d = r["exposure"][v], r["extras"][v]["deduction"]
            rows.append([r["run_key"], v, r["n_scored"], e["scored_exposed"], e["train_rows"], e["train_exposed"],
                         d["any"]] + [d["by_band"][b] for b in spec.BANDS]
                        + [d["determined"], f6(pop[v]["p_exclusion"]), f6(pop[v]["p_determined"])])
    write_csv(out / "exposure_and_deduction.csv",
              ["scenario", "view", "n_scored", "scored_rows_exposed", "train_rows", "train_rows_exposed",
               "scored_with_any_exclusion", "excludes_low", "excludes_medium", "excludes_high", "determined",
               "population_p_exclusion", "population_p_determined"], rows)

    rows = []
    for r in runs.values():
        for v in r["views"]:
            lk = r["extras"][v]["lookup"]
            fb = lk["n"] - lk["covered"]
            rows.append([r["run_key"], v, lk["n"], lk["covered"], f4(Fraction(lk["covered"], lk["n"])),
                         lk["covered_correct"], f4(Fraction(lk["covered_correct"], lk["covered"])) if lk["covered"] else "NA",
                         fb, lk["fallback_correct"], f4(Fraction(lk["fallback_correct"], fb)) if fb else "NA"])
    write_csv(out / "lookup_coverage.csv", ["scenario", "view", "n_scored", "covered", "coverage", "covered_correct",
                                            "covered_accuracy", "fallback_n", "fallback_correct", "fallback_accuracy"],
              rows)

    # seed replicates: replicate 0 is the primary main run
    reps = [runs["main"]] + [runs["main_rep%d" % k] for k in range(1, spec.N_REPLICATES + 1)]
    rows = []
    for k, r in enumerate(reps):
        for v in r["views"]:
            for m in spec.SCORED_MODELS:
                pt = r["point"][(v, m)]
                rows.append(["%d" % k, str(r["master_seed"]), v, m, f4(pt["accuracy"]), f4(pt["macro_recall"]),
                             f4(pt["mean_logloss_bits"])])
    for v in spec.VIEWS:
        for m in spec.SCORED_MODELS:
            for stat in ("accuracy", "macro_recall", "mean_logloss_bits"):
                vals = [float(r["point"][(v, m)][stat]) for r in reps]
                rows.append(["summary_%s" % stat, "", v, m, "min=%s" % f4(min(vals)), "max=%s" % f4(max(vals)),
                             "mean=%s" % f4(math.fsum(vals) / len(vals))])
    write_csv(out / "seed_replicates.csv", ["replicate", "master_seed", "view", "model", "accuracy", "macro_recall",
                                            "mean_logloss_bits"], rows)
    # paired C-A, C-B, D-C for nb across replicates (point estimates; generator + training variability)
    rows = []
    for k, r in enumerate(reps):
        for x, y in (("C", "A"), ("C", "B"), ("D", "C"), ("E", "C")):
            d = r["point"][(x, "nb")]["accuracy"] - r["point"][(y, "nb")]["accuracy"]
            rows.append(["%d" % k, str(r["master_seed"]), "nb", "%s-%s" % (x, y), f4(d)])
    write_csv(out / "seed_replicates_paired.csv", ["replicate", "master_seed", "model", "comparison",
                                                   "accuracy_difference"], rows)

    rows = []
    for s, pop in pops.items():
        for v, p in pop.items():
            rows.append([s, v, p["n_view_values"], f6(p["bayes_accuracy"]), frac(p["bayes_accuracy"]),
                         f6(p["p_exclusion"]), f6(p["p_determined"]), f6(p["h_band_bits"]),
                         f6(p["h_band_given_view_bits"]), f6(p["mi_bits"])])
    write_csv(out / "population_oracle.csv", ["scenario", "view", "n_view_values", "bayes_accuracy",
                                              "bayes_accuracy_exact", "p_exclusion", "p_determined", "h_band_bits",
                                              "h_band_given_view_bits", "mi_bits"], rows)

    rows = []
    for r in runs.values():
        for name, p, count, n, ok, z in r["generator_cells"]:
            rows.append([r["run_key"], name, f6(p), count, n, "" if z is None else "%.3f" % z, ok])
    write_csv(out / "generator_check.csv", ["scenario", "cell", "specified_p", "observed_count", "n", "abs_z", "ok"],
              rows)

    hyp = hypotheses(runs, pops)
    write_csv(out / "hypotheses.csv", ["id", "role", "scenario", "statement", "measure", "estimate", "ci_low",
                                       "ci_high", "outcome"], hyp)
    (out / "worked_cases.md").write_text(worked_cases_md(runs["main"], split), encoding="utf-8")
    write_json(out / "validation.json", checks)

    run_info = OrderedDict([
        ("command", "python3 run_pilot.py --split %s" % split),
        ("scored_split", split),
        ("python_version", sys.version.split()[0]), ("python_implementation", platform.python_implementation()),
        ("platform", platform.platform()),
        ("master_seed", spec.MASTER_SEED),
        ("scenario_seeds", OrderedDict((r["run_key"], r["seeds"]) for r in runs.values())),
        ("replicate_master_seeds", OrderedDict(("main_rep%d" % k, generator.replicate_master(k))
                                               for k in range(1, spec.N_REPLICATES + 1))),
        ("sizes", OrderedDict([("households_per_scenario", spec.N_HOUSEHOLDS), ("splits", OrderedDict(spec.SPLIT_SIZES))])),
        ("n_bootstrap", spec.N_BOOTSTRAP), ("fixture_version", spec.FIXTURE_VERSION),
        ("sha256", freeze_info["current"]),
        ("freeze", freeze_info["status"]),
        ("validation_all_ok", all_ok),
        ("n_checks", len(checks)), ("n_failed", sum(not c["ok"] for c in checks)),
        ("attacker_isolation", "per call: script copied to its own fresh temp dir; working directory a second "
                               "fresh, empty temp dir; `python3 -I <script>`; env={}; input on stdin only; each "
                               "view run twice in independent processes. Process-level isolation, not an OS sandbox."),
    ])
    write_json(out / "run_info.json", run_info)
    return console(runs, pops, hyp, checks, split)


def manifest(out_dir, data_dir, exclude=("output_manifest.json", "reproducibility_check.json")):
    entries = OrderedDict()
    for base, label in ((Path(out_dir), Path(out_dir).name), (Path(data_dir), Path(data_dir).name)):
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.name not in exclude and p.name != ".DS_Store":
                entries["%s/%s" % (label, p.relative_to(base).as_posix())] = OrderedDict([
                    ("sha256", hashlib.sha256(p.read_bytes()).hexdigest()), ("bytes", p.stat().st_size)])
    return entries


# ---------------------------------------------------------------- console summary
def console(runs, pops, hyp, checks, split):
    m = runs["main"]
    out = ["Linked-findings inference pilot | scored split: %s | n = %d per scenario" % (split, m["n_scored"]), ""]
    out.append("main: accuracy [95% CI] / macro recall per view")
    out.append("%-9s" % "model" + "".join("%-27s" % v for v in m["views"]))
    for mod in spec.SCORED_MODELS:
        cells = []
        for v in m["views"]:
            pt = m["point"][(v, mod)]
            lo, hi = acc_ci(m, (v, mod))
            cells.append("%-27s" % ("%s [%s,%s]/%s" % (f4(pt["accuracy"])[1:], f4(lo)[1:], f4(hi)[1:],
                                                       f4(pt["macro_recall"])[1:])))
        out.append("%-9s" % mod + "".join(cells))
    out.append("%-9s" % "pop.Bayes" + "".join("%-27s" % f4(pops["main"][v]["bayes_accuracy"]) for v in m["views"]))
    out.append("%-9s" % "strict AI" + "".join("%-27s" % ("%d/%d" % (m["utility"][(v, "strict")]["action_conveyed"],
                                                                     m["utility"][(v, "strict")]["action_total"]))
                                             for v in m["views"]))
    out.append("")
    for h in hyp:
        out.append("%-4s %-60s %s %s%s -> %s" % (h[0], h[3][:60], h[5], "[%s,%s]" % (h[6], h[7]) if h[6] else "", "", h[8]))
    out.append("")
    n_ok = sum(c["ok"] for c in checks)
    out.append("Validation: %d/%d checks passed" % (n_ok, len(checks)))
    for c in checks:
        if not c["ok"]:
            out.append("  FAIL %s %s" % (c["check"], c["detail"]))
    return "\n".join(out)
