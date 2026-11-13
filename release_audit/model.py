"""Declarative spec -> model; exact joint enumeration; seeded sampling.

A spec (JSON, see docs/spec-reference.md) declares a hidden target, fields with conditional
probability tables (a discrete Bayesian network whose root may be the target), declared
coarsenings, checklist items as rules over raw fields, and views. Every probability is an exact
Fraction. A zero in a table is a hard constraint, and the tools report the logical exclusions it
creates.

Exact enumeration. Each field's table rows are rescaled to integer numerators over that field's
common denominator, and the prior to integers over its own. A raw record's joint weight under
target value t is then W_t(r) = a_t * prod_f num_f(r_f | parents, t), an integer, and
P(t, r) = W_t(r) / TOTAL with one TOTAL for every record and target value. Records whose weight
is zero under every target value are pruned. Enumeration stops with RecordLimit when the record
count would exceed the configured limit; the caller then falls back to seeded sampling.
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from fractions import Fraction
from random import Random

from . import rules


class SpecError(ValueError):
    pass


class RecordLimit(RuntimeError):
    pass


def parse_prob(x, where):
    if isinstance(x, bool):
        raise SpecError("%s: probability must be a number or string, got %r" % (where, x))
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, float):
        return Fraction(repr(x))  # exact decimal of the JSON literal
    if isinstance(x, str):
        try:
            return Fraction(x.strip())
        except (ValueError, ZeroDivisionError):
            raise SpecError("%s: cannot read probability %r" % (where, x))
    raise SpecError("%s: cannot read probability %r" % (where, x))


class Field:
    def __init__(self, name, stage, values, parents, cpt, coarsenings, latent):
        self.name, self.stage, self.values = name, stage, tuple(values)
        self.parents, self.cpt = tuple(parents), cpt          # cpt: parent-value tuple -> tuple of Fractions
        self.coarsenings, self.latent = coarsenings, latent  # name -> {value: coarse value}


class Model:
    """A loaded spec. fields are in topological order; items and views are compiled."""

    def __init__(self, raw_spec, base_dir=None):
        self.spec = raw_spec
        self.name = raw_spec.get("name", "unnamed")
        self.description = raw_spec.get("description", "")
        t = raw_spec.get("target")
        if not isinstance(t, dict) or "name" not in t or "values" not in t or "prior" not in t:
            raise SpecError("target needs name, values and prior")
        self.target = t["name"]
        self.target_values = tuple(t["values"])
        if len(set(self.target_values)) != len(self.target_values) or len(self.target_values) < 2:
            raise SpecError("target values must be distinct and at least two")
        prior = t["prior"]
        if isinstance(prior, dict):
            prior = [prior.get(v, 0) for v in self.target_values]
        self.prior = tuple(parse_prob(p, "target prior") for p in prior)
        if len(self.prior) != len(self.target_values) or sum(self.prior) != 1 or min(self.prior) < 0:
            raise SpecError("target prior must have one probability per value and sum to exactly 1")
        self.fields = self._load_fields(raw_spec.get("fields", []))
        self.field_index = {f.name: i for i, f in enumerate(self.fields)}
        self.items = [rules.Item.from_spec(it, self) for it in raw_spec.get("items", [])]
        if len({it.name for it in self.items}) != len(self.items):
            raise SpecError("item names must be distinct")
        self.search = raw_spec.get("search", {})
        self.limits = raw_spec.get("limits", {})
        from . import viewdefs
        self.views = viewdefs.compile_views(self, raw_spec.get("views"))

    # ------------------------------------------------------------ fields
    def _load_fields(self, specs):
        if not specs:
            raise SpecError("at least one field is required")
        by_name = OrderedDict()
        for fs in specs:
            name = fs.get("name")
            if not name or name in by_name or name == self.target:
                raise SpecError("field names must be present, distinct and differ from the target: %r" % name)
            values = fs.get("values")
            if not values or len(set(values)) != len(values):
                raise SpecError("field %s: values must be a non-empty list of distinct strings" % name)
            by_name[name] = fs
        order, seen, visiting = [], set(), set()

        def visit(n):
            if n in seen:
                return
            if n in visiting:
                raise SpecError("cycle in parents through field %s" % n)
            visiting.add(n)
            for p in by_name[n].get("parents", []):
                if p == self.target:
                    continue
                if p not in by_name:
                    raise SpecError("field %s: unknown parent %s" % (n, p))
                visit(p)
            visiting.discard(n)
            seen.add(n)
            order.append(n)

        for n in by_name:
            visit(n)
        fields = []
        domains = {self.target: self.target_values}
        for n in order:
            fs = by_name[n]
            values = tuple(fs["values"])
            domains[n] = values
            parents = tuple(fs.get("parents", []))
            cpt = self._expand_cpt(n, values, parents, fs, domains)
            coars = OrderedDict()
            for cname, mp in (fs.get("coarsenings") or {}).items():
                if set(mp) != set(values):
                    raise SpecError("field %s coarsening %s must map every value exactly once" % (n, cname))
                coars[cname] = OrderedDict((v, str(mp[v])) for v in values)
            latent = bool(fs.get("latent", False)) or fs.get("stage") in (None, "latent")
            fields.append(Field(n, fs.get("stage", "latent"), values, parents, cpt, coars, latent))
        return fields

    def _expand_cpt(self, name, values, parents, fs, domains):
        def row(probs, where):
            if isinstance(probs, dict):
                unknown = set(probs) - set(values)
                if unknown:
                    raise SpecError("%s: unknown values %s" % (where, sorted(unknown)))
                probs = [probs.get(v, 0) for v in values]
            if len(probs) != len(values):
                raise SpecError("%s: expected %d probabilities" % (where, len(values)))
            out = tuple(parse_prob(p, where) for p in probs)
            if min(out) < 0 or sum(out) != 1:
                raise SpecError("%s: probabilities must be non-negative and sum to exactly 1 (got %s)" % (where, sum(out)))
            return out

        if not parents:
            if "p" in fs:
                return {(): row(fs["p"], "field %s" % name)}
            if "cpt" in fs and "" in fs["cpt"]:
                return {(): row(fs["cpt"][""], "field %s" % name)}
            raise SpecError("field %s has no parents and needs \"p\"" % name)
        if "cpt" not in fs:
            raise SpecError("field %s has parents and needs \"cpt\"" % name)
        combos = [()]
        for p in parents:
            combos = [c + (v,) for c in combos for v in domains[p]]
        table = {}
        for key, probs in fs["cpt"].items():
            parts = key.split("|")
            if len(parts) != len(parents):
                raise SpecError("field %s: cpt key %r needs %d parent values joined by '|'" % (name, key, len(parents)))
            for i, (p, v) in enumerate(zip(parents, parts)):
                if v != "*" and v not in domains[p]:
                    raise SpecError("field %s: cpt key %r: %r is not a value of %s" % (name, key, v, p))
            r = row(probs, "field %s cpt %r" % (name, key))
            for c in combos:  # rows apply in file order; a later row overrides an earlier one
                if all(part == "*" or part == cv for part, cv in zip(parts, c)):
                    table[c] = r
        missing = [c for c in combos if c not in table]
        if missing:
            raise SpecError("field %s: cpt does not cover parent values %s" % (name, "|".join(missing[0])))
        return table

    # ------------------------------------------------------------ helpers
    def released_fields(self):
        return [f for f in self.fields if not f.latent]

    def stages(self):
        out = []
        for f in self.released_fields():
            if f.stage not in out:
                out.append(f.stage)
        return out

    def record_dict(self, values):
        return {f.name: f.values[i] for f, i in zip(self.fields, values)}


def load(path_or_dict):
    if isinstance(path_or_dict, dict):
        return Model(path_or_dict)
    with open(str(path_or_dict), encoding="utf-8") as fh:
        return Model(json.load(fh, object_pairs_hook=OrderedDict))


def _lcm(a, b):
    return a * b // math.gcd(a, b)


class Joint:
    """Records (value-index tuples in model.fields order) with integer weights per target value.

    exact=True: weights are exact; P(t, r) = weights[r][t] / total.
    exact=False: weights are one-hot sample counts (Monte Carlo); total is the sample size.
    """

    def __init__(self, model, records, weights, total, exact, note="", rebuild=None):
        self.model, self.records, self.weights, self.total, self.exact, self.note = model, records, weights, total, exact, note
        self.wsum = [sum(w) for w in weights]
        self.rebuild = rebuild  # ("exact", max_records) or ("mc", n, seed): lets a worker process rebuild it

    def __len__(self):
        return len(self.records)


def enumerate_joint(model, max_records=500000):
    T = len(model.target_values)
    A = 1
    for p in model.prior:
        A = _lcm(A, p.denominator)
    a = tuple(p.numerator * (A // p.denominator) for p in model.prior)
    total = A
    plan = []
    for f in model.fields:
        den = 1
        for probs in f.cpt.values():
            for p in probs:
                den = _lcm(den, p.denominator)
        total *= den
        ints = {k: tuple(p.numerator * (den // p.denominator) for p in probs) for k, probs in f.cpt.items()}
        pidx = []
        for p in f.parents:
            pidx.append(("t", None) if p == model.target else ("f", model.field_index[p]))
        plan.append((f, ints, pidx))
    records, weights = [], []
    n_fields = len(model.fields)
    values = [0] * n_fields

    def key_for(pidx, f_values, t):
        out = []
        for kind, idx in pidx:
            out.append(model.target_values[t] if kind == "t" else model.fields[idx].values[f_values[idx]])
        return tuple(out)

    def dfs(depth, w):
        if depth == n_fields:
            if len(records) >= max_records:
                raise RecordLimit("more than %d raw records" % max_records)
            records.append(tuple(values))
            weights.append(tuple(w))
            return
        f, ints, pidx = plan[depth]
        uses_target = any(kind == "t" for kind, _ in pidx)
        if uses_target:
            rows = [ints[key_for(pidx, values, t)] for t in range(T)]
        else:
            r = ints[key_for(pidx, values, 0)]
            rows = [r] * T
        for vi in range(len(f.values)):
            nw = [w[t] * rows[t][vi] for t in range(T)]
            if any(nw):
                values[depth] = vi
                dfs(depth + 1, nw)
        values[depth] = 0

    dfs(0, list(a))
    return Joint(model, records, weights, total, True, rebuild=("exact", max_records))


def _threshold_table(probs):
    cum, rows = Fraction(0), []
    for i, p in enumerate(probs):
        cum += p
        rows.append((i, float(cum)))
    fallback = [i for i, p in enumerate(probs) if p > 0][-1]
    return rows, fallback


def _draw(table, u):
    rows, fallback = table
    for i, thr in rows:
        if u < thr:
            return i
    return fallback


def sample(model, n, seed):
    """n records drawn from the spec (target first, then fields in topological order) using only
    Random.random() and exact cumulative sums. Returns (target indices, record value tuples)."""
    rng = Random(seed)
    t_table = _threshold_table(model.prior)
    tables = []
    for f in model.fields:
        tables.append({k: _threshold_table(p) for k, p in f.cpt.items()})
    targets, records = [], []
    for _ in range(n):
        t = _draw(t_table, rng.random())
        vals = []
        for f, tab in zip(model.fields, tables):
            key = tuple(model.target_values[t] if p == model.target else
                        model.fields[model.field_index[p]].values[vals[model.field_index[p]]] for p in f.parents)
            vals.append(_draw(tab[key], rng.random()))
        targets.append(t)
        records.append(tuple(vals))
    return targets, records


def sampled_joint(model, n, seed):
    targets, records = sample(model, n, seed)
    T = len(model.target_values)
    weights = [tuple(1 if i == t else 0 for i in range(T)) for t in targets]
    return Joint(model, records, weights, n, False, note="Monte Carlo: %d seeded samples (seed %d)" % (n, seed),
                 rebuild=("mc", n, seed))


def build_joint(model, max_records=None, mc_samples=None, seed=None):
    """Exact enumeration when the raw space fits the limit, else seeded Monte Carlo."""
    max_records = max_records or int(model.limits.get("max_records", 500000))
    mc_samples = mc_samples or int(model.limits.get("mc_samples", 200000))
    seed = 20261113 if seed is None else seed
    try:
        return enumerate_joint(model, max_records)
    except RecordLimit:
        return sampled_joint(model, mc_samples, seed)


def rebuild_joint(raw_spec, how):
    """Rebuild a Joint in another process from the raw spec (item rules are closures and do not
    pickle). Deterministic, so the rebuilt joint is identical."""
    m = Model(raw_spec)
    return enumerate_joint(m, how[1]) if how[0] == "exact" else sampled_joint(m, how[1], how[2])
