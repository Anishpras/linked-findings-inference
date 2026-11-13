"""Exploratory, post-review (v1.1) analyses: E versus D, and the inputs for the new controls.

Everything here is labelled "exploratory, post-review (v1.1)" in the outputs. None of it is a
pre-specified test, and none of it changes a frozen v1.0 number.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from random import Random

from . import checklist, generator, oracle, spec, views

# ---------------------------------------------------------------- E vs D: exact variants (review 4.4)


def _key(view):
    def fn(raw):
        return views.view_key(views.make_view(view, raw, None, False))
    return fn


def _major_settled(raw):
    return raw["r1.event_code"].endswith("_major") and raw["r2.resolution"] == "settled_in_full"


def _drop(view, field):
    def fn(raw):
        return tuple(kv for kv in views.view_key(views.make_view(view, raw, None, False)) if kv[0] != field)
    return fn


E_VS_D_VARIANTS = OrderedDict([
    ("C (linked fine releases)", _key("C")),
    ("D", _key("D")),
    ("D without income_pattern", _drop("D", "r1.income_pattern")),
    ("E", _key("E")),
    ("E plus one item that needs income_pattern", lambda raw: _key("E")(raw) + (("x.income_pattern", raw["r1.income_pattern"]),)),
    ("E plus one item 'major expense settled in full'", lambda raw: _key("E")(raw) + (("x.major_settled", _major_settled(raw)),)),
    ("E plus both", lambda raw: _key("E")(raw) + (("x.income_pattern", raw["r1.income_pattern"]),
                                                  ("x.major_settled", _major_settled(raw)))),
    ("E without goal_module", _drop("E", "e.goal_module")),
])


def e_vs_d_variants(scenario="main"):
    """Exact Bayes accuracy, MI and nb_limit for each variant (process-pool worker)."""
    orc = oracle.build_custom(scenario, E_VS_D_VARIANTS)
    pop = oracle.population(orc)
    out = OrderedDict()
    for name in E_VS_D_VARIANTS:
        out[name] = OrderedDict([("bayes_accuracy", pop[name]["bayes_accuracy"]), ("mi_bits", pop[name]["mi_bits"]),
                                 ("nb_limit", oracle.nb_limit(orc, name))])
    out["baseline"] = OrderedDict([("bayes_accuracy", pop["baseline"]["bayes_accuracy"]), ("mi_bits", 0.0),
                                   ("nb_limit", pop["baseline"]["bayes_accuracy"])])
    return out


# ---------------------------------------------------------------- E vs D: random-generator robustness
# Ported from the independent reviewer's analysis script a4.py ("random generators: is E < D
# robust?"), linked-findings-inference-reports/fable_review_scripts/a4.py, review dated
# 2026-11-13 (Claude, Fable 5.2). Changes in the port, made only for this project's determinism
# rule (only Random.random() is used): normal draws use Box-Muller and Dirichlet draws use sums of
# exponentials (integer concentration only), in place of random.gauss and random.gammavariate;
# each setting has its own seeded generator so the four settings can run in parallel. The draws
# therefore differ from the reviewer's, and the percentages are expected to differ slightly.
# The reduced enumeration keeps only band-informative fields (channel, documents and event type
# are band-independent and independent of every other field, so they cannot change Bayes
# accuracy or MI) and works in floats.

ROBUSTNESS_SETTINGS = (
    ("local perturbation sigma=0.25", 0.25, False, False),
    ("local perturbation sigma=0.5", 0.5, False, False),
    ("local sigma=0.5 + random prevalence", 0.5, True, False),
    ("fully random Dirichlet(1) conditionals + random prevalence", None, True, True),
)
ROBUSTNESS_N = 400
_EV = [("none", None)] + [(s, r) for s in spec.EVENT_SIZES for r in spec.RESOLUTIONS]
_B = spec.BANDS


class _Rng:
    def __init__(self, seed):
        self.r = Random(seed)

    def gauss(self, sigma):
        u1 = 1.0 - self.r.random()
        u2 = self.r.random()
        return sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def dirichlet(self, k, alpha=1):
        g = [math.fsum(-math.log(1.0 - self.r.random()) for _ in range(alpha)) for _ in range(k)]
        s = math.fsum(g)
        return [x / s for x in g]


def _base_tables():
    d = generator.distributions("main")
    t = {f: {b: [float(p) for p in d[f][b]] for b in _B} for f in spec.BAND_DEPENDENT}
    t["res"] = {(s, b): [float(p) for p in d["resolution"][(s, b)]] for s in spec.EVENT_SIZES for b in _B}
    return t


def _records(t, pi, p_event=0.5, p_major=0.4):
    recs = []
    for inc in range(2):
        for sh in range(3):
            for (s, r) in _EV:
                for f1 in range(4):
                    for f2 in range(4):
                        for g in range(4):
                            pr = []
                            for bi, b in enumerate(_B):
                                p = (pi[bi] * t["r1.income_pattern"][b][inc] * t["r1.essential_share"][b][sh]
                                     * t["r1.payment_flag"][b][f1] * t["r2.payment_flag"][b][f2] * t["r2.goal"][b][g])
                                if s == "none":
                                    p *= (1 - p_event)
                                else:
                                    p *= p_event * (p_major if s == "major" else 1 - p_major) \
                                        * t["res"][(s, b)][spec.RESOLUTIONS.index(r)]
                                pr.append(p)
                            recs.append(((inc, sh, s, r, f1, f2, g), pr))
    return recs


def _cres(r):
    return None if r is None else ("arranged" if r in ("settled_in_full", "instalment_plan") else r)


def _fD(x):
    inc, sh, s, r, f1, f2, g = x
    return (inc, sh == 2, s != "none", _cres(r), f1 > 0, f2 > 0, g)


def _fE(x):
    inc, sh, s, r, f1, f2, g = x
    return (f1 > 0 or f2 > 0, f1 >= 2 or f2 >= 2, sh == 2, r in ("instalment_plan", "outstanding"),
            s == "major" and r == "outstanding", r == "instalment_plan", g)


def _stats(recs, f):
    acc = {}
    for x, pr in recs:
        c = acc.get(f(x))
        if c is None:
            c = acc[f(x)] = [0.0, 0.0, 0.0]
        for i in range(3):
            c[i] += pr[i]
    a = math.fsum(max(c) for c in acc.values())
    h = []
    for c in acc.values():
        s = math.fsum(c)
        for p in c:
            if p > 0:
                h.append(-p * math.log2(p / s))
    pb = [math.fsum(c[i] for c in acc.values()) for i in range(3)]
    hp = -math.fsum(p * math.log2(p) for p in pb if p > 0)
    return a, hp - math.fsum(h)


def robustness(setting_index):
    """One setting of the random-generator robustness check (process-pool worker)."""
    label, sigma, random_prev, fully_random = ROBUSTNESS_SETTINGS[setting_index]
    rng = _Rng(generator.subseed(spec.MASTER_SEED, "e_vs_d_robustness", "setting_%d" % setting_index))
    t0, pi0 = _base_tables(), [0.40, 0.35, 0.25]
    gaps_acc, gaps_mi = [], []
    for _ in range(ROBUSTNESS_N):
        if fully_random:
            t = {f: {b: rng.dirichlet(len(spec.BAND_DEPENDENT[f][0])) for b in _B} for f in spec.BAND_DEPENDENT}
            t["res"] = {(s, b): rng.dirichlet(3) for s in spec.EVENT_SIZES for b in _B}
        else:
            t = {}
            for f, tab in t0.items():
                t[f] = {}
                for key, row in tab.items():
                    rr = [p * math.exp(rng.gauss(sigma)) for p in row]  # zeros stay zero
                    s = math.fsum(rr)
                    t[f][key] = [x / s for x in rr]
        pi = rng.dirichlet(3, 3) if random_prev else pi0
        recs = _records(t, pi)
        a_d, m_d = _stats(recs, _fD)
        a_e, m_e = _stats(recs, _fE)
        gaps_acc.append(a_e - a_d)
        gaps_mi.append(m_e - m_d)
    ga, gm = sorted(gaps_acc), sorted(gaps_mi)
    n = ROBUSTNESS_N
    return OrderedDict([
        ("setting", label), ("n_generators", n),
        ("p_bayes_acc_E_below_D", sum(1 for g in gaps_acc if g < -1e-12) / n),
        ("p_mi_E_below_D", sum(1 for g in gaps_mi if g < -1e-12) / n),
        ("acc_gap_median", ga[n // 2]), ("acc_gap_p05", ga[n // 20]), ("acc_gap_p95", ga[-(n // 20)]),
        ("mi_gap_median", gm[n // 2]), ("mi_gap_p05", gm[n // 20]), ("mi_gap_p95", gm[-(n // 20)]),
    ])


# ---------------------------------------------------------------- inputs for the new controls (review 4.6)
def ordered(households, split_of, split, order_key):
    return sorted((h for h in households if split_of[h["id"]] == split), key=lambda h: (order_key[h["id"]], h["id"]))


def stdin_from_rows(train_rows, scored_rows):
    lines = [views.training_line(i, x, y) for i, x, y in train_rows]
    lines += [views.scored_line(i, x) for i, x in scored_rows]
    return b"\n".join(lines) + b"\n"


def permuted_label_stdin(households, view_map, split_of, scored_split, order_key, seed):
    """Training labels shuffled among training rows (seeded); features and scored rows unchanged."""
    train = ordered(households, split_of, "train", order_key)
    rng = Random(seed)
    keys = [rng.random() for _ in train]
    labels = [h["band"] for h in train]
    perm = sorted(range(len(train)), key=lambda i: (keys[i], i))
    shuffled = [labels[j] for j in perm]
    scored = ordered(households, split_of, scored_split, order_key)
    return stdin_from_rows([(h["id"], view_map[h["id"]], y) for h, y in zip(train, shuffled)],
                           [(h["id"], view_map[h["id"]]) for h in scored])


def _id_order_features(hid, pos, n):
    return {"id_char1": hid[1], "id_char2": hid[2], "id_last": hid[-1], "row_position_decile": str(pos * 10 // n)}


def id_order_stdin(households, split_of, scored_split, order_key):
    """Features built only from the opaque id and the row's position in the attacker's input."""
    train = ordered(households, split_of, "train", order_key)
    scored = ordered(households, split_of, scored_split, order_key)
    return stdin_from_rows([(h["id"], _id_order_features(h["id"], i, len(train)), h["band"]) for i, h in enumerate(train)],
                           [(h["id"], _id_order_features(h["id"], i, len(scored))) for i, h in enumerate(scored)])


LEARNING_CURVE_SIZES = (100, 300, 1000, 3000, 6000)


def subset_stdin(households, view_map, split_of, scored_split, order_key, n_train):
    """The first n_train training rows in the attacker's seeded order (nested subsets)."""
    train = ordered(households, split_of, "train", order_key)[:n_train]
    scored = ordered(households, split_of, scored_split, order_key)
    return stdin_from_rows([(h["id"], view_map[h["id"]], h["band"]) for h in train],
                           [(h["id"], view_map[h["id"]]) for h in scored])
