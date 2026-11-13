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
  nb_pair   nb after replacing a schema-linked cross-release pair by one joint feature.
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
        self.counts = {}  # field -> value -> band -> count
        for x, y in zip(rows, labels):
            self.class_counts[y] += 1
            for field, value in x.items():
                per_value = self.counts.setdefault(field, {})
                per_value.setdefault(value, {b: 0 for b in BANDS})[y] += 1
        self.prior = {b: Fraction(self.class_counts[b] + 1, self.n + len(BANDS)) for b in BANDS}

    def likelihood(self, field, value, band):
        """(numerator, denominator) of P(value | band), or None if this value of this field was
        never seen in training."""
        seen = self.counts.get(field)
        if seen is None or value not in seen:
            return None  # UNSEEN-VALUE RULE: no factor for this field in this row
        return (seen[value][band] + ALPHA, self.class_counts[band] + ALPHA * (len(seen) + 1))

    def posterior(self, x):
        """(posterior dict, number of skipped unseen values)."""
        num = {b: self.prior[b].numerator for b in BANDS}
        den = {b: self.prior[b].denominator for b in BANDS}
        skipped = 0
        for field in sorted(x):
            factors = [self.likelihood(field, x[field], b) for b in BANDS]
            if any(f is None for f in factors):
                skipped += 1
                continue
            for b, (fn, fd) in zip(BANDS, factors):
                num[b] *= fn
                den[b] *= fd
        return normalise({b: Fraction(num[b], den[b]) for b in BANDS}), skipped


def pair_features(x):
    """Replace each schema-linked pair present in x by one joint categorical feature."""
    out = dict(x)
    for a, b in SCHEMA_PAIRS:
        if a in out and b in out:
            out["%s+%s" % (a, b)] = "%s|%s" % (out.pop(a), out.pop(b))
    return out


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
        p_nb, skip_nb = nb.posterior(x)
        p_pair, skip_pair = nb_pair.posterior(pair_features(x))
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
            "nb_pair": {"pred": argmax(p_pair), "p": fmt(p_pair), "skipped": skip_pair},
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
