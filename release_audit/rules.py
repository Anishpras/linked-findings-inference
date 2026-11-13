"""Checklist items as declarative rules over raw fields (docs/spec-reference.md, "items").

An item is an ordered list of rules; the first rule whose condition holds gives the item's value.
Conditions:  true (or omitted) | {"field": f, "in": [..]} | {"field": f, "not_in": [..]}
             | {"field": f, "eq": v} | {"field": f, "ne": v} | {"all": [..]} | {"any": [..]} | {"not": c}
Values:      "literal" | {"field": f} (copy) | {"field": f, "map": {value: output, ...}} (total map)
An item is an action item for a record unless its value is listed in "no_action". Items may not
read the target. With a record that lacks a field the item needs (real-data mode), the value is
None (unknown).
"""
from __future__ import annotations


class _Missing(Exception):
    pass


def _cond(spec, model, where, deps):
    if spec is True or spec is None:
        return lambda r: True
    if not isinstance(spec, dict) or len(spec) == 0:
        raise _err(model, "%s: a condition must be true or an object" % where)
    if "all" in spec or "any" in spec:
        key = "all" if "all" in spec else "any"
        subs = [_cond(c, model, where, deps) for c in spec[key]]
        return (lambda r: all(s(r) for s in subs)) if key == "all" else (lambda r: any(s(r) for s in subs))
    if "not" in spec:
        sub = _cond(spec["not"], model, where, deps)
        return lambda r: not sub(r)
    f = spec.get("field")
    _check_field(f, model, where)
    deps.add(f)
    vals = model.fields[model.field_index[f]].values
    for op in ("in", "not_in"):
        if op in spec:
            bad = [v for v in spec[op] if v not in vals]
            if bad:
                raise _err(model, "%s: %s are not values of %s" % (where, bad, f))
            s = frozenset(spec[op])
            return (lambda r: _get(r, f) in s) if op == "in" else (lambda r: _get(r, f) not in s)
    for op in ("eq", "ne"):
        if op in spec:
            v = spec[op]
            if v not in vals:
                raise _err(model, "%s: %r is not a value of %s" % (where, v, f))
            return (lambda r: _get(r, f) == v) if op == "eq" else (lambda r: _get(r, f) != v)
    raise _err(model, "%s: condition on %s needs in, not_in, eq or ne" % (where, f))


def _value(spec, model, where, deps):
    if isinstance(spec, str):
        return lambda r: spec
    if isinstance(spec, dict) and "field" in spec:
        f = spec["field"]
        _check_field(f, model, where)
        deps.add(f)
        if "map" in spec:
            mp = spec["map"]
            vals = model.fields[model.field_index[f]].values
            if set(mp) != set(vals):
                raise _err(model, "%s: map on %s must cover every value exactly" % (where, f))
            return lambda r: mp[_get(r, f)]
        return lambda r: _get(r, f)
    raise _err(model, "%s: a value must be a string or {\"field\": ...}" % where)


def _get(r, f):
    v = r.get(f)
    if v is None or v == "":
        raise _Missing(f)
    return v


def _check_field(f, model, where):
    if f == model.target:
        raise _err(model, "%s: items may not read the target" % where)
    if f not in model.field_index:
        raise _err(model, "%s: unknown field %r" % (where, f))


def _err(model, msg):
    from .model import SpecError
    return SpecError(msg)


class Item:
    def __init__(self, name, rules, no_action, deps):
        self.name, self.rules, self.no_action, self.depends_on = name, rules, frozenset(no_action), frozenset(deps)

    @classmethod
    def from_spec(cls, spec, model):
        name = spec.get("name")
        if not name:
            from .model import SpecError
            raise SpecError("every item needs a name")
        deps = set()
        rules = []
        for i, r in enumerate(spec.get("rules", [])):
            where = "item %s rule %d" % (name, i + 1)
            rules.append((_cond(r.get("when", True), model, where, deps), _value(r.get("value"), model, where, deps)))
        if not rules:
            from .model import SpecError
            raise SpecError("item %s needs at least one rule" % name)
        return cls(name, rules, spec.get("no_action", []), deps)

    def evaluate(self, record):
        """Value for a record (dict field -> value), or None if a needed field is missing."""
        try:
            for cond, val in self.rules:
                if cond(record):
                    return val(record)
        except _Missing:
            return None
        from .model import SpecError
        raise SpecError("item %s: no rule matched record %s" % (self.name, record))

    def is_action(self, value):
        return value is not None and value not in self.no_action
