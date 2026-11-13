"""One complete run: validate, generate, attack (isolated), render, score, write outputs.

Runs are processed one scenario at a time to bound memory. The scored split is `dev` before the
freeze and `test` after it; the training split is always `train`. Nothing in a dev run touches
test-split households except data generation and the data/ files, which hold every split.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from . import (checklist, exact_utility, exploratory, exposure, generator, isolate, metrics, oracle, postreview,
               report, spec, validate, views)

ROOT = Path(__file__).resolve().parent.parent
ATTACKER = ROOT / "lfi" / "attacker.py"
PROBE = ROOT / "lfi" / "probe.py"
HAND_EXAMPLES = ROOT / "fixtures" / "hand_examples.json"
KNOWN_ANSWERS = ROOT / "fixtures" / "attacker_known_answers.json"
SEED_RUN_MODELS = ("nb", "nb_pair", "oracle")
PER_CASE_FILES = ("per_case_predictions.csv", "per_case_report_checks.csv")
# Every file a run writes into the results directory. Only these are removed at the start of a
# run, so files the run does not produce (reproducibility_check.json) are left alone (v1.1).
KNOWN_OUTPUTS = PER_CASE_FILES + (
    "confusion.csv", "controls.csv", "exposure_and_deduction.csv", "generator_check.csv", "hypotheses.csv",
    "lookup_coverage.csv", "output_manifest.json", "population_oracle.csv", "run_info.json",
    "seed_replicates.csv", "seed_replicates_paired.csv", "summary_inference.csv", "summary_paired.csv",
    "summary_utility.csv", "tradeoff.csv", "utility_by_item.csv", "validation.json", "worked_cases.md",
) + postreview.OUTPUTS


def load_json(path):
    with open(str(path), encoding="utf-8") as fh:
        return json.load(fh, object_pairs_hook=OrderedDict)


def run_unit_tests():
    """Unit and mutation tests, in a separate process so patched modules cannot leak back."""
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                          cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = proc.stdout.decode("utf-8", "replace").strip().splitlines()
    summary = [line for line in text if line.startswith("Ran ") or line.startswith("OK") or line.startswith("FAILED")]
    summary = [re.sub(r" in [0-9.]+s$", "", line) for line in summary]  # drop wall time: outputs must be byte-stable
    return [validate.result("x_unit_and_mutation_tests", proc.returncode == 0, " | ".join(summary))]


def pre_run_checks():
    checks = run_unit_tests()
    checks += validate.check_hand_examples(load_json(HAND_EXAMPLES))
    checks += validate.check_attacker_known_answers(load_json(KNOWN_ANSWERS), ATTACKER)
    checks += validate.check_attacker_static(ATTACKER)
    checks += validate.check_isolation_probe(PROBE, ROOT)
    return checks


def run_attackers(stdin_by_view, workers):
    """Each view's input through the isolated attacker twice (independent processes)."""
    jobs = [(v, rep) for v in stdin_by_view for rep in (1, 2)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = OrderedDict((job, ex.submit(isolate.run_isolated, ATTACKER, stdin_by_view[job[0]])) for job in jobs)
        done = OrderedDict((job, f.result()) for job, f in futures.items())
    return (OrderedDict((v, done[(v, 1)]) for v in stdin_by_view),
            OrderedDict((v, done[(v, 2)]) for v in stdin_by_view))


def write_data(data_dir, scenario, serialised):
    hh, vb = serialised
    d = Path(data_dir) / scenario
    (d / "views").mkdir(parents=True, exist_ok=True)
    (d / "households.jsonl").write_bytes(hh)
    for v, b in vb.items():
        (d / "views" / ("%s.jsonl" % v)).write_bytes(b)


def exploratory_controls(data, maps, split, true, band_index, ctx, preds):
    """Exploratory, post-review (v1.1) controls on `main` (review 4.6): a label-permutation
    control, an id-and-row-order-only attacker, and an nb learning curve. Each input goes through
    the same isolated attacker once; intervals use main's bootstrap resamples."""
    hh, order_key = data["households"], data["order_key"]
    split_of = {h["id"]: h["split"] for h in hh}
    ids = [h["id"] for h in hh if h["split"] == split]
    jobs = OrderedDict()
    for v in maps:
        jobs[("permuted", v)] = exploratory.permuted_label_stdin(
            hh, maps[v], split_of, split, order_key, generator.subseed(spec.MASTER_SEED, "main", "label_permutation"))
    jobs[("id_order", "-")] = exploratory.id_order_stdin(hh, split_of, split, order_key)
    for n_train in exploratory.LEARNING_CURVE_SIZES[:-1]:
        for v in maps:
            jobs[("lc%d" % n_train, v)] = exploratory.subset_stdin(hh, maps[v], split_of, split, order_key, n_train)
    with ThreadPoolExecutor(max_workers=ctx["workers"]) as ex:
        futures = OrderedDict((k, ex.submit(isolate.run_isolated, ATTACKER, b)) for k, b in jobs.items())
        outputs = OrderedDict((k, f.result()) for k, f in futures.items())
    preds_x = OrderedDict()
    extra = OrderedDict()
    for (kind, v), raw in outputs.items():
        rows = {r["id"]: r for r in (json.loads(line) for line in raw.decode("ascii").splitlines())}
        for a in spec.ATTACKERS:
            preds_x[(kind, v, a)] = [(rows[i][a]["pred"], rows[i][a]["p"]) for i in ids]
        extra[(kind, v)] = OrderedDict([("nb_skipped", sum(rows[i]["nb"]["skipped"] for i in ids)),
                                        ("nb_pair_fallbacks", sum(rows[i]["nb_pair"]["pair_fallbacks"] for i in ids)),
                                        ("lookup_covered", sum(1 for i in ids if rows[i]["lookup"]["covered"]))])
    for v in maps:  # the 6,000-label point of the learning curve is the primary run itself
        for a in spec.ATTACKERS:
            preds_x[("lc6000", v, a)] = preds[(v, a)]
    point, series = OrderedDict(), OrderedDict()
    for key, pl in preds_x.items():
        pred = [p for p, _ in pl]
        p_true = [probs[bi] for (_, probs), bi in zip(pl, band_index)]
        point[key] = metrics.point(true, pred, p_true)
        series[key] = ([1 if p == t else 0 for p, t in zip(pred, true)], [metrics.logloss_bits(p) for p in p_true])
    boot_future = ctx["pool"].submit(metrics.bootstrap, data["seeds"]["bootstrap"], band_index, series)
    return OrderedDict([("point", point), ("extra", extra), ("boot_future", boot_future), ("n", len(ids))])


def process_run(run_key, scenario, master, split, orc, primary, ctx):
    """Everything for one generated dataset. Returns a summary dict."""
    checks = ctx["checks"]
    data = generator.generate(scenario, master)
    pc = data["positive_control"]
    vlist = views.views_for(data)
    maps = views.build_view_maps(data)
    serialised = validate.serialise_scenario(data, maps)
    checks += validate.check_regeneration(run_key, scenario, master, serialised)
    if primary:
        # v1.1: band-bearing data goes to a private staging directory that no attacker is told
        # about, and is moved to data/ only after every attacker process has finished.
        write_data(ctx["staging"] / "data", scenario, serialised)
    del serialised

    split_of = {h["id"]: h["split"] for h in data["households"]}
    stdin = OrderedDict((v, views.attacker_stdin(data["households"], maps[v], split_of, split, data["order_key"]))
                        for v in vlist)
    checks += validate.check_split_isolation(run_key, data, stdin, split, maps)
    scans = OrderedDict((v, exposure.scan(stdin[v])) for v in vlist)
    checks += validate.check_band_removed(run_key, scans, pc)
    cells = validate.generator_cells(data)
    checks += validate.check_generator(run_key, cells)
    checks += validate.check_hard_zero_in_data(run_key, data)

    first, second = run_attackers(stdin, ctx["workers"])
    checks += validate.check_attacker_determinism(run_key, first, second)

    scored = [h for h in data["households"] if h["split"] == split]  # sorted by opaque id
    ids = [h["id"] for h in scored]
    true = [h["band"] for h in scored]
    rows = OrderedDict()
    order_ok = True
    for v in vlist:
        parsed = [json.loads(line) for line in first[v].decode("ascii").splitlines()]
        sent = [obj["id"] for _l, obj, is_tr in views.parse_stdin(stdin[v]) if not is_tr]
        order_ok &= [r["id"] for r in parsed] == sent
        rows[v] = {r["id"]: r for r in parsed}
    checks.append(validate.result("5_attacker_returned_every_scored_row_in_order:%s" % run_key, order_ok))

    preds = OrderedDict()      # (view, model) -> [(pred, [p_low, p_medium, p_high])] in `ids` order
    extras = OrderedDict()     # per view: skipped values, lookup coverage, deduction counts
    out_of_support = true_zero = 0
    for v in vlist:
        for a in spec.ATTACKERS:
            preds[(v, a)] = [(rows[v][i][a]["pred"], rows[v][i][a]["p"]) for i in ids]
        o_preds, n_excl, n_det = [], OrderedDict((b, 0) for b in spec.BANDS), 0
        n_any = 0
        excl_by_id = {}
        for h in scored:
            try:
                post, excluded, determined = oracle.posterior(orc, v, maps[v][h["id"]])
            except KeyError:
                out_of_support += 1
                post, excluded, determined = OrderedDict(zip(spec.BANDS, orc["pi"])), [], False
            if post[h["band"]] == 0:
                true_zero += 1
            o_preds.append((oracle.argmax(post), [float(post[b]) for b in spec.BANDS]))
            for b in excluded:
                n_excl[b] += 1
            n_any += bool(excluded)
            n_det += determined
            excl_by_id[h["id"]] = excluded
        preds[(v, "oracle")] = o_preds
        lk = [rows[v][i]["lookup"] for i in ids]
        covered = [k["covered"] for k in lk]
        lk_correct = [p == t for (p, _), t in zip(preds[(v, "lookup")], true)]
        extras[v] = OrderedDict([
            ("skipped", OrderedDict((a, (sum(rows[v][i][a]["skipped"] for i in ids),
                                         sum(1 for i in ids if rows[v][i][a]["skipped"]))) for a in ("nb", "nb_pair"))),
            ("lookup", OrderedDict([
                ("n", len(ids)), ("covered", sum(covered)),
                ("covered_correct", sum(c and k for c, k in zip(covered, lk_correct))),
                ("fallback_correct", sum((not c) and k for c, k in zip(covered, lk_correct)))])),
            ("deduction", OrderedDict([("any", n_any), ("by_band", n_excl), ("determined", n_det)])),
            ("excluded_by_id", excl_by_id if (primary and scenario == "main") else None),
        ])
    checks += validate.check_oracle_support(run_key, out_of_support, true_zero)

    point = OrderedDict()
    series = OrderedDict()
    band_index = [spec.BANDS.index(t) for t in true]
    for key, pl in preds.items():
        pred = [p for p, _ in pl]
        p_true = [probs[bi] for (_, probs), bi in zip(pl, band_index)]
        point[key] = metrics.point(true, pred, p_true)
        series[key] = ([1 if p == t else 0 for p, t in zip(pred, true)], [metrics.logloss_bits(p) for p in p_true])

    # ---- report checklist and renderers
    # v1.0 outcome (protocol 4.4): correct / omission / unsupported (= output given and wrong).
    # v1.1 split (post-review correction, review 2.2): an output is "supported" when the strict
    # renderer, which answers only when the view entails the answer, gives an output; the
    # default-filling renderer's other outputs are "unsupported" whether right or wrong. Only
    # supported outputs earn action-item credit in the v1.1 columns.
    answers = {h["id"]: checklist.correct_answers(h["raw"]) for h in scored}
    utility = OrderedDict()
    renders = OrderedDict()
    n_report_rows = 0
    strict_unsupported = 0
    writer = ctx["report_writer"] if primary else None
    v11_keys = exact_utility.CLASSES + ("action_conveyed_supported",)
    for v in vlist:
        strict_outs = {h["id"]: checklist.render_strict(maps[v][h["id"]]) for h in scored}
        for r in spec.RENDERERS:
            u = OrderedDict([("action_total", 0), ("action_conveyed", 0), ("items_total", 0), ("correct", 0),
                             ("omission", 0), ("unsupported", 0)] + [(k, 0) for k in v11_keys if k != "omission"])
            per_item = OrderedDict((it, OrderedDict([("n", 0), ("action", 0), ("action_conveyed", 0), ("correct", 0),
                                                     ("omission", 0), ("unsupported", 0)]
                                                    + [(k, 0) for k in v11_keys if k != "omission"]))
                                   for it in spec.ITEMS)
            outs = {}
            for h in scored:
                out = checklist.render(r, maps[v][h["id"]])
                st = strict_outs[h["id"]]
                outs[h["id"]] = out
                for it in spec.ITEMS:
                    ans = answers[h["id"]][it]
                    oc = checklist.outcome(ans, out[it])
                    cls = exact_utility.classify(ans, st[it], out[it])
                    act = checklist.is_action_item(it, ans)
                    u["items_total"] += 1
                    u[oc] += 1
                    pi_ = per_item[it]
                    pi_["n"] += 1
                    pi_[oc] += 1
                    if cls != "omission":
                        u[cls] += 1
                        pi_[cls] += 1
                    if act:
                        u["action_total"] += 1
                        pi_["action"] += 1
                        if oc == "correct":
                            u["action_conveyed"] += 1
                            pi_["action_conveyed"] += 1
                        if cls == "supported_correct":
                            u["action_conveyed_supported"] += 1
                            pi_["action_conveyed_supported"] += 1
                    n_report_rows += 1
                    if writer is not None:
                        writer.writerow([scenario, v, r, h["id"], it, ans, "" if out[it] is None else out[it], oc,
                                         "none" if out[it] is None else ("supported" if st[it] is not None else "unsupported"),
                                         cls])
            if r == "strict":
                strict_unsupported += u["unsupported"] + u["supported_wrong"]
                if primary and scenario == "main":
                    renders[v] = outs
            u["per_item"] = per_item
            utility[(v, r)] = u
    checks += validate.check_strict_never_unsupported(run_key, strict_unsupported)
    checks += validate.check_denominators(run_key, split, len(scored), rows, n_report_rows, len(vlist))

    # ---- per-case predictions (primary runs only)
    if primary:
        pw = ctx["pred_writer"]
        for (v, m), pl in preds.items():
            for hid, t, (p, probs) in zip(ids, true, pl):
                pw.writerow([scenario, v, m, hid, t, p] + ["%.6f" % x for x in probs])

    summary = OrderedDict([
        ("run_key", run_key), ("scenario", scenario), ("master_seed", master), ("seeds", data["seeds"]),
        ("positive_control", pc), ("views", vlist), ("n_scored", len(scored)),
        ("point", point), ("extras", extras), ("exposure", scans), ("utility", utility),
        ("generator_cells", cells), ("primary", primary),
    ])
    summary["correct"] = OrderedDict((k, s[0]) for k, s in series.items())
    if primary:
        summary["boot_future"] = ctx["pool"].submit(metrics.bootstrap, data["seeds"]["bootstrap"], band_index,
                                                     series)
    else:
        # v1.1 (review 2.1, 4.3-4.4): paired intervals for the seed replicates, for the keys the
        # H2a and E-vs-D seed tables use. Same bootstrap seed rule as the primary runs.
        keep = OrderedDict((k, v_) for k, v_ in series.items() if k[0] in ("C", "D", "E") and k[1] in SEED_RUN_MODELS)
        summary["boot_future"] = ctx["pool"].submit(metrics.bootstrap, data["seeds"]["bootstrap"], band_index, keep)
    if primary and scenario == "main":
        summary["exploratory"] = exploratory_controls(data, maps, split, true, band_index, ctx, preds)
    if primary and scenario == "main":
        summary["worked"] = OrderedDict([
            ("ids", ids), ("true", true), ("preds", preds), ("renders", renders), ("answers", answers),
            ("lines", OrderedDict((v, {i: views.scored_line(i, maps[v][i]) for i in ids}) for v in vlist)),
            ("excluded", extras["C"]["excluded_by_id"]),
        ])
    for v in vlist:
        extras[v].pop("excluded_by_id", None)
    return summary


def run(split, out_dir, data_dir, freeze_info, workers=None):
    """Full pipeline. Returns (all_ok, checks, console text)."""
    workers = workers or max(2, min(10, os.cpu_count() or 2))
    out_dir, data_dir = Path(out_dir), Path(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in KNOWN_OUTPUTS:
        if (out_dir / name).exists():
            (out_dir / name).unlink()
    if data_dir.exists():
        shutil.rmtree(str(data_dir))  # no band-bearing file from an earlier run stays on disk
    checks = pre_run_checks()
    blocking = [c for c in checks if not c["ok"]]
    if blocking:
        report.write_json(out_dir / "validation.json", checks)
        return False, checks, "PRE-RUN VALIDATION FAILED; nothing scored:\n" + "\n".join(
            "  FAIL %s %s" % (c["check"], c["detail"]) for c in blocking)

    hand = load_json(HAND_EXAMPLES)
    oracles, pops = OrderedDict(), OrderedDict()
    for s in spec.SCENARIOS:
        oracles[s] = oracle.build(s)
        pops[s] = oracle.population(oracles[s])
        checks += validate.check_oracle_population(s, pops[s])
    checks += validate.check_hand_exclusions(hand, oracles["main"])

    runs = OrderedDict()
    staging = Path(tempfile.mkdtemp(prefix="lfi-staging-"))  # private (0700); never passed to an attacker
    try:
        pred_fh = open(str(staging / PER_CASE_FILES[0]), "w", newline="", encoding="utf-8")
        rep_fh = open(str(staging / PER_CASE_FILES[1]), "w", newline="", encoding="utf-8")
        try:
            pred_writer = csv.writer(pred_fh, lineterminator="\n")
            pred_writer.writerow(["scenario", "view", "attacker", "household", "true_band", "prediction",
                                  "p_low", "p_medium", "p_high"])
            rep_writer = csv.writer(rep_fh, lineterminator="\n")
            rep_writer.writerow(["scenario", "view", "renderer", "household", "item", "correct_answer", "output",
                                 "outcome", "evidence_v1_1", "outcome_v1_1"])
            with ProcessPoolExecutor(max_workers=workers) as pool:
                extra_jobs = OrderedDict()
                for s in spec.SCENARIOS:
                    extra_jobs[("nb_limits", s)] = pool.submit(oracle.nb_limits, s)
                extra_jobs[("exact_utility", "main")] = pool.submit(exact_utility.exact_utility, "main")
                extra_jobs[("e_vs_d_variants", "main")] = pool.submit(exploratory.e_vs_d_variants, "main")
                for i in range(len(exploratory.ROBUSTNESS_SETTINGS)):
                    extra_jobs[("robustness", i)] = pool.submit(exploratory.robustness, i)
                ctx = {"checks": checks, "workers": workers, "pool": pool, "staging": staging,
                       "pred_writer": pred_writer, "report_writer": rep_writer}
                for s in spec.SCENARIOS:
                    runs[s] = process_run(s, s, spec.MASTER_SEED, split, oracles[s], True, ctx)
                for k in range(1, spec.N_REPLICATES + 1):
                    key = "main_rep%d" % k
                    runs[key] = process_run(key, "main", generator.replicate_master(k), split, oracles["main"],
                                            False, ctx)
                for r in runs.values():
                    r["boot"] = r.pop("boot_future").result()
                    if "exploratory" in r:
                        r["exploratory"]["boot"] = r["exploratory"].pop("boot_future").result()
                extras = OrderedDict((k, f.result()) for k, f in extra_jobs.items())
        finally:
            pred_fh.close()
            rep_fh.close()
        # Every attacker process has finished: move band-bearing outputs into place.
        for name in PER_CASE_FILES:
            shutil.move(str(staging / name), str(out_dir / name))
        if (staging / "data").exists():
            shutil.move(str(staging / "data"), str(data_dir))
    finally:
        shutil.rmtree(str(staging), ignore_errors=True)

    checks += report.controls_checks(runs)
    checks += postreview.checks(runs, pops, extras)
    all_ok = all(c["ok"] for c in checks)
    text = report.write_all(out_dir, split, runs, pops, checks, freeze_info, all_ok, extras)
    text += "\n" + postreview.write_all(out_dir, split, runs, pops, extras)
    report.write_json(out_dir / "validation.json", checks)
    return all_ok, checks, text
