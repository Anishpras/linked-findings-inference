"""Exact expected utility per household, by full enumeration (v1.1, post-review correction).

For every raw record r, P(r) = sum_b pi(b) P(r | b) exactly (integer numerators from the oracle
enumeration). For each view and renderer, each item's output is classified as:
  supported_correct    the strict renderer answers (the view entails the answer) and it is right
  supported_wrong      the strict renderer answers and it is wrong (must be exactly 0)
  unsupported_correct  only the default-filling renderer answers, and its default happens to be
                       right (a lucky default)
  unsupported_wrong    only the default-filling renderer answers, and its default is wrong
  omission             no output
Only supported outputs earn action-item credit (review 2.2). Expectations are exact Fractions.
"""
from __future__ import annotations

from collections import OrderedDict
from fractions import Fraction

from . import checklist, oracle, spec, views

CLASSES = ("supported_correct", "supported_wrong", "unsupported_correct", "unsupported_wrong", "omission")
PASS_THROUGH_ITEMS = ("contact_channel", "goal_module", "documents_request")  # verbatim copies of one field


def classify(correct, strict_output, output):
    if output is None:
        return "omission"
    if strict_output is not None:
        return "supported_correct" if output == correct else "supported_wrong"
    return "unsupported_correct" if output == correct else "unsupported_wrong"


def exact_utility(scenario="main"):
    """{(view, renderer): {"per_item": {item: {class: Fraction, "action": F, "action_conveyed": F}},
    "action": F, "action_conveyed": F, class: F}} as expectations per household."""
    D, recs = oracle.records(scenario)
    pi = tuple(spec.SCENARIOS[scenario]["pi"][b] for b in spec.BANDS)
    a, A = oracle._pi_int(pi)
    total = A * D
    acc = OrderedDict()
    for v in spec.VIEWS:
        for r in spec.RENDERERS:
            acc[(v, r)] = OrderedDict((it, OrderedDict([(c, 0) for c in CLASSES] + [("action", 0), ("action_conveyed", 0)]))
                                      for it in spec.ITEMS)
    for raw, nums in recs:
        w = a[0] * nums[0] + a[1] * nums[1] + a[2] * nums[2]
        if w == 0:
            continue
        ans = checklist.correct_answers(raw)
        for v in spec.VIEWS:
            strict = checklist.render_strict(views.make_view(v, raw, None, False))
            for r in spec.RENDERERS:
                cells = acc[(v, r)]
                for it in spec.ITEMS:
                    s_out = strict[it]
                    out = s_out if (r == "strict" or s_out is not None) else spec.DEFAULT_FILL[it]
                    cls = classify(ans[it], s_out, out)
                    cell = cells[it]
                    cell[cls] += w
                    if checklist.is_action_item(it, ans[it]):
                        cell["action"] += w
                        if cls == "supported_correct":
                            cell["action_conveyed"] += w
    out = OrderedDict()
    for key, cells in acc.items():
        per_item = OrderedDict((it, OrderedDict((k, Fraction(x, total)) for k, x in c.items())) for it, c in cells.items())
        summary = OrderedDict((k, sum((per_item[it][k] for it in spec.ITEMS), Fraction(0)))
                              for k in CLASSES + ("action", "action_conveyed"))
        summary["per_item"] = per_item
        out[key] = summary
    return out
