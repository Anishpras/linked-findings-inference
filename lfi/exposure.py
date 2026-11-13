"""Direct-exposure scan (PROTOCOL.md section 5) on the exact bytes given to the attacker.

Each line of the attacker's stdin is parsed from those bytes and every key and string value at
every nesting level is inspected: a key containing 'reserve' or 'band', or a value equal to
'low', 'medium' or 'high', is an exposure. The training label (top-level "y" of a training row)
is the declared supervision signal and is excluded; everything else in a training row is scanned.
Scope: direct exposure only, not inference through correlated fields.
"""
from __future__ import annotations

from collections import OrderedDict

from . import spec, views

KEY_MARKERS = ("reserve", "band")
BAND_VALUES = frozenset(spec.BANDS)


def _hits(obj, top=True, is_training=False):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if top and is_training and k == "y":
                continue
            if any(m in k for m in KEY_MARKERS):
                hits.append("key:%s" % k)
            hits += _hits(v, False, is_training)
    elif isinstance(obj, list):
        for v in obj:
            hits += _hits(v, False, is_training)
    elif isinstance(obj, str) and obj in BAND_VALUES:
        hits.append("value:%s" % obj)
    return hits


def scan(stdin_bytes):
    rows = views.parse_stdin(stdin_bytes)
    out = OrderedDict([("train_rows", 0), ("train_exposed", 0), ("scored_rows", 0), ("scored_exposed", 0),
                       ("exposed_scored_ids", [])])
    for _line, obj, is_training in rows:
        hit = bool(_hits(obj, True, is_training))
        if is_training:
            out["train_rows"] += 1
            out["train_exposed"] += hit
        else:
            out["scored_rows"] += 1
            out["scored_exposed"] += hit
            if hit:
                out["exposed_scored_ids"].append(obj.get("id"))
    return out
