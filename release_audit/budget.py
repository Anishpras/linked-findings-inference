"""Per-field information budget (review section 7.2).

For the full linked view (every released field kept):
  * each field alone: I(target; field) and Bayes accuracy;
  * each field dropped: the loss of I and of Bayes accuracy from the full linked view;
  * each declared coarsening applied alone in the full view: the loss it buys;
  * every cross-stage pair of fields: synergy S(f, g) = I(target; f, g) - I(target; f) - I(target; g).
    Positive synergy means the pair says more together than the sum of its parts (an interaction
    across releases); negative means redundancy;
  * a scan for logical exclusions created only by linking: cross-stage pairs whose joint values
    rule out a target value although neither field alone does.
"""
from __future__ import annotations

from collections import OrderedDict

from .viewdefs import make_view


def _full_options(model):
    return OrderedDict((f.name, "keep") for f in model.released_fields())


def budget(ev):
    m = ev.model
    full_opts = _full_options(m)
    full = ev.leakage(make_view(m, "linked", full_opts), with_nb=False)
    fields = []
    alone_cache = {}
    for f in m.released_fields():
        alone = ev.leakage(make_view(m, f.name, {f.name: "keep"}), with_nb=False)
        alone_cache[f.name] = alone
        dropped = ev.leakage(make_view(m, "-" + f.name, OrderedDict((k, v) for k, v in full_opts.items() if k != f.name)),
                             with_nb=False)
        row = OrderedDict([("field", f.name), ("stage", f.stage), ("mi_alone", alone["mi_bits"]),
                           ("bayes_alone", alone["bayes_accuracy"]),
                           ("mi_loss_if_dropped", full["mi_bits"] - dropped["mi_bits"]),
                           ("bayes_loss_if_dropped", full["bayes_accuracy"] - dropped["bayes_accuracy"]),
                           ("p_exclusion_alone", alone["p_exclusion"]), ("coarsenings", OrderedDict())])
        for cname in f.coarsenings:
            opts = OrderedDict(full_opts)
            opts[f.name] = "coarsen:%s" % cname
            c = ev.leakage(make_view(m, "%s~%s" % (f.name, cname), opts), with_nb=False)
            row["coarsenings"][cname] = OrderedDict([("mi_loss", full["mi_bits"] - c["mi_bits"]),
                                                     ("bayes_loss", full["bayes_accuracy"] - c["bayes_accuracy"])])
        fields.append(row)
    pairs = []
    rel = m.released_fields()
    for i in range(len(rel)):
        for j in range(i + 1, len(rel)):
            f, g = rel[i], rel[j]
            if f.stage == g.stage:
                continue
            view = make_view(m, "%s+%s" % (f.name, g.name), OrderedDict([(f.name, "keep"), (g.name, "keep")]))
            keys = ev.keys(view)
            pair = ev.leakage(view, keys=keys, with_nb=False)
            syn = pair["mi_bits"] - alone_cache[f.name]["mi_bits"] - alone_cache[g.name]["mi_bits"]
            new_excl = (ev.joint.exact and pair["p_exclusion"] > 0 and alone_cache[f.name]["p_exclusion"] == 0
                        and alone_cache[g.name]["p_exclusion"] == 0)
            pairs.append(OrderedDict([("fields", (f.name, g.name)), ("stages", (f.stage, g.stage)),
                                      ("mi_pair", pair["mi_bits"]), ("synergy_bits", syn),
                                      ("bayes_pair", pair["bayes_accuracy"]), ("p_exclusion", pair["p_exclusion"]),
                                      ("exclusion_only_when_linked", new_excl),
                                      ("exclusion_examples", ev.exclusions(view, keys=keys) if new_excl else [])]))
    pairs.sort(key=lambda p: (-p["synergy_bits"], p["fields"]))
    return OrderedDict([("full", full), ("fields", fields), ("pairs", pairs)])
