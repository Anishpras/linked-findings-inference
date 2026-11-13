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


def iter_records(scenario):
    """Yield (raw record, (N_low, N_medium, N_high)) for every raw record, with P(raw | band) =
    N_band / D exactly; also returns D through the first element of the generator protocol:
    use `records(scenario)` for a materialised list and D."""
    dists = generator.distributions(scenario)
    blocks, D = [], 1
    for block in _blocks(dists):
        rows, den = _integerise(block)
        blocks.append(rows)
        D *= den
    yield D
    for combo in itertools.product(*blocks):
        raw = {}
        nl = nm = nh = 1
        for assign, (a, b, c) in combo:
            raw.update(assign)
            nl *= a
            nm *= b
            nh *= c
        yield raw, (nl, nm, nh)


def records(scenario):
    it = iter_records(scenario)
    D = next(it)
    return D, list(it)


def build(scenario):
    """Exact tables {view: {view_key: [N_low, N_medium, N_high]}} and the common denominator D."""
    pc = bool(spec.SCENARIOS[scenario].get("band_field"))
    view_list = spec.POSITIVE_CONTROL_VIEWS if pc else spec.VIEWS
    it = iter_records(scenario)
    D = next(it)
    tables = OrderedDict((v, {}) for v in view_list)
    n_records = 0
    for raw, nums in it:
        n_records += 1
        nl, nm, nh = nums
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


def build_custom(scenario, view_fns):
    """Exact tables for arbitrary views: view_fns maps a name to a function raw -> hashable key.
    Used for the exploratory E-vs-D variants (v1.1)."""
    it = iter_records(scenario)
    D = next(it)
    tables = OrderedDict((name, {}) for name in view_fns)
    for raw, (nl, nm, nh) in it:
        for name, fn in view_fns.items():
            table = tables[name]
            key = fn(raw)
            cell = table.get(key)
            if cell is None:
                cell = table[key] = [0, 0, 0]
            cell[0] += nl
            cell[1] += nm
            cell[2] += nh
    pi = tuple(spec.SCENARIOS[scenario]["pi"][b] for b in spec.BANDS)
    return OrderedDict([("scenario", scenario), ("D", D), ("pi", pi), ("tables", tables)])


def nb_limit(orc, view, pair=False):
    """Exact accuracy of the nb attacker with unlimited training data (v1.1, review 2.1).

    With infinite training data nb's estimates converge to the true prior pi(b) and the true
    per-field marginals P(x_f | b), which are read off the exact table by summing over view
    values. nb then predicts argmax_b pi(b) prod_f P(x_f | b) (ties low, medium, high), and its
    accuracy is sum_v pi(pred(v)) P(v | pred(v)). With pair=True the schema-linked pair is one
    joint feature, exactly as in the nb_pair attacker. Integer arithmetic: every marginal is an
    integer numerator over D, and the common factor D^k is dropped from the comparison.
    """
    from . import attacker  # the attacker's own pair rule, so the limit matches nb_pair exactly
    table = orc["tables"][view]
    a, A = _pi_int(orc["pi"])

    def feats(key):
        x = dict(key)
        if pair:
            x = attacker.pair_features(x)
        return sorted(x.items())

    marg = {}
    for key, cell in table.items():
        for fv in feats(key):
            m = marg.get(fv)
            if m is None:
                m = marg[fv] = [0, 0, 0]
            m[0] += cell[0]
            m[1] += cell[1]
            m[2] += cell[2]
    correct = 0
    for key, cell in table.items():
        if cell[0] == cell[1] == cell[2] == 0:
            continue
        s0, s1, s2 = a
        for fv in feats(key):
            m = marg[fv]
            s0 *= m[0]
            s1 *= m[1]
            s2 *= m[2]
        best = 0
        if s1 > s0:
            best = 1
        if s2 > (s1 if best == 1 else s0):
            best = 2
        correct += a[best] * cell[best]
    return Fraction(correct, A * orc["D"])


def nb_limits(scenario):
    """{view: (nb_limit, nb_pair_limit)} for one scenario (process-pool worker)."""
    orc = build(scenario)
    return OrderedDict((v, (nb_limit(orc, v, False), nb_limit(orc, v, True))) for v in orc["tables"])


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
