"""Validation checks (PROTOCOL.md section 8). Each returns a list of {"check", "ok", "detail"}.

Check names start with the protocol's check number (1-10); "1b" and "x" checks are additional
safeguards described in PROTOCOL.md Revisions.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from collections import OrderedDict
from fractions import Fraction

from . import checklist, exposure, generator, isolate, oracle, spec, views

ALLOWED_ATTACKER_IMPORTS = {"json", "sys", "fractions"}
FORBIDDEN_NAMES = {"open", "eval", "exec", "compile", "__import__", "input", "globals", "locals", "vars",
                   "getattr", "setattr", "delattr", "__builtins__", "breakpoint", "memoryview"}
FORBIDDEN_ATTRS = {"argv", "environ", "path", "modules", "getenv", "system", "popen", "open", "codecs",
                   "__dict__", "__globals__", "__builtins__", "__class__", "__subclasses__", "__code__",
                   "loader", "spec_from_file_location", "import_module"}
# Variables a child may see although it is started with env={}: LC_CTYPE is set by the
# interpreter's own locale coercion (PEP 538); __CF_USER_TEXT_ENCODING is injected by macOS.
INTERPRETER_INJECTED_ENV = {"LC_CTYPE", "__CF_USER_TEXT_ENCODING"}


def result(check, ok, detail=""):
    return OrderedDict([("check", check), ("ok", bool(ok)), ("detail", detail)])


# ---------------------------------------------------------------- check 1: hand examples
def check_hand_examples(fixture):
    out = []
    for h in fixture["households"]:
        problems = []
        for v in spec.VIEWS:
            got = views.make_view(v, h["raw"], h["band"], False)
            if dict(got) != h["views"][v]:
                problems.append("view %s differs: %s" % (v, views.canonical(got)))
            if views.canonical(got) != views.canonical(h["views"][v]):
                problems.append("view %s bytes differ" % v)
        answers = checklist.correct_answers(h["raw"])
        if dict(answers) != h["checklist"]:
            problems.append("checklist differs: %s" % dict(answers))
        actions = [i for i in spec.ITEMS if checklist.is_action_item(i, answers[i])]
        if actions != h["action_items"]:
            problems.append("action items differ: %s" % actions)
        for v in spec.VIEWS:
            for source, x in (("fixture view", h["views"][v]),
                              ("generated view", views.make_view(v, h["raw"], h["band"], False))):
                strict = checklist.render_strict(x)
                if dict(strict) != h["strict"][v]:
                    problems.append("strict %s on %s differs: %s" % (v, source, dict(strict)))
            strict = checklist.render_strict(h["views"][v])
            n_correct = sum(checklist.outcome(h["checklist"][i], strict[i]) == "correct" for i in spec.ITEMS)
            if n_correct != h["strict_correct_count"][v]:
                problems.append("strict %s correct count %d != %d" % (v, n_correct, h["strict_correct_count"][v]))
        out.append(result("1_hand_example:%s" % h["name"], not problems, "; ".join(problems)))
    return out


def check_hand_exclusions(fixture, main_oracle):
    out = []
    for h in fixture["households"]:
        problems = []
        for v in spec.VIEWS:
            _post, excluded, _det = oracle.posterior(main_oracle, v, h["views"][v])
            if excluded != h["excluded_bands_main"][v]:
                problems.append("%s excludes %s, expected %s" % (v, excluded, h["excluded_bands_main"][v]))
        out.append(result("1_hand_example_exclusions:%s" % h["name"], not problems, "; ".join(problems)))
    return out


# ---------------------------------------------------------------- check 1b: attacker known answers
def known_answer_stdin(dataset):
    lines = [views.training_line("R%02d" % i, r["x"], r["y"]) for i, r in enumerate(dataset["train"])]
    lines += [views.scored_line(s["id"], s["x"]) for s in dataset["scored"]]
    return b"\n".join(lines) + b"\n"


def check_attacker_known_answers(fixture, script_path):
    """Run the attacker on each hand-computed dataset and compare every expected value exactly
    (probabilities as float(Fraction), which is what the attacker emits)."""
    problems = []
    for ds in fixture["datasets"]:
        try:
            raw = isolate.run_isolated(script_path, known_answer_stdin(ds))
            rows = [json.loads(line) for line in raw.decode("ascii").splitlines()]
        except Exception as exc:  # a crash is a failure, not an error in the harness
            return [result("1b_attacker_known_answers", False, "attacker failed: %s" % str(exc)[:300])]
        if [r["id"] for r in rows] != [s["id"] for s in ds["scored"]]:
            problems.append("%s: row ids/order differ" % ds["name"])
        for s, r in zip(ds["scored"], rows):
            for attacker, exp in s["expected"].items():
                got = r.get(attacker, {})
                for k, v in exp.items():
                    want = [float(Fraction(p)) for p in v] if k == "p" else v
                    if got.get(k) != want:
                        problems.append("%s %s %s %s: got %s want %s" % (ds["name"], s["id"], attacker, k, got.get(k), want))
    return [result("1b_attacker_known_answers", not problems, "; ".join(problems[:6]))]


# ---------------------------------------------------------------- check 2: split isolation
def check_split_isolation(run_key, data, stdin_by_view, scored_split, view_maps):
    split_of = {h["id"]: h["split"] for h in data["households"]}
    ids = {name: {i for i, s in split_of.items() if s == name} for name, _ in spec.SPLIT_SIZES}
    problems = []
    names = [n for n, _ in spec.SPLIT_SIZES]
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            if ids[names[a]] & ids[names[b]]:
                problems.append("%s and %s overlap" % (names[a], names[b]))
    sizes = dict((n, len(ids[n])) for n in names)
    expected_sizes = dict(spec.SPLIT_SIZES)
    if len(data["households"]) == spec.N_HOUSEHOLDS and sizes != expected_sizes:
        problems.append("split sizes %s" % sizes)
    for v, stdin in stdin_by_view.items():
        train_ids, scored_ids = [], []
        for line, obj, is_training in views.parse_stdin(stdin):
            hid = obj["id"]
            if is_training:
                train_ids.append(hid)
                if obj["x"] != view_maps[v][hid]:
                    problems.append("%s training row %s is not the household's view" % (v, hid))
            else:
                scored_ids.append(hid)
                if line != views.scored_line(hid, view_maps[v][hid]):
                    problems.append("%s scored row %s differs from the view file line" % (v, hid))
        if len(set(train_ids)) != len(train_ids) or set(train_ids) != ids["train"]:
            problems.append("view %s training rows are not exactly the household train split" % v)
        if len(set(scored_ids)) != len(scored_ids) or set(scored_ids) != ids[scored_split]:
            problems.append("view %s scored rows are not exactly the household %s split" % (v, scored_split))
        if set(train_ids) & ids[scored_split]:
            problems.append("view %s: a scored household appears in training input" % v)
    return [result("2_split_isolation:%s" % run_key, not problems, "; ".join(problems[:5]))]


# ---------------------------------------------------------------- check 3: deterministic regeneration
def serialise_scenario(data, view_maps):
    """Bytes of households.jsonl and of each views/<view>.jsonl (rows sorted by opaque id)."""
    hh = b"".join(views.canonical(OrderedDict([("band", h["band"]), ("gen_index", h["gen_index"]),
                                                ("id", h["id"]), ("raw", h["raw"]), ("split", h["split"])]))
                  .encode("ascii") + b"\n" for h in data["households"])
    vb = OrderedDict((v, b"".join(views.scored_line(h["id"], m[h["id"]]) + b"\n" for h in data["households"]))
                     for v, m in view_maps.items())
    return hh, vb


def check_regeneration(run_key, scenario, master, first):
    data = generator.generate(scenario, master)
    second = serialise_scenario(data, views.build_view_maps(data))
    ok = first[0] == second[0] and first[1] == second[1]
    digest = hashlib.sha256(first[0]).hexdigest()[:16]
    return [result("3_deterministic_regeneration:%s" % run_key, ok, "households sha256[:16]=%s" % digest)]


# ---------------------------------------------------------------- check 4: band removed
def check_band_removed(run_key, scans, positive_control):
    if positive_control:
        return []
    bad = ["%s(train %d, scored %d)" % (v, s["train_exposed"], s["scored_exposed"])
           for v, s in scans.items() if s["train_exposed"] or s["scored_exposed"]]
    return [result("4_band_removed:%s" % run_key, not bad, "; ".join(bad))]


# ---------------------------------------------------------------- check 5: denominators
def check_denominators(run_key, scored_split, n_scored, attacker_rows, n_report_rows, n_views):
    expected = dict(spec.SPLIT_SIZES)[scored_split]
    problems = []
    if n_scored != expected:
        problems.append("scored households %d != %d" % (n_scored, expected))
    for v, rows in attacker_rows.items():
        if len(rows) != expected:
            problems.append("view %s attacker rows %d" % (v, len(rows)))
    want_report = expected * len(spec.ITEMS) * len(spec.RENDERERS) * n_views
    if n_report_rows is not None and n_report_rows != want_report:
        problems.append("report rows %d != %d" % (n_report_rows, want_report))
    return [result("5_denominators:%s" % run_key, not problems,
                   "; ".join(problems) or "%d households x %d items" % (expected, len(spec.ITEMS)))]


# ---------------------------------------------------------------- check 7: generator matches spec
def generator_cells(data):
    """(scenario, cell name, p, count, n, ok, z) for every specified probability, training split."""
    dists = generator.distributions(data["scenario"])
    train = [h for h in data["households"] if h["split"] == "train"]
    cells = []

    def add(name, p, count, n):
        if n == 0:
            cells.append((name, p, count, n, True, None))
            return
        if p == 0:
            cells.append((name, p, count, n, count == 0, None))
            return
        pf = float(p)
        se = math.sqrt(pf * (1 - pf) / n)
        dev = abs(count / n - pf)
        cells.append((name, p, count, n, dev <= spec.GENERATOR_CHECK_SE * se + 1.0 / n, dev / se))

    n = len(train)
    for i, b in enumerate(spec.BANDS):
        add("band=%s" % b, dists["pi"][i], sum(h["band"] == b for h in train), n)
    for b in spec.BANDS:
        hb = [h for h in train if h["band"] == b]
        for field, (values, _c) in spec.BAND_DEPENDENT.items():
            for i, v in enumerate(values):
                add("%s=%s|%s" % (field, v, b), dists[field][b][i], sum(h["raw"][field] == v for h in hb), len(hb))
    events = [h for h in train if h["raw"]["r1.event_code"] != "none"]
    add("event_occurs=yes", dists["event_occurs"][1], len(events), n)
    for i, t in enumerate(spec.EVENT_TYPES):
        add("event_type=%s|event" % t, dists["event_type"][i],
            sum(h["raw"]["r1.event_code"].split("_")[0] == t for h in events), len(events))
    for i, s in enumerate(spec.EVENT_SIZES):
        add("event_size=%s|event" % s, dists["event_size"][i],
            sum(h["raw"]["r1.event_code"].split("_")[1] == s for h in events), len(events))
    for s in spec.EVENT_SIZES:
        for b in spec.BANDS:
            hs = [h for h in events if h["band"] == b and h["raw"]["r1.event_code"].endswith("_" + s)]
            for i, r in enumerate(spec.RESOLUTIONS):
                add("resolution=%s|%s,%s" % (r, s, b), dists["resolution"][(s, b)][i],
                    sum(h["raw"]["r2.resolution"] == r for h in hs), len(hs))
    no_event_ok = all(h["raw"]["r2.resolution"] == spec.NO_EVENT_RESOLUTION
                      for h in train if h["raw"]["r1.event_code"] == "none")
    cells.append(("resolution=not_applicable|no_event", Fraction(1), int(no_event_ok), 1, no_event_ok, None))
    for field in ("r1.contact_channel", "r2.document_status"):
        values = spec.BAND_INDEPENDENT[field][0]
        for i, v in enumerate(values):
            add("%s=%s" % (field, v), dists[field][i], sum(h["raw"][field] == v for h in train), n)
    return cells


def check_generator(run_key, cells):
    misses = [c for c in cells if not c[4]]
    detail = "%d cells, %d outside 4 SE + 1/n" % (len(cells), len(misses))
    if misses:
        detail += ": " + "; ".join("%s p=%s obs=%d/%d" % (c[0], c[1], c[2], c[3]) for c in misses[:5])
    return [result("7_generator_matches_spec:%s" % run_key, not misses, detail)]


# ---------------------------------------------------------------- check 8: oracle and hard zero
def check_oracle_population(scenario, pop):
    problems = [v for v, r in pop.items() if not r["band_sums_ok"]]
    out = [result("8_oracle_sums_to_one:%s" % scenario, not problems,
                  "P(view|band) sums to exactly 1 for every band" if not problems else "fails for %s" % problems)]
    # Information monotonicity (exact): A, B, D and E are functions of C, so their Bayes accuracy
    # and mutual information cannot exceed C's. A violation would mean an enumeration bug.
    c = pop["C"]
    bad = [v for v in pop if v not in ("C", "baseline") and
           (pop[v]["bayes_accuracy"] > c["bayes_accuracy"] or pop[v]["mi_bits"] > c["mi_bits"] + 1e-12)]
    out.append(result("8x_oracle_information_monotone:%s" % scenario, not bad, "violations: %s" % bad if bad else ""))
    return out


def check_hard_zero_in_data(run_key, data):
    if spec.SCENARIOS[data["scenario"]]["lam"] != 1:
        return []
    bad = [h["id"] for h in data["households"] if h["band"] == "low"
           and h["raw"]["r1.event_code"].endswith("_major") and h["raw"]["r2.resolution"] == "settled_in_full"]
    return [result("8_hard_zero_in_data:%s" % run_key, not bad, "%d violations" % len(bad))]


def check_oracle_support(run_key, n_out_of_support, n_true_band_zero):
    ok = n_out_of_support == 0 and n_true_band_zero == 0
    return [result("8x_oracle_covers_data:%s" % run_key, ok,
                   "views outside support %d; true band with P(view|band)=0: %d" % (n_out_of_support, n_true_band_zero))]


# ---------------------------------------------------------------- check 9: isolation
def check_attacker_static(script_path):
    """Static audit of the SHIPPED attacker script only (v1.1 wording, review 2.4).

    It reads the source of lfi/attacker.py and fails on imports outside json/sys/fractions and on
    a deny-list of names and attributes (file, environment, argv, reflection). It is a code
    review aid for this one script, not a confinement mechanism: a replaced attacker could reach
    the file system by routes a deny-list does not anticipate, and the launcher is process-level
    isolation, not an OS sandbox. Band-bearing files are written only after every attacker
    process has finished (pipeline.run), which removes the obvious route, but nothing stops a
    hostile process from searching the disk for other files.
    """
    src = open(str(script_path), encoding="utf-8").read()
    tree = ast.parse(src)
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_ATTACKER_IMPORTS:
                    problems.append("import %s" % a.name)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_ATTACKER_IMPORTS:
                problems.append("from %s import" % node.module)
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            problems.append("name %s" % node.id)
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            problems.append("attribute .%s" % node.attr)
    # The attacker's copies of the fixed constants must equal the spec.
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    for name, want in (("BANDS", spec.BANDS), ("ALPHA", spec.ALPHA), ("LOOKUP_MIN_COUNT", spec.LOOKUP_MIN_COUNT),
                       ("SCHEMA_PAIRS", spec.SCHEMA_PAIRS)):
        if consts.get(name) != want:
            problems.append("%s=%r differs from spec %r" % (name, consts.get(name), want))
    return [result("9_attacker_source_reads_stdin_only", not problems,
                   "; ".join(problems) or "audits the shipped lfi/attacker.py only; not a sandbox")]


def check_isolation_probe(probe_path, project_root):
    payload = b'{"probe":"stdin only"}\n'
    try:
        rep = json.loads(isolate.run_isolated(probe_path, payload).decode("utf-8"))
    except Exception as exc:
        return [result("9_isolation_probe", False, "probe failed: %s" % exc)]
    problems = []
    if rep["cwd_listing"] != []:
        problems.append("working directory not empty: %s" % rep["cwd_listing"])
    extra = set(rep["env_keys"]) - INTERPRETER_INJECTED_ENV
    if extra:
        problems.append("environment has %s" % sorted(extra))
    if not (rep["flags_isolated"] and rep["flags_ignore_environment"] and rep["flags_no_user_site"]):
        problems.append("interpreter not in isolated mode")
    if rep["stdin_sha256"] != hashlib.sha256(payload).hexdigest():
        problems.append("stdin not received intact")
    if rep["argv_len"] != 1:
        problems.append("extra argv")
    root = str(project_root)
    if any(root in p for p in [rep["cwd"], rep["script_dir"]] + rep["sys_path"]):
        problems.append("project directory visible to the process")
    if rep["cwd"] == rep["script_dir"]:
        problems.append("working directory holds the script")
    detail = "cwd empty, env keys %s (interpreter/OS-injected only), -I flags set" % rep["env_keys"]
    return [result("9_isolation_probe", not problems, "; ".join(problems) or detail)]


# ---------------------------------------------------------------- check 10 (in-run part)
def check_attacker_determinism(run_key, first, second):
    bad = [v for v in first if first[v] != second[v]]
    return [result("10_attacker_outputs_identical_across_two_isolated_runs:%s" % run_key, not bad,
                   "differs for %s" % bad if bad else "")]


# ---------------------------------------------------------------- extra: renderer invariant
def check_strict_never_unsupported(run_key, n_unsupported_strict):
    return [result("x_strict_renderer_never_unsupported:%s" % run_key, n_unsupported_strict == 0,
                   "%d unsupported strict outputs" % n_unsupported_strict)]
