"""Leakage and utility of a view, computed over a Joint (exact enumeration or Monte Carlo).

Leakage (per view):
  bayes_accuracy  sum_v max_t P(t, v): the accuracy of the best possible attacker. Exact Fraction
                  under enumeration; under Monte Carlo the resubstitution plug-in (optimistic) and
                  a held-out estimate (half/half split) with its binomial standard error.
  mi_bits         I(target; view) = H(target) - H(target | view), in bits (log2 in double precision
                  over exact probabilities, summed with math.fsum). Monte Carlo: plug-in (biased
                  upward) and Miller-Madow corrected.
  nb_limit        accuracy of naive Bayes over the view's released values with unlimited training
                  data: true prior times true per-feature marginals, ties to the first target value.
  exclusion       probability mass of view values that rule out at least one target value
                  (P(view | t) = 0); determined: exactly one target value remains.
Utility (per view), by entailment: an item is conveyed for a record iff the item's value is the
same for every positive-probability raw record that yields the same view value. This is what a
renderer that answers only when the evidence settles the answer can output. Utility is the
expected share of action items conveyed.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from fractions import Fraction


class Evaluator:
    def __init__(self, joint):
        self.joint = joint
        m = joint.model
        self.model = m
        self.T = len(m.target_values)
        n = len(joint.records)
        self.cols = [[r[i] for r in joint.records] for i in range(len(m.fields))]
        # ---- item values per record, memoised on each item's dependency fields
        self.item_vocab = [OrderedDict() for _ in m.items]
        self.item_cols = []
        for ii, it in enumerate(m.items):
            dep_idx = [m.field_index[f] for f in sorted(it.depends_on)]
            memo = {}
            col = []
            for r in joint.records:
                key = tuple(r[i] for i in dep_idx)
                code = memo.get(key)
                if code is None:
                    rec = {m.fields[i].name: m.fields[i].values[r[i]] for i in dep_idx}
                    val = it.evaluate(rec)
                    code = self.item_vocab[ii].setdefault(val, len(self.item_vocab[ii]))
                    memo[key] = code
                col.append(code)
            self.item_cols.append(col)
        self.item_values = [list(v) for v in self.item_vocab]
        # ---- interned item tuples and their action masks
        tuples = list(zip(*self.item_cols)) if m.items else [()] * n
        intern, ids = {}, []
        for tpl in tuples:
            tid = intern.get(tpl)
            if tid is None:
                tid = intern[tpl] = len(intern)
            ids.append(tid)
        self.item_ids = ids
        self.item_tuples = [None] * len(intern)
        for tpl, tid in intern.items():
            self.item_tuples[tid] = tpl
        self.action_mask = []
        for tpl in self.item_tuples:
            mask = 0
            for ii, code in enumerate(tpl):
                if m.items[ii].is_action(self.item_values[ii][code]):
                    mask |= 1 << ii
            self.action_mask.append(mask)
        self.full_mask = (1 << len(m.items)) - 1
        self._agree = {}
        tw = [0] * self.T
        for w in joint.weights:
            for t in range(self.T):
                tw[t] += w[t]
        self.target_weight = tw
        self.h_target = -math.fsum((x / joint.total) * math.log2(x / joint.total) for x in tw if x > 0)

    # ------------------------------------------------------------ keys and tables
    def keys(self, view):
        cols = []
        for part in view.parts:
            if part[0] == "field":
                _, fi, _, mp = part
                col = self.cols[fi]
                if mp is not None:
                    codes = {}
                    lut = [codes.setdefault(v, len(codes)) for v in mp]
                    col = [lut[c] for c in col]
                cols.append(col)
            else:
                cols.append(self.item_cols[part[1]])
        if not cols:
            return [()] * len(self.joint.records)
        return list(zip(*cols))

    def table(self, keys):
        agg = {}
        T = self.T
        for k, w in zip(keys, self.joint.weights):
            cell = agg.get(k)
            if cell is None:
                agg[k] = list(w)
            else:
                for t in range(T):
                    cell[t] += w[t]
        return agg

    # ------------------------------------------------------------ leakage
    def leakage(self, view, keys=None, with_nb=True):
        keys = keys if keys is not None else self.keys(view)
        agg = self.table(keys)
        total = self.joint.total
        best = 0
        excl = det = 0
        terms = []
        for cell in agg.values():
            s = sum(cell)
            best += max(cell)
            nz = sum(1 for c in cell if c > 0)
            if nz < self.T:
                excl += s
            if nz == 1:
                det += s
            ls = math.log2(s)
            for c in cell:
                if c > 0:
                    terms.append((c / total) * (math.log2(c) - ls))
        h_cond = 0.0 - math.fsum(terms)
        exact = self.joint.exact
        out = OrderedDict([
            ("n_values", len(agg)),
            ("bayes_accuracy", Fraction(best, total) if exact else best / total),
            ("mi_bits", self.h_target - h_cond),
            ("h_target_bits", self.h_target),
            ("h_target_given_view_bits", h_cond),
            ("p_exclusion", Fraction(excl, total) if exact else excl / total),
            ("p_determined", Fraction(det, total) if exact else det / total),
        ])
        if not exact:
            k_eff = len(agg) * self.T - len(agg) - self.T + 1  # (non-empty cells) df approximation
            out["mi_bits_miller_madow"] = out["mi_bits"] - max(k_eff, 0) / (2.0 * total * math.log(2))
            out["bayes_accuracy_heldout"], out["bayes_accuracy_heldout_se"] = self._heldout_accuracy(keys)
        if with_nb:
            out["nb_limit"] = self.nb_limit(view, agg)
        return out

    def _heldout_accuracy(self, keys):
        """Monte Carlo only: fit the plug-in posterior on even-indexed samples, score odd ones."""
        fit = {}
        T = self.T
        for i in range(0, len(keys), 2):
            cell = fit.setdefault(keys[i], [0] * T)
            w = self.joint.weights[i]
            for t in range(T):
                cell[t] += w[t]
        prior = [0] * T
        for i in range(0, len(keys), 2):
            for t in range(T):
                prior[t] += self.joint.weights[i][t]
        default = max(range(T), key=lambda t: (prior[t], -t))
        correct = n = 0
        for i in range(1, len(keys), 2):
            cell = fit.get(keys[i])
            pred = default if cell is None else max(range(T), key=lambda t: (cell[t], -t))
            correct += self.joint.weights[i][pred]
            n += 1
        acc = correct / n
        return acc, math.sqrt(acc * (1 - acc) / n)

    def nb_limit(self, view, agg=None):
        """Naive Bayes over the view's components with unlimited training data (exact under
        enumeration; plug-in resubstitution under Monte Carlo)."""
        agg = agg if agg is not None else self.table(self.keys(view))
        T = self.T
        tw = self.target_weight
        if not agg or not next(iter(agg)):
            best = max(range(T), key=lambda t: (tw[t], -t))
            return Fraction(tw[best], self.joint.total) if self.joint.exact else tw[best] / self.joint.total
        marg = {}
        for key, cell in agg.items():
            for pos, code in enumerate(key):
                m = marg.get((pos, code))
                if m is None:
                    m = marg[(pos, code)] = [0] * T
                for t in range(T):
                    m[t] += cell[t]
        k = len(next(iter(agg)))
        correct = 0
        if self.joint.exact:
            # P(x_f | t) = m_t / tw_t. score_t = P(t) prod_f P(x_f | t) is proportional to
            # tw_t^(1-k) prod_f m_t; compare exactly as Fractions.
            for key, cell in agg.items():
                scores = []
                for t in range(T):
                    if tw[t] == 0:
                        scores.append(Fraction(0))
                        continue
                    num = 1
                    for pos, code in enumerate(key):
                        num *= marg[(pos, code)][t]
                    scores.append(Fraction(num, tw[t] ** (k - 1)))
                best = 0
                for t in range(1, T):
                    if scores[t] > scores[best]:
                        best = t
                correct += cell[best]
            return Fraction(correct, self.joint.total)
        for key, cell in agg.items():
            scores = []
            for t in range(T):
                if tw[t] == 0:
                    scores.append(-1.0)
                    continue
                s = math.log(tw[t])
                for pos, code in enumerate(key):
                    mm = marg[(pos, code)][t]
                    s += math.log(mm / tw[t]) if mm > 0 else -1e300
                scores.append(s)
            best = max(range(T), key=lambda t: (scores[t], -t))
            correct += cell[best]
        return correct / self.joint.total

    def exclusions(self, view, keys=None, limit=8):
        """Up to `limit` view values (by mass) that rule out a target value, decoded."""
        keys = keys if keys is not None else self.keys(view)
        agg = self.table(keys)
        examples = {}
        for r_idx, k in enumerate(keys):
            if k not in examples:
                examples[k] = r_idx
        rows = []
        for k, cell in agg.items():
            zero = [self.model.target_values[t] for t in range(self.T) if cell[t] == 0]
            if zero:
                rows.append((sum(cell), self.describe(view, examples[k]), zero))
        rows.sort(key=lambda r: (-r[0], str(r[1])))
        return [(Fraction(m, self.joint.total) if self.joint.exact else m / self.joint.total, d, z) for m, d, z in rows[:limit]]

    def describe(self, view, record_index):
        """Readable released values of one record under a view."""
        m = self.model
        r = self.joint.records[record_index]
        out = OrderedDict()
        for part in view.parts:
            if part[0] == "field":
                _, fi, name, mp = part
                out[name] = m.fields[fi].values[r[fi]] if mp is None else mp[r[fi]]
            else:
                out[part[2]] = self.item_values[part[1]][self.item_cols[part[1]][record_index]]
        return out

    # ------------------------------------------------------------ utility by entailment
    def _agree_mask(self, a, b):
        key = (a, b) if a < b else (b, a)
        m = self._agree.get(key)
        if m is None:
            ta, tb = self.item_tuples[a], self.item_tuples[b]
            m = 0
            for i, (x, y) in enumerate(zip(ta, tb)):
                if x == y:
                    m |= 1 << i
            self._agree[key] = m
        return m

    def constant_masks(self, keys):
        first, const = {}, {}
        for k, tid in zip(keys, self.item_ids):
            f = first.get(k)
            if f is None:
                first[k] = tid
                const[k] = self.full_mask
            elif f != tid:
                const[k] &= self._agree_mask(f, tid)
        return const

    def utility(self, view, keys=None, per_item=False):
        if not self.model.items:
            return OrderedDict([("action", 0), ("conveyed", 0), ("share", None)])
        keys = keys if keys is not None else self.keys(view)
        const = self.constant_masks(keys)
        action = conveyed = 0
        n_items = len(self.model.items)
        per = [[0, 0, 0] for _ in range(n_items)]  # action, conveyed, entailed (any value)
        for k, tid, w in zip(keys, self.item_ids, self.joint.wsum):
            am = self.action_mask[tid]
            cm = const[k] & am
            action += w * bin(am).count("1")
            conveyed += w * bin(cm).count("1")
            if per_item:
                c_all = const[k]
                for i in range(n_items):
                    bit = 1 << i
                    if am & bit:
                        per[i][0] += w
                        if c_all & bit:
                            per[i][1] += w
                    if c_all & bit:
                        per[i][2] += w
        total = self.joint.total
        exact = self.joint.exact

        def q(x):
            return Fraction(x, total) if exact else x / total
        out = OrderedDict([("action", q(action)), ("conveyed", q(conveyed)),
                           ("share", (Fraction(conveyed, action) if exact else conveyed / action) if action else None)])
        if per_item:
            out["per_item"] = OrderedDict((it.name, OrderedDict([("action", q(per[i][0])), ("conveyed", q(per[i][1])),
                                                                  ("entailed", q(per[i][2]))]))
                                          for i, it in enumerate(self.model.items))
        return out

    def entailed_outputs(self, view):
        """Per record: tuple of item values the view entails (None where it does not)."""
        keys = self.keys(view)
        const = self.constant_masks(keys)
        out = []
        n_items = len(self.model.items)
        for k, tid in zip(keys, self.item_ids):
            c = const[k]
            tpl = self.item_tuples[tid]
            out.append(tuple(self.item_values[i][tpl[i]] if c & (1 << i) else None for i in range(n_items)))
        return out
