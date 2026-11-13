"""Releases, the declared coarsening, views A-E and the exact attacker input bytes
(PROTOCOL.md sections 3.2-3.6 and 11).

A view is a flat map from field name to string value. The attacker receives one JSON line per
household: {"id": <opaque id>, "x": <view map>} for scored rows, plus "y": <band> for training
rows. The renderer receives the "x" map only. Serialisation is canonical (sorted keys, no
whitespace, ASCII) so equal inputs are equal bytes.
"""
from __future__ import annotations

import json
from collections import OrderedDict

from . import checklist, spec


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def view_key(x):
    """Hashable key of a view map (used by the oracle to look up P(view | band))."""
    return tuple(sorted(x.items()))


def release1(raw, band, band_field=False):
    r = OrderedDict((f, raw[f]) for f in spec.R1_FIELDS)
    if band_field:  # positive control only
        r[spec.BAND_FIELD_R1] = band
    return r


def release2(raw, band, band_field=False):
    r = OrderedDict((f, raw[f]) for f in spec.R2_FIELDS)
    if band_field:  # positive control only
        r[spec.BAND_FIELD_R2] = band
    return r


def coarsen(fine):
    """Declared coarsening (section 3.5): rename and map the four coarsened fields; keep the rest
    (including the positive control's band field) unchanged. No field is dropped."""
    out = OrderedDict()
    for field, value in fine.items():
        if field == "r1.essential_share":
            out[spec.COARSE_RENAME[field]] = spec.COARSE_SHARE[value]
        elif field == "r1.event_code":
            out[spec.COARSE_RENAME[field]] = value if value == "none" else value.split("_")[0]
        elif field in ("r1.payment_flag", "r2.payment_flag"):
            out[spec.COARSE_RENAME[field]] = spec.COARSE_FLAG[value]
        elif field == "r2.resolution":
            out[spec.COARSE_RENAME[field]] = spec.COARSE_RESOLUTION[value]
        else:
            out[field] = value
    return out


def make_view(view, raw, band, band_field=False):
    """The flat map for one view of one household, keys sorted."""
    if view == "A":
        m = release1(raw, band, band_field)
    elif view == "B":
        m = release2(raw, band, band_field)
    elif view == "C":
        m = OrderedDict(release1(raw, band, band_field))
        m.update(release2(raw, band, band_field))
    elif view == "D":
        fine = OrderedDict(release1(raw, band, band_field))
        fine.update(release2(raw, band, band_field))
        m = coarsen(fine)
    elif view == "E":
        if band_field:
            raise ValueError("view E is not defined for the positive control")
        m = OrderedDict(("e." + item, ans) for item, ans in checklist.correct_answers(raw).items())
    else:
        raise ValueError(view)
    return OrderedDict(sorted(m.items()))


def views_for(scenario_data):
    return spec.POSITIVE_CONTROL_VIEWS if scenario_data["positive_control"] else spec.VIEWS


def build_view_maps(scenario_data):
    """{view: {household id: x}} for every household."""
    pc = scenario_data["positive_control"]
    return OrderedDict((v, OrderedDict((h["id"], make_view(v, h["raw"], h["band"], pc))
                                       for h in scenario_data["households"]))
                       for v in views_for(scenario_data))


def scored_line(hid, x):
    """Exact bytes (without newline) of one unlabelled row, as in data/<scenario>/views/<view>.jsonl."""
    return canonical(OrderedDict([("id", hid), ("x", x)])).encode("ascii")


def training_line(hid, x, band):
    return canonical(OrderedDict([("id", hid), ("x", x), ("y", band)])).encode("ascii")


def attacker_stdin(households, view_map, split_of, scored_split, order_key):
    """Exact stdin bytes for one (scenario, view): training rows then scored rows, each block in
    seeded order (order_key), one JSON object per line.

    split_of maps household id -> split. The pipeline passes the per-household split from the
    generator; the split-per-view mutation test passes a different mapping per view.
    """
    train = sorted((h for h in households if split_of[h["id"]] == "train"), key=lambda h: (order_key[h["id"]], h["id"]))
    scored = sorted((h for h in households if split_of[h["id"]] == scored_split),
                    key=lambda h: (order_key[h["id"]], h["id"]))
    lines = [training_line(h["id"], view_map[h["id"]], h["band"]) for h in train]
    lines += [scored_line(h["id"], view_map[h["id"]]) for h in scored]
    return b"\n".join(lines) + b"\n"


def parse_stdin(stdin_bytes):
    """[(raw line bytes, parsed object, is_training)] for every line of an attacker input."""
    out = []
    for line in stdin_bytes.split(b"\n"):
        if not line:
            continue
        obj = json.loads(line.decode("ascii"))
        out.append((line, obj, "y" in obj))
    return out
