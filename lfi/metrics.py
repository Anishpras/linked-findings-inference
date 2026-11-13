"""Measures and bootstrap intervals (PROTOCOL.md section 6, S9).

Portability: every float sum uses math.fsum (correctly rounded, order-independent). The built-in
sum() of floats changed to compensated summation in Python 3.12, which would make outputs differ
between 3.9-3.11 and 3.12+.

Bootstrap: 2,000 resamples of the scored households with a seeded Random; resample r is a vector
of multiplicities w_r (household i drawn w_r[i] times, draws by int(u * n)). The same w_r is
applied to every view and every attacker, so paired differences resample households jointly.
Percentile interval: the sorted statistics at 0-based positions floor(0.025 B) and
B - 1 - floor(0.025 B), i.e. positions 50 and 1949 for B = 2,000 (the central 1,900 values).
"""
from __future__ import annotations

import math
from collections import OrderedDict
from fractions import Fraction
from itertools import compress
from operator import mul
from random import Random

from . import spec


def logloss_bits(p):
    return -math.log2(max(p, spec.LOGLOSS_CLIP))


def point(true, pred, p_true):
    """Point metrics for one (scenario, view, model). true/pred: band names; p_true: floats."""
    n = len(true)
    B = spec.BANDS
    confusion = OrderedDict((t, OrderedDict((p, 0) for p in B)) for t in B)
    for t, p in zip(true, pred):
        confusion[t][p] += 1
    n_band = OrderedDict((b, sum(confusion[b].values())) for b in B)
    c_band = OrderedDict((b, confusion[b][b]) for b in B)
    correct = sum(c_band.values())
    recall = OrderedDict((b, (c_band[b] / n_band[b]) if n_band[b] else None) for b in B)
    present = [r for r in recall.values() if r is not None]
    return OrderedDict([
        ("n", n), ("correct", correct), ("accuracy", Fraction(correct, n)),
        ("n_band", n_band), ("correct_band", c_band), ("recall", recall),
        ("bands_absent", [b for b in B if not n_band[b]]),
        ("macro_recall", math.fsum(present) / len(present)),
        ("mean_p_true", math.fsum(p_true) / n),
        ("mean_logloss_bits", math.fsum(logloss_bits(p) for p in p_true) / n),
        ("confusion", confusion),
    ])


def resample_weights(seed, n, n_resamples=spec.N_BOOTSTRAP):
    rng = Random(seed)
    for _ in range(n_resamples):
        w = [0] * n
        for _ in range(n):
            w[min(int(rng.random() * n), n - 1)] += 1
        yield w


def bootstrap(seed, band_index, series, n_resamples=spec.N_BOOTSTRAP):
    """Per-resample statistics for every key.

    band_index: list of 0/1/2 (true band) per household, in the fixed household order.
    series: {key: (correct 0/1 list, logloss float list)} in the same household order.
    Returns {key: {"correct": [int], "macro_recall": [float], "logloss": [float]}}.
    """
    n = len(band_index)
    in_band = [[1 if bi == k else 0 for bi in band_index] for k in range(3)]
    masks = {key: [[c & m for c, m in zip(correct, in_band[k])] for k in range(3)]
             for key, (correct, _ll) in series.items()}
    out = {key: {"correct": [], "macro_recall": [], "logloss": []} for key in series}
    for w in resample_weights(seed, n, n_resamples):
        n_b = [sum(compress(w, in_band[k])) for k in range(3)]
        for key, (_correct, ll) in series.items():
            c_b = [sum(compress(w, masks[key][k])) for k in range(3)]
            rec = [c_b[k] / n_b[k] for k in range(3) if n_b[k]]
            o = out[key]
            o["correct"].append(c_b[0] + c_b[1] + c_b[2])
            o["macro_recall"].append(math.fsum(rec) / len(rec))
            o["logloss"].append(math.fsum(map(mul, w, ll)) / n)
    return out


def percentile_ci(values):
    s = sorted(values)
    lo = (len(s) * 25) // 1000
    return s[lo], s[len(s) - 1 - lo]


def ci_accuracy(counts, n):
    lo, hi = percentile_ci(counts)
    return Fraction(lo, n), Fraction(hi, n)


def paired(boot, key_x, key_y, n):
    """Bootstrap CIs of X - Y for accuracy, macro recall and log-loss (same resamples)."""
    bx, by = boot[key_x], boot[key_y]
    acc = percentile_ci([a - b for a, b in zip(bx["correct"], by["correct"])])
    mr = percentile_ci([a - b for a, b in zip(bx["macro_recall"], by["macro_recall"])])
    ll = percentile_ci([a - b for a, b in zip(bx["logloss"], by["logloss"])])
    return OrderedDict([("accuracy", (Fraction(acc[0], n), Fraction(acc[1], n))),
                        ("macro_recall", mr), ("logloss", ll)])


def discordant(correct_x, correct_y):
    """(correct in X only, correct in Y only)."""
    x_only = sum(1 for a, b in zip(correct_x, correct_y) if a and not b)
    y_only = sum(1 for a, b in zip(correct_x, correct_y) if b and not a)
    return x_only, y_only
