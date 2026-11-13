"""Reference ceiling: the exact Bayes posterior under the true generator (PROTOCOL.md section 5).

Enumeration. Given the band, the raw record factorises into independent blocks: income, share,
(event occurrence, type, size, resolution), release-1 flag, channel, release-2 flag, goal and
documents. For each block every probability is an exact Fraction; it is rescaled to an integer
numerator over that block's common denominator (lcm over all entries and bands). The
probability of a raw record given band b is then (product of block numerators) / D, where D, the
product of the block denominators, is the same for every record and band. Enumerating all
2*3*19*4*3*4*4*3 = 65,664 raw records, mapping each to every view with the same make_view used
for the data, and adding numerators gives P(view = v | b) = N_b(v) / D with integer N_b(v).
Exact integers mean the hard zero is exactly zero, and logical exclusion (N_b(v) = 0) and
determination (exactly one band non-zero) are read off without tolerance.

Population quantities per view: Bayes accuracy sum_v max_b pi(b) P(v|b) (exact Fraction), the
probability mass on which some band is excluded / the band is determined (exact), and the S9
information measures H(band), H(band | view) and I(band; view) in bits (exact enumeration;
log2 in double precision, summed with math.fsum).
"""
from __future__ import annotations

import itertools
import math
from collections import OrderedDict
from fractions import Fraction

from . import generator, spec, views


def _lcm(a, b):
    return a * b // math.gcd(a, b)


def _blocks(dists):
    """List of blocks; each block is a list of (assignment pairs, (p_low, p_medium, p_high))."""
    B = spec.BANDS
    occ = dict(zip(spec.EVENT_OCCURS, dists["event_occurs"]))
    typ = dict(zip(spec.EVENT_TYPES, dists["event_type"]))
    siz = dict(zip(spec.EVENT_SIZES, dists["event_size"]))

    def dependent(field, values):
        return [(((field, v),), tuple(dists[field][b][i] for b in B)) for i, v in enumerate(values)]

    def independent(field, values):
        return [(((field, v),), (dists[field][i],) * 3) for i, v in enumerate(values)]

    event = [((("r1.event_code", "none"), ("r2.resolution", spec.NO_EVENT_RESOLUTION)), (occ["no"],) * 3)]
    for t in spec.EVENT_TYPES:
        for s in spec.EVENT_SIZES:
            for i, r in enumerate(spec.RESOLUTIONS):
                probs = tuple(occ["yes"] * typ[t] * siz[s] * dists["resolution"][(s, b)][i] for b in B)
                event.append(((("r1.event_code", "%s_%s" % (t, s)), ("r2.resolution", r)), probs))
    return [
        dependent("r1.income_pattern", spec.INCOME),
        dependent("r1.essential_share", spec.SHARE),
        event,
        dependent("r1.payment_flag", spec.FLAGS),
        independent("r1.contact_channel", spec.CHANNELS),
        dependent("r2.payment_flag", spec.FLAGS),
        dependent("r2.goal", spec.GOALS),
        independent("r2.document_status", spec.DOCUMENTS),
    ]


def _integerise(block):
    den = 1
    for _assign, probs in block:
        for p in probs:
            den = _lcm(den, p.denominator)
    rows = []
    for assign, probs in block:
        nums = tuple(p.numerator * (den // p.denominator) for p in probs)
        rows.append((assign, nums))
    for b in range(3):  # each block must sum to exactly 1 for every band
        if sum(r[1][b] for r in rows) != den:
            raise ValueError("oracle block does not sum to 1")
    return rows, den


def build(scenario):
    """Exact tables {view: {view_key: [N_low, N_medium, N_high]}} and the common denominator D."""
    dists = generator.distributions(scenario)
    pc = bool(spec.SCENARIOS[scenario].get("band_field"))
    view_list = spec.POSITIVE_CONTROL_VIEWS if pc else spec.VIEWS
    blocks, D = [], 1
    for block in _blocks(dists):
        rows, den = _integerise(block)
        blocks.append(rows)
        D *= den
    tables = OrderedDict((v, {}) for v in view_list)
    n_records = 0
    for combo in itertools.product(*blocks):
        n_records += 1
        raw = {}
        nl = nm = nh = 1
        for assign, (a, b, c) in combo:
            raw.update(assign)
            nl *= a
            nm *= b
            nh *= c
        nums = (nl, nm, nh)
        for v in view_list:
            table = tables[v]
            if pc:
                # The band field is part of the view: record r with band b maps to a key that
                # carries b, so each key accumulates mass under one band only.
                for bi, band in enumerate(spec.BANDS):
                    key = views.view_key(views.make_view(v, raw, band, True))
                    cell = table.get(key)
                    if cell is None:
                        cell = table[key] = [0, 0, 0]
                    cell[bi] += nums[bi]
            else:
                key = views.view_key(views.make_view(v, raw, None, False))
                cell = table.get(key)
                if cell is None:
                    cell = table[key] = [0, 0, 0]
                cell[0] += nl
                cell[1] += nm
                cell[2] += nh
    pi = tuple(spec.SCENARIOS[scenario]["pi"][b] for b in spec.BANDS)
    return OrderedDict([("scenario", scenario), ("D", D), ("pi", pi), ("tables", tables),
                        ("n_raw_records", n_records)])


def _pi_int(pi):
    A = 1
    for p in pi:
        A = _lcm(A, p.denominator)
    return tuple(p.numerator * (A // p.denominator) for p in pi), A


def entropy_bits(probs):
    return -math.fsum(float(p) * math.log2(p) for p in probs if p > 0)


def population(oracle):
    """Exact population summaries per view (plus a 'baseline' row: the empty view)."""
    D, pi = oracle["D"], oracle["pi"]
    a, A = _pi_int(pi)
    total = A * D
    h_prior = entropy_bits(pi)
    out = OrderedDict()
    out["baseline"] = OrderedDict([
        ("n_view_values", 1), ("bayes_accuracy", max(pi)), ("p_exclusion", Fraction(0)),
        ("p_determined", Fraction(0)), ("h_band_bits", h_prior), ("h_band_given_view_bits", h_prior),
        ("mi_bits", 0.0), ("band_sums_ok", True)])
    for v, table in oracle["tables"].items():
        acc = excl = det = 0
        n_values = 0
        terms = []
        sums = [0, 0, 0]
        for cell in table.values():
            w = [a[i] * cell[i] for i in range(3)]
            s = w[0] + w[1] + w[2]
            for i in range(3):
                sums[i] += cell[i]
            if s == 0:
                # Zero mass under every band (only arises in the positive control, where a
                # low-band record with the impossible (major, settled_in_full) pair still gets
                # a key carrying 'low'). Outside the support: contributes nothing.
                continue
            n_values += 1
            acc += max(w)
            nonzero = sum(1 for c in cell if c > 0)
            if nonzero < 3:
                excl += s
            if nonzero == 1:
                det += s
            log_s = math.log2(s)
            for wi in w:
                if wi > 0:
                    terms.append((wi / total) * (math.log2(wi) - log_s))
        h_cond = -math.fsum(terms)
        out[v] = OrderedDict([
            ("n_view_values", n_values), ("bayes_accuracy", Fraction(acc, total)),
            ("p_exclusion", Fraction(excl, total)), ("p_determined", Fraction(det, total)),
            ("h_band_bits", h_prior), ("h_band_given_view_bits", h_cond), ("mi_bits", h_prior - h_cond),
            ("band_sums_ok", all(s == D for s in sums))])
    return out


def posterior(oracle, view, x):
    """Exact posterior (dict band -> Fraction), excluded bands and determination for one view map.
    Raises KeyError if the view value has probability zero under every band."""
    cell = oracle["tables"][view][views.view_key(x)]
    a, _A = _pi_int(oracle["pi"])
    w = [a[i] * cell[i] for i in range(3)]
    s = sum(w)
    if s == 0:
        raise KeyError("view value outside the generator's support")
    post = OrderedDict((b, Fraction(w[i], s)) for i, b in enumerate(spec.BANDS))
    excluded = [b for i, b in enumerate(spec.BANDS) if cell[i] == 0]
    return post, excluded, len(excluded) == 2


def argmax(post):
    best = spec.BANDS[0]
    for b in spec.BANDS[1:]:
        if post[b] > post[best]:
            best = b
    return best
