"""Direct-exposure scan (PROTOCOL.md section 5) on the exact bytes given to the attacker.

v1.1 (post-review correction, review 2.5): the scan is structural. Each line of the attacker's
stdin is parsed from those exact bytes, and an exposure is
  * a key, at any nesting level, exactly equal to a configured target field name
    (TARGET_FIELDS), or
  * a string value, at any nesting level (including the row id), exactly equal to a configured
    target label (TARGET_LABELS).
The training label (top-level "y" of a training row) is the declared supervision signal and is
excluded; everything else in a training row is scanned.

Scope, stated plainly. This detects only the literal target field and the literal label strings.
It does not detect case variants ("LOW"), embedded labels ("band=low", "h-low-123"), codes or
numbers standing for a band, the band's definition expressed another way, or inference through
correlated fields. A field that legitimately uses the same vocabulary (e.g. a "risk_level" of
"medium") would be flagged. "Zero exposures" therefore means "no field named or valued as the
band", not "no encoding of the band". v1.0 used substring matching on keys ("reserve", "band"),
which also flagged unrelated keys such as "broadband"; on this pilot's schema both rules give
identical counts.
"""
from __future__ import annotations

from collections import OrderedDict

from . import spec, views

TARGET_FIELDS = frozenset((spec.BAND_FIELD_R1, spec.BAND_FIELD_R2))
TARGET_LABELS = frozenset(spec.BANDS)
LABEL_KEY = "y"


def _hits(obj, top=True, is_training=False, fields=TARGET_FIELDS, labels=TARGET_LABELS):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if top and is_training and k == LABEL_KEY:
                continue
            if k in fields:
                hits.append("key:%s" % k)
            hits += _hits(v, False, is_training, fields, labels)
    elif isinstance(obj, list):
        for v in obj:
            hits += _hits(v, False, is_training, fields, labels)
    elif isinstance(obj, str) and obj in labels:
        hits.append("value:%s" % obj)
    return hits


def scan(stdin_bytes, fields=TARGET_FIELDS, labels=TARGET_LABELS):
    rows = views.parse_stdin(stdin_bytes)
    out = OrderedDict([("train_rows", 0), ("train_exposed", 0), ("scored_rows", 0), ("scored_exposed", 0),
                       ("exposed_scored_ids", [])])
    for _line, obj, is_training in rows:
        hit = bool(_hits(obj, True, is_training, fields, labels))
        if is_training:
            out["train_rows"] += 1
            out["train_exposed"] += hit
        else:
            out["scored_rows"] += 1
            out["scored_exposed"] += hit
            if hit:
                out["exposed_scored_ids"].append(obj.get("id"))
    return out
