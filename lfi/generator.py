"""Synthetic household generator (PROTOCOL.md sections 3.4 and 3.6-3.8).

Determinism rules (identical output on Python 3.9-3.14):
  * every random number is `random.Random(seed).random()`; categorical draws use inverse-CDF
    lookup against cumulative sums; shuffles sort by `rng.random()` keys (ties by index);
  * each household consumes exactly 12 uniforms in a fixed order, whether or not every one is
    used (an unused draw, e.g. event type when no event occurs, is simply ignored);
  * cumulative sums are exact Fractions converted to float once, so thresholds do not depend on
    float summation order.
"""
from __future__ import annotations

import hashlib
import hmac
from collections import OrderedDict
from fractions import Fraction
from random import Random

from . import spec

SEED_PURPOSES = ("generate", "split", "ids", "attacker_order", "bootstrap")
UNIFORMS_PER_HOUSEHOLD = 12


def subseed(master, scenario, purpose):
    """Sub-seed for one purpose: first 8 bytes of sha256("{master}:{scenario}:{purpose}")."""
    digest = hashlib.sha256(("%s:%s:%s" % (master, scenario, purpose)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def replicate_master(k):
    """Master seed of seed replicate k (1..5): the 'replicate_k' sub-seed of the main scenario."""
    return subseed(spec.MASTER_SEED, "main", "replicate_%d" % k)


# ---------------------------------------------------------------- distributions
def _mix(lam, marginal, conditional):
    return tuple((1 - lam) * m + lam * c for m, c in zip(marginal, conditional))


def distributions(scenario):
    """Exact generator distributions for one scenario.

    P_lambda(f | b) = (1 - lambda) M(f) + lambda P(f | b), with M(f) = sum_b pi_main(b) P(f | b).
    Resolution is mixed separately for each event size. Prevalence variants keep lambda = 1.
    Returns an OrderedDict: "pi" -> tuple over BANDS; band-dependent field -> {band: tuple};
    "resolution" -> {(size, band): tuple}; band-independent field -> tuple.
    """
    cfg = spec.SCENARIOS[scenario]
    lam = cfg["lam"]
    out = OrderedDict()
    out["pi"] = tuple(cfg["pi"][b] for b in spec.BANDS)
    for field, (values, cond) in spec.BAND_DEPENDENT.items():
        marginal = tuple(sum(spec.PI_MAIN[b] * cond[b][i] for b in spec.BANDS) for i in range(len(values)))
        out[field] = OrderedDict((b, _mix(lam, marginal, cond[b])) for b in spec.BANDS)
    res = OrderedDict()
    for size, cond in spec.RESOLUTION.items():
        marginal = tuple(sum(spec.PI_MAIN[b] * cond[b][i] for b in spec.BANDS)
                         for i in range(len(spec.RESOLUTIONS)))
        for b in spec.BANDS:
            res[(size, b)] = _mix(lam, marginal, cond[b])
    out["resolution"] = res
    for field, (_values, probs) in spec.BAND_INDEPENDENT.items():
        out[field] = probs
    _assert_normalised(out)
    return out


def _assert_normalised(dists):
    def ok(t):
        return sum(t) == 1 and all(p >= 0 for p in t)
    for key, value in dists.items():
        tables = value.values() if isinstance(value, dict) else [value]
        for t in tables:
            if not ok(t):
                raise ValueError("distribution %s does not sum to 1: %s" % (key, t))


# ---------------------------------------------------------------- sampling
def _table(values, probs):
    """Inverse-CDF table: (value, float(exact cumulative sum)) pairs plus a fallback value.

    A zero-probability value gets the same threshold as its predecessor (0.0 if it is first), so
    `u < threshold` can never select it: the hard zero is never sampled. The fallback (last value
    with positive probability) is unreachable because the final threshold is exactly 1.0, but
    guards against any future table whose float sum falls short of 1.
    """
    cum = Fraction(0)
    rows = []
    for v, p in zip(values, probs):
        cum += p
        rows.append((v, float(cum)))
    fallback = [v for v, p in zip(values, probs) if p > 0][-1]
    return rows, fallback


def draw(table, u):
    rows, fallback = table
    for value, threshold in rows:
        if u < threshold:
            return value
    return fallback


def _sampling_tables(dists):
    t = {"band": _table(spec.BANDS, dists["pi"])}
    for field, (values, _cond) in spec.BAND_DEPENDENT.items():
        t[field] = {b: _table(values, dists[field][b]) for b in spec.BANDS}
    t["resolution"] = {key: _table(spec.RESOLUTIONS, probs) for key, probs in dists["resolution"].items()}
    for field, (values, _probs) in spec.BAND_INDEPENDENT.items():
        t[field] = _table(values, dists[field])
    return t


def generate_raw(scenario, seed, n):
    """List of (band, raw) in generation order. raw is the flat release-1 + release-2 map."""
    t = _sampling_tables(distributions(scenario))
    rng = Random(seed)
    out = []
    for _ in range(n):
        u = [rng.random() for _ in range(UNIFORMS_PER_HOUSEHOLD)]
        band = draw(t["band"], u[0])
        occurs = draw(t["event_occurs"], u[3]) == "yes"
        etype = draw(t["event_type"], u[4])
        size = draw(t["event_size"], u[5])
        raw = OrderedDict()
        raw["r1.income_pattern"] = draw(t["r1.income_pattern"][band], u[1])
        raw["r1.essential_share"] = draw(t["r1.essential_share"][band], u[2])
        raw["r1.event_code"] = "%s_%s" % (etype, size) if occurs else "none"
        raw["r1.payment_flag"] = draw(t["r1.payment_flag"][band], u[6])
        raw["r1.contact_channel"] = draw(t["r1.contact_channel"], u[7])
        raw["r2.resolution"] = (draw(t["resolution"][(size, band)], u[8]) if occurs
                                else spec.NO_EVENT_RESOLUTION)
        raw["r2.payment_flag"] = draw(t["r2.payment_flag"][band], u[9])
        raw["r2.goal"] = draw(t["r2.goal"][band], u[10])
        raw["r2.document_status"] = draw(t["r2.document_status"], u[11])
        out.append((band, raw))
    return out


def assign_splits(n, seed, sizes=spec.SPLIT_SIZES):
    """Per-household split by seeded shuffle: sort indices by rng.random() keys (ties by index),
    then cut into train / dev / test. Returns split name per generation index."""
    if sum(s for _, s in sizes) != n:
        raise ValueError("split sizes do not sum to n")
    rng = Random(seed)
    keys = [rng.random() for _ in range(n)]
    order = sorted(range(n), key=lambda i: (keys[i], i))
    split = [None] * n
    pos = 0
    for name, size in sizes:
        for i in order[pos:pos + size]:
            split[i] = name
        pos += size
    return split


def household_ids(n, seed):
    """Opaque IDs: HMAC-SHA256 of the generation index under a secret derived from the ids
    sub-seed. Neither the secret nor the index mapping is ever given to the attacker."""
    secret = hashlib.sha256(b"lfi-household-id-secret:" + seed.to_bytes(8, "big")).digest()
    ids = ["h" + hmac.new(secret, str(i).encode("ascii"), hashlib.sha256).hexdigest()[:16] for i in range(n)]
    if len(set(ids)) != n:
        raise ValueError("opaque ID collision")
    return ids


def order_keys(n, seed):
    """Seeded keys that fix the (label-independent) row order the attacker receives."""
    rng = Random(seed)
    return [rng.random() for _ in range(n)]


def generate(scenario, master=spec.MASTER_SEED, n=spec.N_HOUSEHOLDS, split_sizes=spec.SPLIT_SIZES):
    """One scenario's households (sorted by opaque ID) with band, split and raw record."""
    seeds = OrderedDict((p, subseed(master, scenario, p)) for p in SEED_PURPOSES)
    raws = generate_raw(scenario, seeds["generate"], n)
    splits = assign_splits(n, seeds["split"], split_sizes)
    ids = household_ids(n, seeds["ids"])
    keys = order_keys(n, seeds["attacker_order"])
    households = []
    for i, (band, raw) in enumerate(raws):
        households.append(OrderedDict([("id", ids[i]), ("gen_index", i), ("band", band),
                                       ("split", splits[i]), ("raw", raw)]))
    households.sort(key=lambda h: h["id"])
    return OrderedDict([
        ("scenario", scenario), ("master_seed", master), ("seeds", seeds),
        ("positive_control", bool(spec.SCENARIOS[scenario].get("band_field"))),
        ("households", households),
        ("order_key", {ids[i]: keys[i] for i in range(n)}),
    ])
