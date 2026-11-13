"""Real-data mode: estimate the same tables from labelled records (review section 7.5).

Input: a CSV of categorical columns, one of which is the target. Empty cells are missing values.
Optionally a spec supplies stages, views (field options) and checklist items; without one, the
views are one per stage (a column "stage.field" belongs to stage "stage") plus "linked".

Per view:
  * plug-in Bayes accuracy (resubstitution; optimistic) and a k-fold cross-validated lookup;
  * plug-in mutual information and a Miller-Madow correction. The plug-in is biased upward,
    badly so when view values are many and records few;
  * k-fold naive Bayes (add-1 smoothing, unseen values skipped, optional fields handled) and
    k-fold multinomial logistic regression with all pairwise feature conjunctions, which can find
    a cross-field interaction it was not told about; accuracy and log-loss (bits) from pooled
    out-of-fold predictions, with a binomial standard error for accuracy;
  * a learning curve: the same attackers trained on 10%, 25%, 50% and 100% of each training fold;
  * utility by entailment on the OBSERVED support: an item counts as conveyed when it is constant
    across the observed records sharing a view value. Records never observed could break that, so
    this overstates utility, increasingly so for sparse data. Observed zero cells are not hard
    constraints, so logical exclusions are not reported in this mode.
Folds are a seeded shuffle (Random.random() keys). Everything is deterministic for a given seed.
"""
from __future__ import annotations

import csv
import math
from collections import OrderedDict
from fractions import Fraction
from random import Random



def load_csv(path, target):
    with open(str(path), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or target not in rows[0]:
        raise ValueError("CSV has no column %r" % target)
    rows = [r for r in rows if r.get(target, "") != ""]
    return rows


def default_views(columns):
    stages = OrderedDict()
    for c in columns:
        stages.setdefault(c.split(".", 1)[0] if "." in c else "all", []).append(c)
    views = OrderedDict()
    if len(stages) > 1:
        for s, cols in stages.items():
            views["stage:%s" % s] = OrderedDict((c, "keep") for c in cols)
    views["linked"] = OrderedDict((c, "keep") for c in columns)
    return views


def project(rows, view_fields, model=None, items=()):
    """Feature dicts per row for a view: kept/mapped fields (missing cells omitted) plus items."""
    out = []
    for r in rows:
        x = OrderedDict()
        for name, opt in view_fields.items():
            v = r.get(name, "")
            if opt == "drop" or v == "":
                continue
            if isinstance(opt, dict) and "map" in opt:
                v = opt["map"].get(v, v)
            elif isinstance(opt, dict) and "coarsen" in opt and model is not None:
                v = model.fields[model.field_index[name]].coarsenings[opt["coarsen"]].get(v, v)
            elif isinstance(opt, str) and opt.startswith("coarsen:") and model is not None:
                v = model.fields[model.field_index[name]].coarsenings[opt.split(":", 1)[1]].get(v, v)
            x[name] = v
        for it in items:
            val = it.evaluate(r)
            if val is not None:
                x["item:" + it.name] = val
        out.append(x)
    return out


# ---------------------------------------------------------------- attackers
class NB:
    def __init__(self, xs, ys, classes):
        self.classes = classes
        self.n = len(xs)
        self.cc = {c: 0 for c in classes}
        self.counts, self.fc = {}, {}
        for x, y in zip(xs, ys):
            self.cc[y] += 1
            for f, v in x.items():
                self.counts.setdefault(f, {}).setdefault(v, {c: 0 for c in classes})[y] += 1
                self.fc.setdefault(f, {c: 0 for c in classes})[y] += 1

    def proba(self, x):
        k = len(self.classes)
        logs = [math.log((self.cc[c] + 1) / (self.n + k)) for c in self.classes]
        for f, v in sorted(x.items()):
            seen = self.counts.get(f)
            if seen is None or v not in seen:
                continue  # unseen value: no factor
            for i, c in enumerate(self.classes):
                logs[i] += math.log((seen[v][c] + 1) / (self.fc[f][c] + len(seen) + 1))
        mx = max(logs)
        e = [math.exp(l - mx) for l in logs]
        s = math.fsum(e)
        return [x_ / s for x_ in e]


class PairwiseLogistic:
    """Multinomial logistic regression on one-hot fields plus all pairwise conjunctions seen at
    least `min_count` times in training; L2 penalty; full-batch gradient descent for a fixed number
    of iterations (deterministic, slow on large data: pure Python)."""

    def __init__(self, xs, ys, classes, iterations=150, lr=0.5, l2=1e-3, min_count=2):
        self.classes = classes
        counts = {}
        feats = [self._features(x) for x in xs]
        for fs in feats:
            for f in fs:
                counts[f] = counts.get(f, 0) + 1
        self.index = {f: i for i, f in enumerate(sorted(f for f, c in counts.items() if c >= min_count))}
        rows = [[self.index[f] for f in fs if f in self.index] for fs in feats]
        k, d, n = len(classes), len(self.index), len(xs)
        y_idx = [classes.index(y) for y in ys]
        self.W = [[0.0] * d for _ in range(k)]
        self.b = [0.0] * k
        for _ in range(iterations):
            gW = [[0.0] * d for _ in range(k)]
            gb = [0.0] * k
            for r, yi in zip(rows, y_idx):
                p = self._p(r)
                for c in range(k):
                    g = p[c] - (1.0 if c == yi else 0.0)
                    gb[c] += g
                    row = gW[c]
                    for j in r:
                        row[j] += g
            for c in range(k):
                self.b[c] -= lr * gb[c] / n
                Wc, gc = self.W[c], gW[c]
                for j in range(d):
                    Wc[j] -= lr * (gc[j] / n + l2 * Wc[j])

    @staticmethod
    def _features(x):
        items = sorted(x.items())
        fs = ["%s=%s" % kv for kv in items]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                fs.append("%s=%s&%s=%s" % (items[i] + items[j]))
        return fs

    def _p(self, r):
        s = [self.b[c] + math.fsum(self.W[c][j] for j in r) for c in range(len(self.classes))]
        mx = max(s)
        e = [math.exp(v - mx) for v in s]
        t = math.fsum(e)
        return [v / t for v in e]

    def proba(self, x):
        return self._p([self.index[f] for f in self._features(x) if f in self.index])


def folds(n, k, seed):
    rng = Random(seed)
    keys = [rng.random() for _ in range(n)]
    order = sorted(range(n), key=lambda i: (keys[i], i))
    out = [[] for _ in range(k)]
    for pos, i in enumerate(order):
        out[pos % k].append(i)
    return out


def crossval(xs, ys, classes, k, seed, fraction=1.0, attackers=("nb", "logistic"), lr_iterations=150):
    n = len(xs)
    fs = folds(n, k, seed)
    probs = {a: [None] * n for a in attackers}
    for fi, test in enumerate(fs):
        train = [i for fj, f in enumerate(fs) if fj != fi for i in f]
        if fraction < 1.0:
            train = train[:max(1, int(len(train) * fraction))]
        tx, ty = [xs[i] for i in train], [ys[i] for i in train]
        models = {}
        if "nb" in attackers:
            models["nb"] = NB(tx, ty, classes)
        if "logistic" in attackers:
            models["logistic"] = PairwiseLogistic(tx, ty, classes, iterations=lr_iterations)
        for a, mdl in models.items():
            for i in test:
                probs[a][i] = mdl.proba(xs[i])
    out = OrderedDict()
    for a in attackers:
        correct = 0
        ll = []
        for p, y in zip(probs[a], ys):
            yi = classes.index(y)
            best = max(range(len(classes)), key=lambda c: (p[c], -c))
            correct += best == yi
            ll.append(-math.log2(max(p[yi], 1e-12)))
        acc = correct / n
        out[a] = OrderedDict([("accuracy", acc), ("accuracy_se", math.sqrt(acc * (1 - acc) / n)),
                              ("logloss_bits", math.fsum(ll) / n)])
    return out


# ---------------------------------------------------------------- plug-in tables
def plugin(xs, ys, classes, k, seed):
    keys = [tuple(sorted(x.items())) for x in xs]
    n = len(xs)
    cells = {}
    for kk, y in zip(keys, ys):
        cells.setdefault(kk, {c: 0 for c in classes})[y] += 1
    resub = sum(max(c.values()) for c in cells.values()) / n
    py = {c: sum(1 for y in ys if y == c) / n for c in classes}
    h_y = -math.fsum(p * math.log2(p) for p in py.values() if p > 0)
    h_cond = 0.0
    terms = []
    for c in cells.values():
        s = sum(c.values())
        for v in c.values():
            if v:
                terms.append(-(v / n) * math.log2(v / s))
    h_cond = math.fsum(terms)
    mi = h_y - h_cond
    k_xy = sum(1 for c in cells.values() for v in c.values() if v)
    k_x = len(cells)
    k_y = sum(1 for p in py.values() if p > 0)
    mm = mi - (k_xy - k_x - k_y + 1) / (2.0 * n * math.log(2))
    # cross-validated lookup (falls back to the training majority for unseen view values)
    fs = folds(n, k, seed)
    correct = 0
    for fi, test in enumerate(fs):
        tr = {}
        maj = {c: 0 for c in classes}
        for fj, f in enumerate(fs):
            if fj == fi:
                continue
            for i in f:
                tr.setdefault(keys[i], {c: 0 for c in classes})[ys[i]] += 1
                maj[ys[i]] += 1
        default = max(classes, key=lambda c: (maj[c], -classes.index(c)))
        for i in test:
            cell = tr.get(keys[i])
            pred = default if cell is None else max(classes, key=lambda c: (cell[c], -classes.index(c)))
            correct += pred == ys[i]
    return OrderedDict([("n_values", len(cells)), ("bayes_resubstitution", resub), ("lookup_cv", correct / n),
                        ("mi_plugin_bits", mi), ("mi_miller_madow_bits", mm), ("h_target_bits", h_y)])


def observed_entailment(rows, xs, items):
    """Share of action items conveyed, with constancy checked on the observed records only."""
    if not items:
        return None
    keys = [tuple(sorted((k, v) for k, v in x.items() if not k.startswith("item:"))) +
            tuple(sorted((k, v) for k, v in x.items() if k.startswith("item:"))) for x in xs]
    vals = [tuple(it.evaluate(r) for it in items) for r in rows]
    first, const = {}, {}
    for kk, tv in zip(keys, vals):
        if kk not in first:
            first[kk] = tv
            const[kk] = [v is not None for v in tv]
        else:
            const[kk] = [c and a == b for c, a, b in zip(const[kk], first[kk], tv)]
    action = conveyed = 0
    for kk, tv in zip(keys, vals):
        for i, (it, v) in enumerate(zip(items, tv)):
            if it.is_action(v):
                action += 1
                conveyed += const[kk][i]
    return Fraction(conveyed, action) if action else None


def run(rows, target, model=None, k=5, seed=20261113, fractions=(0.1, 0.25, 0.5, 1.0), lr_iterations=150):
    classes = sorted({r[target] for r in rows})
    if model is not None and set(model.target_values) >= set(classes):
        classes = [c for c in model.target_values if c in classes]
    columns = [c for c in rows[0] if c != target]
    if model is not None:
        known = set(model.field_index)
        columns = [c for c in columns if c in known]
        views = OrderedDict()
        for name, vd in model.views.items():
            fields = OrderedDict()
            for part in vd.field_parts():
                f = model.fields[part[1]]
                if f.name not in columns:
                    continue
                if part[3] is None:
                    fields[f.name] = "keep"
                else:
                    fields[f.name] = {"map": {v: part[3][i] for i, v in enumerate(f.values)}}
            items = [model.items[p[1]] for p in vd.item_parts()]
            views[name] = (fields, items)
    else:
        views = OrderedDict((n, (v, [])) for n, v in default_views(columns).items())
    ys = [r[target] for r in rows]
    out = OrderedDict([("n_records", len(rows)), ("classes", classes), ("columns", columns), ("views", OrderedDict())])
    all_items = model.items if model is not None else []
    for name, (fields, items) in views.items():
        xs = project(rows, fields, model, items)
        res = OrderedDict()
        res["plugin"] = plugin(xs, ys, classes, k, seed)
        res["learning_curve"] = OrderedDict(
            (f, crossval(xs, ys, classes, k, seed, f, lr_iterations=lr_iterations)) for f in fractions)
        res["attackers"] = res["learning_curve"][1.0] if 1.0 in fractions else \
            crossval(xs, ys, classes, k, seed, 1.0, lr_iterations=lr_iterations)
        res["observed_utility"] = observed_entailment(rows, project(rows, fields, model, items), all_items)
        out["views"][name] = res
    return out
