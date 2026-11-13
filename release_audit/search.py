"""Release-design search and the leakage-versus-utility Pareto frontier (review section 7.3).

A design gives every released field one option: keep, drop, or coarsen:<name> for each declared
coarsening; the search also adds "items only" (release the task outputs) and "items plus one
field" designs. Each design is scored for leakage (mutual information and Bayes accuracy, exact
under enumeration) and utility (share of action items conveyed, by entailment). A design is on the
frontier if no other design has at least its utility with lower leakage, or lower-or-equal
leakage with more utility.

The design space is the product of per-field options; when it exceeds max_designs, the search
keeps the "items" designs and walks greedily from the full linked design, applying at each step
the single coarsening or drop with the best leakage removed per utility lost, and reports that the
frontier is then approximate. Designs are evaluated in a process pool when workers > 1; results are
collected by design index, so the output does not depend on scheduling.

Options per field can be restricted in the spec: "search": {"fields": {name: ["keep", "drop", ...]},
"max_designs": N, "items_plus_fields": 1}.
"""
from __future__ import annotations

import itertools
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor

from .viewdefs import make_view

_EV = None


def field_options(model):
    conf = (model.search or {}).get("fields", {})
    out = OrderedDict()
    for f in model.released_fields():
        default = ["keep"] + ["coarsen:%s" % c for c in f.coarsenings] + ["drop"]
        out[f.name] = list(conf.get(f.name, default))
    return out


def designs(model):
    opts = field_options(model)
    names = list(opts)
    max_designs = int((model.search or {}).get("max_designs", 5000))
    n_product = 1
    for o in opts.values():
        n_product *= len(o)
    out = []
    exhaustive = n_product <= max_designs
    if exhaustive:
        for combo in itertools.product(*[opts[n] for n in names]):
            out.append((OrderedDict(zip(names, combo)), False))
    if model.items:
        k_max = int((model.search or {}).get("items_plus_fields", 1))
        out.append((OrderedDict((n, "drop") for n in names), True))
        for k in range(1, k_max + 1):
            for chosen in itertools.combinations(names, k):
                for combo in itertools.product(*[[o for o in opts[n] if o != "drop"] for n in chosen]):
                    d = OrderedDict((n, "drop") for n in names)
                    d.update(zip(chosen, combo))
                    out.append((d, True))
    return out, exhaustive, n_product


def label(design, with_items):
    kept = [n if o == "keep" else "%s(%s)" % (n, o.split(":", 1)[1]) for n, o in design.items() if o != "drop"]
    if with_items:
        return "items only" if not kept else "items + " + ", ".join(kept)
    return ", ".join(kept) if kept else "nothing released"


def _init(ev):
    global _EV
    _EV = ev


def _init_remote(raw_spec, how):
    from .measures import Evaluator
    from .model import rebuild_joint
    _init(Evaluator(rebuild_joint(raw_spec, how)))


def _score(args):
    idx, design, with_items = args
    ev = _EV
    m = ev.model
    view = make_view(m, "design%d" % idx, design, [it.name for it in m.items] if with_items else [])
    keys = ev.keys(view)
    lk = ev.leakage(view, keys=keys, with_nb=False)
    ut = ev.utility(view, keys=keys)
    # Under Monte Carlo the less biased estimates are used: Miller-Madow MI and held-out accuracy.
    return idx, OrderedDict([("design", design), ("items", with_items), ("label", label(design, with_items)),
                             ("mi_bits", lk.get("mi_bits_miller_madow", lk["mi_bits"])),
                             ("bayes_accuracy", lk.get("bayes_accuracy_heldout", lk["bayes_accuracy"])),
                             ("p_exclusion", lk["p_exclusion"]), ("utility", ut["share"])])


def evaluate(ev, todo, workers):
    if workers > 1 and len(todo) > 50:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_remote,
                                 initargs=(ev.model.spec, ev.joint.rebuild)) as pool:
            res = dict(pool.map(_score, todo, chunksize=max(1, len(todo) // (workers * 8))))
    else:
        _init(ev)
        res = dict(_score(a) for a in todo)
    return [res[i] for i, _, _ in todo]


def greedy(ev, workers):
    """Walk from the full linked design toward dropping everything, one field step at a time."""
    m = ev.model
    opts = field_options(m)
    cur = OrderedDict((n, o[0]) for n, o in opts.items())
    path = evaluate(ev, [(0, OrderedDict(cur), False)], 1)
    step = 0
    while True:
        cands = []
        for n, o in opts.items():
            i = o.index(cur[n])
            if i + 1 < len(o):
                d = OrderedDict(cur)
                d[n] = o[i + 1]
                cands.append(d)
        if not cands:
            break
        step += 1
        scored = evaluate(ev, [(j, d, False) for j, d in enumerate(cands)], workers)
        base = path[-1]

        def gain(s):
            dl = base["mi_bits"] - s["mi_bits"]
            du = float(base["utility"] or 0) - float(s["utility"] or 0)
            return (dl / du if du > 1e-15 else float("inf") if dl > 0 else 0.0, dl)
        best = max(scored, key=gain)
        path.append(best)
        cur = best["design"]
    return path


def run(ev, workers=1):
    m = ev.model
    todo_designs, exhaustive, n_product = designs(m)
    todo = [(i, d, it) for i, (d, it) in enumerate(todo_designs)]
    results = evaluate(ev, todo, workers)
    if not exhaustive:
        results = greedy(ev, workers) + results
    frontier_mark(results, "mi_bits", "frontier_mi")
    frontier_mark(results, "bayes_accuracy", "frontier_bayes")
    return OrderedDict([("results", results), ("exhaustive", exhaustive), ("n_product", n_product)])


def _n_released(r):
    return sum(1 for o in r["design"].values() if o != "drop") + (1 if r["items"] else 0)


def frontier_mark(results, leak_key, flag):
    """Leakage values within 1e-12 bits count as equal (float noise); among equal designs the one
    with the fewest released components comes first."""
    pts = sorted(range(len(results)), key=lambda i: (round(float(results[i][leak_key]), 12),
                                                      -float(results[i]["utility"] or 0), _n_released(results[i]), i))
    best_u = None
    for i in pts:
        u = float(results[i]["utility"] or 0)
        on = best_u is None or u > best_u
        results[i][flag] = on
        if on:
            best_u = u
