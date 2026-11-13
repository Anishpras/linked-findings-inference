"""release_audit: leakage-versus-utility audits of multi-stage releases (standard library only).

Describe a pipeline declaratively (a hidden target, fields with conditional tables, declared
coarsenings, checklist items as rules, views), and the toolkit computes, exactly when the raw
space is small enough and by seeded Monte Carlo otherwise:
  * per view: Bayes accuracy, mutual information, naive Bayes's unlimited-data accuracy, logical
    exclusions, and utility by entailment;
  * a per-field information budget with cross-stage synergy;
  * a release-design search with its leakage-versus-utility Pareto frontier.
A real-data mode estimates the same tables from labelled records. See docs/tutorial.md.
"""
from __future__ import annotations

from collections import OrderedDict

from . import budget as budget_mod
from . import measures, model, search as search_mod

__version__ = "1.1.0"


def audit_spec(m, budget=True, search=True, workers=1, max_records=None, mc_samples=None, seed=None):
    joint = model.build_joint(m, max_records=max_records, mc_samples=mc_samples, seed=seed)
    ev = measures.Evaluator(joint)
    views = OrderedDict()
    for name, vd in m.views.items():
        keys = ev.keys(vd)
        views[name] = (ev.leakage(vd, keys=keys), ev.utility(vd, keys=keys, per_item=True), ev.exclusions(vd, keys=keys))
    out = OrderedDict([("joint", joint), ("evaluator", ev), ("views", views),
                       ("budget", budget_mod.budget(ev) if budget else None),
                       ("search", search_mod.run(ev, workers=workers) if search else None)])
    return out
