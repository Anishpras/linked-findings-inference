#!/usr/bin/env python3
"""Standalone attacker (PROTOCOL.md section 5). Runs as `python3 -I attacker.py` in a fresh empty
working directory with an empty environment; its only input is stdin.

Input: JSON lines. A line with "y" is a labelled training row {"id", "x", "y"}; a line without
"y" is a scored row {"id", "x"}. "x" is the flat view map. Output: one JSON line per scored row,
in input order, with each attacker's prediction and posterior over (low, medium, high).

Attackers (all see identical inputs; none abstains; argmax ties break low, medium, high):
  baseline  most frequent training band; its probabilities are the add-1 smoothed class prior.
  nb        categorical naive Bayes. Prior: add-1 over the three bands. Likelihood for field f:
            (count(f=v, band) + alpha) / (count(band) + alpha * (K_f + 1)), K_f = number of
            values of f seen in training (any band), the +1 being one slot for unseen values.
            A scored value never seen in training for that field contributes NO factor: it is
            skipped and counted (the unseen-value rule).
  nb_pair   nb after replacing a schema-linked cross-release pair by one joint feature. When the
            joint value was never seen in training, the two marginal nb factors are used instead
            (each still subject to the unseen-value rule) and the fallback is counted. (v1.1)
  lookup    joint lookup over the full visible tuple when it occurs >= m = 5 times in training
            (argmax of add-1 smoothed band counts for that tuple); otherwise the nb result.

Arithmetic is exact (fractions.Fraction), so ties are genuine ties and results do not depend on
float summation order. Imports: json, sys, fractions only; no files, environment or argv.
"""
import json
import sys
from fractions import Fraction

BANDS = ("low", "medium", "high")
ALPHA = 1
LOOKUP_MIN_COUNT = 5
SCHEMA_PAIRS = (("r1.event_code", "r2.resolution"), ("r1.event_type", "r2.resolution_coarse"))


def argmax(probs):
    best = BANDS[0]
    for b in BANDS[1:]:
        if probs[b] > probs[best]:  # strict: earlier band wins ties
            best = b
    return best


def normalise(scores):
    total = sum(scores.values())
    return {b: scores[b] / total for b in BANDS}


class NaiveBayes:
    def __init__(self, rows, labels):
        self.n = len(rows)
        self.class_counts = {b: 0 for b in BANDS}
        self.counts = {}         # field -> value -> band -> count
        self.field_counts = {}   # field -> band -> number of training rows of that band carrying the field
        for x, y in zip(rows, labels):
            self.class_counts[y] += 1
            for field, value in x.items():
                per_value = self.counts.setdefault(field, {})
                per_value.setdefault(value, {b: 0 for b in BANDS})[y] += 1
                self.field_counts.setdefault(field, {b: 0 for b in BANDS})[y] += 1
        self.prior = {b: Fraction(self.class_counts[b] + 1, self.n + len(BANDS)) for b in BANDS}

    def likelihood(self, field, value, band):
        """(numerator, denominator) of P(value | band), or None if this value of this field was
        never seen in training. The denominator counts only training rows of `band` that carry
        the field (v1.1: correct for optional fields; identical when every row has every field)."""
        seen = self.counts.get(field)
        if seen is None or value not in seen:
            return None  # UNSEEN-VALUE RULE: no factor for this field in this row
        return (seen[value][band] + ALPHA, self.field_counts[field][band] + ALPHA * (len(seen) + 1))

    def factors(self, field, value):
        """Per-band likelihood factors, or None under the unseen-value rule."""
        factors = [self.likelihood(field, value, b) for b in BANDS]
        return None if any(f is None for f in factors) else factors

    def posterior(self, x, fallback=None):
        """(posterior dict, number of skipped unseen values, number of pair fallbacks).

        fallback: optional (marginal model, {joint field: (field a, field b)}, original row). For
        a joint field whose value was never seen, the marginal model's factors for the two
        original fields are used instead (each subject to the unseen-value rule).
        """
        num = {b: self.prior[b].numerator for b in BANDS}
        den = {b: self.prior[b].denominator for b in BANDS}
        skipped = fallbacks = 0
        for field in sorted(x):
            factor_sets = [self.factors(field, x[field])]
            if factor_sets[0] is None and fallback is not None and field in fallback[1]:
                marginal, joint_fields, original = fallback
                fallbacks += 1
                factor_sets = [marginal.factors(f, original[f]) for f in joint_fields[field]]
            for factors in factor_sets:
                if factors is None:
                    skipped += 1
                    continue
                for b, (fn, fd) in zip(BANDS, factors):
                    num[b] *= fn
                    den[b] *= fd
        return normalise({b: Fraction(num[b], den[b]) for b in BANDS}), skipped, fallbacks


def pair_features(x):
    """Replace each schema-linked pair present in x by one joint categorical feature."""
    out = dict(x)
    for a, b in SCHEMA_PAIRS:
        if a in out and b in out:
            out["%s+%s" % (a, b)] = "%s|%s" % (out.pop(a), out.pop(b))
    return out


JOINT_FIELDS = {"%s+%s" % (a, b): (a, b) for a, b in SCHEMA_PAIRS}


def tuple_key(x):
    return tuple(sorted(x.items()))


def run(lines):
    train_x, train_y, scored = [], [], []
    for obj in lines:
        if "y" in obj:
            if obj["y"] not in BANDS:
                raise ValueError("bad label")
            train_x.append(obj["x"])
            train_y.append(obj["y"])
        else:
            scored.append(obj)

    nb = NaiveBayes(train_x, train_y)
    nb_pair = NaiveBayes([pair_features(x) for x in train_x], train_y)
    baseline_pred = argmax({b: nb.class_counts[b] for b in BANDS})
    tuple_counts = {}
    for x, y in zip(train_x, train_y):
        tuple_counts.setdefault(tuple_key(x), {b: 0 for b in BANDS})[y] += 1

    def fmt(probs):
        return [float(probs[b]) for b in BANDS]

    out = []
    for obj in scored:
        x = obj["x"]
        p_nb, skip_nb, _ = nb.posterior(x)
        p_pair, skip_pair, fb_pair = nb_pair.posterior(pair_features(x), fallback=(nb, JOINT_FIELDS, x))
        counts = tuple_counts.get(tuple_key(x))
        n_tuple = sum(counts.values()) if counts else 0
        if n_tuple >= LOOKUP_MIN_COUNT:
            p_lookup = normalise({b: Fraction(counts[b] + 1) for b in BANDS})
        else:
            p_lookup = p_nb  # fallback to nb
        out.append({
            "id": obj["id"],
            "baseline": {"pred": baseline_pred, "p": fmt(nb.prior)},
            "nb": {"pred": argmax(p_nb), "p": fmt(p_nb), "skipped": skip_nb},
            "nb_pair": {"pred": argmax(p_pair), "p": fmt(p_pair), "skipped": skip_pair, "pair_fallbacks": fb_pair},
            "lookup": {"pred": argmax(p_lookup), "p": fmt(p_lookup), "covered": n_tuple >= LOOKUP_MIN_COUNT,
                       "tuple_count": n_tuple},
        })
    return out


def main():
    raw = sys.stdin.buffer.read().decode("ascii")
    lines = [json.loads(line) for line in raw.split("\n") if line]
    for row in run(lines):
        sys.stdout.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
