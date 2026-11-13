"""Views: what a downstream system receives (docs/spec-reference.md, "views").

A view maps each raw record to a released value. Per field it keeps the value, maps it through a
declared coarsening or an inline total map, or drops it (fields not listed are dropped); it may
also include checklist items ("items": "all" or a list), i.e. release task outputs. Without a
"views" section the defaults are one view per stage, "linked" (every released field) and, if the
spec has items, "items_only".
"""
from __future__ import annotations

from collections import OrderedDict


class ViewDef:
    """parts: list of ("field", field index, output name, code map or None) and ("item", item index, name)."""

    def __init__(self, name, parts, description=""):
        self.name, self.parts, self.description = name, parts, description

    def field_parts(self):
        return [p for p in self.parts if p[0] == "field"]

    def item_parts(self):
        return [p for p in self.parts if p[0] == "item"]

    def label(self):
        return self.description or self.name


def field_option_map(model, fi, option):
    """Output values (as a list indexed by raw value index) for keep / coarsen:<name> / a dict map."""
    f = model.fields[fi]
    if option == "keep":
        return None
    if isinstance(option, str) and option.startswith("coarsen:"):
        cname = option.split(":", 1)[1]
        if cname not in f.coarsenings:
            from .model import SpecError
            raise SpecError("field %s has no coarsening %r" % (f.name, cname))
        mp = f.coarsenings[cname]
        return [mp[v] for v in f.values]
    if isinstance(option, dict):
        if set(option) != set(f.values):
            from .model import SpecError
            raise SpecError("map on %s must cover every value exactly" % f.name)
        return [str(option[v]) for v in f.values]
    from .model import SpecError
    raise SpecError("unknown option %r for field %s" % (option, f.name))


def make_view(model, name, field_options, items=(), description=""):
    """field_options: {field name: "keep" | "coarsen:<name>" | {value: output}}; items: item names."""
    parts = []
    for fname, opt in field_options.items():
        if opt == "drop":
            continue
        if fname not in model.field_index:
            from .model import SpecError
            raise SpecError("view %s: unknown field %r" % (name, fname))
        fi = model.field_index[fname]
        out_name = fname
        if isinstance(opt, dict) and ("coarsen" in opt or "map" in opt or "keep" in opt):
            out_name = opt.get("as", fname)
            opt = ("coarsen:%s" % opt["coarsen"]) if "coarsen" in opt else (opt["map"] if "map" in opt else "keep")
        parts.append(("field", fi, out_name, field_option_map(model, fi, opt)))
    names = [it.name for it in model.items]
    for it in items:
        if it not in names:
            from .model import SpecError
            raise SpecError("view %s: unknown item %r" % (name, it))
        parts.append(("item", names.index(it), it))
    return ViewDef(name, parts, description)


def compile_views(model, spec_views):
    out = OrderedDict()
    if spec_views:
        for name, vs in spec_views.items():
            items = vs.get("items", [])
            if items == "all":
                items = [it.name for it in model.items]
            out[name] = make_view(model, name, vs.get("fields", {}), items, vs.get("description", ""))
        return out
    for stage in model.stages():
        out["stage:%s" % stage] = make_view(model, "stage:%s" % stage,
                                            OrderedDict((f.name, "keep") for f in model.released_fields() if f.stage == stage))
    out["linked"] = make_view(model, "linked", OrderedDict((f.name, "keep") for f in model.released_fields()))
    if model.items:
        out["items_only"] = make_view(model, "items_only", {}, [it.name for it in model.items])
    return out
