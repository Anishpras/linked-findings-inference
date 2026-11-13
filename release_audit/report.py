"""Markdown and CSV outputs for the toolkit. Deterministic: fixed row order and float formatting."""
from __future__ import annotations

import csv
from fractions import Fraction
from pathlib import Path


def f4(x):
    # round first so float noise such as -1e-17 prints as 0.0000, then + 0.0 removes negative zero
    return "" if x is None else "%.4f" % (round(float(x), 10) + 0.0)


def write_csv(path, header, rows):
    with open(str(path), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _mode_line(joint):
    if joint.exact:
        return "Exact enumeration over %d raw records with positive probability." % len(joint)
    return ("**Monte Carlo** (%s): the raw space exceeds the enumeration limit. Bayes accuracy is given as a "
            "resubstitution plug-in (optimistic) and a held-out plug-in classifier (usually pessimistic) with its standard error; mutual "
            "information as a plug-in (biased upward) and Miller-Madow corrected; utility by entailment on the "
            "sampled support (it may overstate conveyance)." % joint.note)


def audit(out, model, joint, views, budget, search):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tv = model.target_values
    rows = []
    for name, (lk, ut, _ex) in views.items():
        rows.append([name, lk["n_values"], f4(lk["bayes_accuracy"]), f4(lk.get("bayes_accuracy_heldout")),
                     f4(lk["mi_bits"]), f4(lk.get("mi_bits_miller_madow")), f4(lk["nb_limit"]),
                     f4(lk["p_exclusion"]), f4(lk["p_determined"]), f4(ut["share"]),
                     str(lk["bayes_accuracy"]) if isinstance(lk["bayes_accuracy"], Fraction) else ""])
    write_csv(out / "views.csv", ["view", "n_values", "bayes_accuracy", "bayes_accuracy_heldout_mc", "mi_bits",
                                  "mi_bits_miller_madow_mc", "nb_limit", "p_exclusion", "p_determined",
                                  "utility_share", "bayes_accuracy_exact"], rows)
    item_rows = []
    for name, (_lk, ut, _ex) in views.items():
        for it, d in (ut.get("per_item") or {}).items():
            item_rows.append([name, it, f4(d["action"]), f4(d["conveyed"]), f4(d["entailed"]),
                              f4(d["conveyed"] / d["action"]) if d["action"] else ""])
    write_csv(out / "items.csv", ["view", "item", "action_per_record", "conveyed_per_record", "entailed_share",
                                  "conveyed_share_of_action"], item_rows)

    L = ["# Release audit: %s" % model.name, ""]
    if model.description:
        L += [model.description, ""]
    base = max(model.prior)
    L += [_mode_line(joint), "",
          "Hidden target `%s` with values %s and prior %s. A frequency baseline is right %s of the time; the prior "
          "entropy is %s bits." % (model.target, ", ".join(tv), ", ".join(f4(p) for p in model.prior), f4(base),
                                    f4(views[next(iter(views))][0]["h_target_bits"])), "",
          "## Views", "",
          "Bayes accuracy is the best any attacker can do; nb_limit is naive Bayes with unlimited training data; "
          "MI is I(target; view). Utility is the expected share of action items the view entails.", ""]
    if joint.exact:
        L += ["| View | Bayes accuracy | MI (bits) | nb_limit | Excluding mass | Utility |", "|---|---|---|---|---|---|"]
        for name, (lk, ut, _ex) in views.items():
            L.append("| %s | %s | %s | %s | %s | %s |" % (name, f4(lk["bayes_accuracy"]), f4(lk["mi_bits"]),
                                                          f4(lk["nb_limit"]), f4(lk["p_exclusion"]), f4(ut["share"])))
    else:
        L += ["Monte Carlo estimates. The Bayes accuracy is bracketed: the held-out value scores a plug-in "
              "classifier fitted on half the samples and tends to understate it when view values are many; the "
              "resubstitution value overstates it. The Miller-Madow MI corrects part of the plug-in MI's upward "
              "bias. Logical exclusions cannot be established from samples and are not reported. Raise "
              "--max-records for an exact answer, or --mc-samples to narrow the bracket.", "",
              "| View | Bayes accuracy, held-out (SE) | Bayes, resubstitution (optimistic) | MI, Miller-Madow | "
              "MI, plug-in (biased up) | nb (plug-in) | Utility (sampled support) |", "|---|---|---|---|---|---|---|"]
        for name, (lk, ut, _ex) in views.items():
            L.append("| %s | %s (%s) | %s | %s | %s | %s | %s |" % (
                name, f4(lk["bayes_accuracy_heldout"]), f4(lk["bayes_accuracy_heldout_se"]), f4(lk["bayes_accuracy"]),
                f4(lk["mi_bits_miller_madow"]), f4(lk["mi_bits"]), f4(lk["nb_limit"]), f4(ut["share"])))
    ex_lines = []
    for name, (_lk, _ut, ex) in views.items():
        for mass, desc, zero in ex:
            ex_lines.append("| %s | %s | %s | %s |" % (name, ", ".join("%s=%s" % kv for kv in desc.items()),
                                                      ", ".join(zero), f4(mass)))
    if ex_lines:
        L += ["", "### Logical exclusions (largest view values)", "",
              "A view value that has probability zero under some target value rules that value out, whatever the "
              "attacker. These come from zeros in the spec's tables.", "",
              "| View | Released values | Rules out | Mass |", "|---|---|---|---|"] + ex_lines
    if item_rows:
        L += ["", "### Utility by item (share of action items conveyed)", "",
              "| View | " + " | ".join(it.name for it in model.items) + " |", "|---|" + "---|" * len(model.items)]
        for name, (_lk, ut, _ex) in views.items():
            cells = []
            for it in model.items:
                d = ut["per_item"][it.name]
                cells.append(f4(d["conveyed"] / d["action"]) if d["action"] else "-")
            L.append("| %s | %s |" % (name, " | ".join(cells)))

    if budget is not None:
        frows = []
        for r in budget["fields"]:
            frows.append([r["field"], r["stage"], f4(r["mi_alone"]), f4(r["bayes_alone"]), f4(r["mi_loss_if_dropped"]),
                          f4(r["bayes_loss_if_dropped"])] +
                         ["; ".join("%s: %s" % (c, f4(v["mi_loss"])) for c, v in r["coarsenings"].items())])
        write_csv(out / "budget_fields.csv", ["field", "stage", "mi_alone_bits", "bayes_alone", "mi_loss_if_dropped",
                                              "bayes_loss_if_dropped", "coarsening_mi_loss"], frows)
        prows = []
        for p in budget["pairs"]:
            prows.append([p["fields"][0], p["fields"][1], f4(p["mi_pair"]), f4(p["synergy_bits"]), f4(p["bayes_pair"]),
                          f4(p["p_exclusion"]), p["exclusion_only_when_linked"]])
        write_csv(out / "budget_pairs.csv", ["field_a", "field_b", "mi_pair_bits", "synergy_bits", "bayes_pair",
                                             "p_exclusion", "exclusion_only_when_linked"], prows)
        full = budget["full"]
        L += ["", "## Per-field information budget", "",
              "Against the full linked view (every released field): MI %s bits, Bayes accuracy %s."
              % (f4(full["mi_bits"]), f4(full["bayes_accuracy"])), "",
              "| Field | Stage | MI alone | MI lost if dropped | Bayes lost if dropped | MI lost by each coarsening |",
              "|---|---|---|---|---|---|"]
        for r in sorted(budget["fields"], key=lambda r: (-r["mi_alone"], r["field"])):
            L.append("| %s | %s | %s | %s | %s | %s |" % (r["field"], r["stage"], f4(r["mi_alone"]), f4(r["mi_loss_if_dropped"]),
                                                           f4(r["bayes_loss_if_dropped"]),
                                                           "; ".join("%s %s" % (c, f4(v["mi_loss"]))
                                                                     for c, v in r["coarsenings"].items()) or "-"))
        top = budget["pairs"][:8]
        L += ["", "### Cross-stage synergy (top pairs)", "",
              "Synergy = I(target; a, b) - I(target; a) - I(target; b). A large positive value is an interaction "
              "that only linking the stages reveals.", "",
              "| Field a | Field b | MI of pair | Synergy (bits) | Exclusion only when linked |", "|---|---|---|---|---|"]
        for p in top:
            L.append("| %s | %s | %s | %s | %s |" % (p["fields"][0], p["fields"][1], f4(p["mi_pair"]), f4(p["synergy_bits"]),
                                                     "yes" if p["exclusion_only_when_linked"] else "no"))
        linked_ex = [p for p in budget["pairs"] if p["exclusion_only_when_linked"]]
        if linked_ex:
            L += ["", "### Logical exclusions created only by linking", ""]
            for p in linked_ex:
                for mass, desc, zero in p["exclusion_examples"]:
                    L.append("- %s rules out %s (mass %s)" % (", ".join("%s=%s" % kv for kv in desc.items()),
                                                              ", ".join(zero), f4(mass)))

    if search is not None:
        res = search["results"]
        names = [f.name for f in model.released_fields()]
        drows = []
        for i, r in enumerate(res):
            drows.append([i, r["label"], r["items"]] + [r["design"][n] for n in names] +
                         [f4(r["mi_bits"]), f4(r["bayes_accuracy"]), f4(r["p_exclusion"]), f4(r["utility"]),
                          r["frontier_mi"], r["frontier_bayes"]])
        hdr = ["design", "label", "items"] + names + ["mi_bits", "bayes_accuracy", "p_exclusion", "utility",
                                                       "frontier_mi", "frontier_bayes"]
        write_csv(out / "designs.csv", hdr, drows)
        fr = sorted([r for r in res if r["frontier_mi"]], key=lambda r: (r["mi_bits"], -float(r["utility"] or 0)))
        write_csv(out / "frontier.csv", ["label", "items", "mi_bits", "bayes_accuracy", "utility"],
                  [[r["label"], r["items"], f4(r["mi_bits"]), f4(r["bayes_accuracy"]), f4(r["utility"])] for r in fr])
        L += ["", "## Release designs: leakage against utility", "",
              "%d designs evaluated (%s). The frontier lists designs that no other design beats on both mutual "
              "information and utility." % (len(res), "exhaustive over %d field-option combinations plus items "
                                                       "designs" % search["n_product"] if search["exhaustive"] else
                                                       "greedy path plus items designs; the field-option space (%d) "
                                                       "exceeded max_designs, so the frontier is approximate"
                                                       % search["n_product"]), "",
              "| Design | MI (bits) | Bayes accuracy | Utility |", "|---|---|---|---|"]
        for r in fr:
            L.append("| %s | %s | %s | %s |" % (r["label"], f4(r["mi_bits"]), f4(r["bayes_accuracy"]), f4(r["utility"])))
        named = [(n, views[n]) for n in views]
        L += ["", "Declared views for comparison: " + "; ".join(
            "%s MI %s, utility %s" % (n, f4(v[0]["mi_bits"]), f4(v[1]["share"])) for n, v in named) + "."]
    L += ["", "## Caveats", "",
          "- Every number is conditional on the spec's probabilities. Exact values are exact for the spec, not for "
          "the world.",
          "- Bayes accuracy and MI bound any attacker that sees the view; a real attacker with finite data does "
          "worse (see nb_limit and, for data, the learning curves of real-data mode).",
          "- Utility by entailment assumes the downstream task is exactly the declared checklist.", ""]
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")


def realdata(out, result, target):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, r in result["views"].items():
        p = r["plugin"]
        for a, s in r["attackers"].items():
            rows.append([name, a, f4(s["accuracy"]), f4(s["accuracy_se"]), f4(s["logloss_bits"]), f4(p["bayes_resubstitution"]),
                         f4(p["lookup_cv"]), f4(p["mi_plugin_bits"]), f4(p["mi_miller_madow_bits"]),
                         f4(r["observed_utility"])])
    write_csv(out / "realdata_views.csv", ["view", "attacker", "cv_accuracy", "cv_accuracy_se", "cv_logloss_bits",
                                           "bayes_resubstitution", "lookup_cv", "mi_plugin_bits",
                                           "mi_miller_madow_bits", "observed_utility_share"], rows)
    lc = []
    for name, r in result["views"].items():
        for frac_, res in r["learning_curve"].items():
            for a, s in res.items():
                lc.append([name, frac_, a, f4(s["accuracy"]), f4(s["accuracy_se"]), f4(s["logloss_bits"])])
    write_csv(out / "realdata_learning_curve.csv", ["view", "train_fraction", "attacker", "cv_accuracy",
                                                    "cv_accuracy_se", "cv_logloss_bits"], lc)
    L = ["# Release audit from labelled records (target `%s`)" % target, "",
         "%d records; classes %s; columns %s." % (result["n_records"], ", ".join(result["classes"]),
                                                   ", ".join(result["columns"])), "",
         "Read these as estimates. The plug-in Bayes accuracy is optimistic (it is scored on the records it was "
         "fitted to) and the plug-in MI is biased upward, badly so with many view values and few records; the "
         "Miller-Madow value corrects part of that bias. Cross-validated accuracies are from pooled out-of-fold "
         "predictions; the standard errors are binomial and ignore fold-to-fold variation. Utility is computed on "
         "the observed support only and can overstate what a view conveys. Zeros in observed counts are not hard "
         "constraints, so no logical exclusions are reported.", "",
         "| View | Plug-in Bayes (resub.) | Lookup (CV) | MI plug-in | MI Miller-Madow | nb (CV) | Pairwise logistic (CV) | Utility (observed) |",
         "|---|---|---|---|---|---|---|---|"]
    for name, r in result["views"].items():
        p, a = r["plugin"], r["attackers"]
        L.append("| %s | %s | %s | %s | %s | %s +/- %s | %s +/- %s | %s |" % (
            name, f4(p["bayes_resubstitution"]), f4(p["lookup_cv"]), f4(p["mi_plugin_bits"]), f4(p["mi_miller_madow_bits"]),
            f4(a["nb"]["accuracy"]), f4(a["nb"]["accuracy_se"]), f4(a["logistic"]["accuracy"]), f4(a["logistic"]["accuracy_se"]),
            f4(r["observed_utility"])))
    L += ["", "## Learning curves (cross-validated accuracy by share of each training fold)", "",
          "| View | Attacker | " + " | ".join(str(f) for f in next(iter(result["views"].values()))["learning_curve"]) + " |",
          "|---|---|" + "---|" * len(next(iter(result["views"].values()))["learning_curve"])]
    for name, r in result["views"].items():
        for a in ("nb", "logistic"):
            L.append("| %s | %s | %s |" % (name, a, " | ".join(f4(res[a]["accuracy"]) for res in r["learning_curve"].values())))
    L.append("")
    (out / "realdata.md").write_text("\n".join(L), encoding="utf-8")
