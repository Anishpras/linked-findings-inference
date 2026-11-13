"""Report checklist, correct answers and the two renderers (PROTOCOL.md section 4).

The strict renderer reads only the view map it is given. It answers when the visible evidence
logically settles the item, including from partial evidence (e.g. one visible payment flag that
shows difficulty settles `budget_session` = yes), and abstains (returns None) otherwise. The
default-filling renderer applies the same rules and replaces every abstention by a default.
"""
from __future__ import annotations

from collections import OrderedDict

from . import spec

YES, NO, NONE = "yes", "no", "none"


def _yn(flag):
    return YES if flag else NO


# ---------------------------------------------------------------- correct answers (from the raw record)
def correct_answers(raw):
    f1, f2 = raw["r1.payment_flag"], raw["r2.payment_flag"]
    code, res = raw["r1.event_code"], raw["r2.resolution"]
    event = code != "none"
    etype, size = (code.split("_") if event else (None, None))
    a = OrderedDict()
    a["budget_session"] = _yn(f1 != "none" or f2 != "none")
    a["overdraft_guidance"] = _yn(f1 in ("overdraft_fee", "both") or f2 in ("overdraft_fee", "both"))
    a["essential_cost_review"] = _yn(raw["r1.essential_share"] == "over_70")
    a["expense_referral"] = etype if (event and res in ("instalment_plan", "outstanding")) else NONE
    a["hardship_review"] = _yn(size == "major" and res == "outstanding")
    a["plan_monitoring"] = _yn(res == "instalment_plan")
    a["goal_module"] = raw["r2.goal"]
    a["documents_request"] = spec.DOCUMENTS_REQUEST[raw["r2.document_status"]]
    a["contact_channel"] = raw["r1.contact_channel"]
    return a


def is_action_item(item, answer):
    """Action item: correct answer 'yes', or not 'none' for categorical items; contact_channel always."""
    return item == "contact_channel" or answer not in (NO, NONE)


# ---------------------------------------------------------------- evidence visible in a view
def _flag(x, stage):
    """('fine', value), ('coarse', value) or None if that stage's flag is not visible."""
    if "%s.payment_flag" % stage in x:
        return ("fine", x["%s.payment_flag" % stage])
    if "%s.payment_difficulty" % stage in x:
        return ("coarse", x["%s.payment_difficulty" % stage])
    return None


def _event(x):
    """(event_known_absent, type or None, size or None) from release 1, fine or coarse."""
    if "r1.event_code" in x:
        code = x["r1.event_code"]
        if code == "none":
            return True, None, None
        etype, size = code.split("_")
        return False, etype, size
    if "r1.event_type" in x:
        t = x["r1.event_type"]
        return (True, None, None) if t == "none" else (False, t, None)
    return False, None, None


def _resolution(x):
    """('fine', value), ('coarse', value) or None."""
    if "r2.resolution" in x:
        return ("fine", x["r2.resolution"])
    if "r2.resolution_coarse" in x:
        return ("coarse", x["r2.resolution_coarse"])
    return None


# ---------------------------------------------------------------- strict renderer (section 4.2)
def render_strict(x):
    """Item -> answer, or None to abstain. Reads only the supplied view map."""
    if any(k.startswith("e.") for k in x):  # condition E: answers read directly
        return OrderedDict((item, x.get("e." + item)) for item in spec.ITEMS)

    f1, f2 = _flag(x, "r1"), _flag(x, "r2")
    flags = [f for f in (f1, f2) if f is not None]
    no_event_r1, etype, size = _event(x)
    res = _resolution(x)
    res_val = res[1] if res else None          # fine and coarse share 'outstanding'/'not_applicable'
    no_event = no_event_r1 or res_val == "not_applicable"
    out = OrderedDict()

    # budget_session: yes if any visible flag shows difficulty; no only if both stages are
    # visible and neither does.
    difficulty = [(kind == "fine" and v != "none") or (kind == "coarse" and v == "any") for kind, v in flags]
    if any(difficulty):
        out["budget_session"] = YES
    elif f1 is not None and f2 is not None:
        out["budget_session"] = NO
    else:
        out["budget_session"] = None

    # overdraft_guidance: yes needs a fine overdraft_fee/both; no needs both stages visible and each
    # either fine none/late_utility or coarse none. Coarse 'any' cannot settle it.
    if any(kind == "fine" and v in ("overdraft_fee", "both") for kind, v in flags):
        out["overdraft_guidance"] = YES
    elif f1 is not None and f2 is not None and all(
            (kind == "fine" and v in ("none", "late_utility")) or (kind == "coarse" and v == "none")
            for kind, v in (f1, f2)):
        out["overdraft_guidance"] = NO
    else:
        out["overdraft_guidance"] = None

    # essential_cost_review: fine or coarse share; abstain if release 1 is missing.
    if "r1.essential_share" in x:
        out["essential_cost_review"] = _yn(x["r1.essential_share"] == "over_70")
    elif "r1.essential_share_coarse" in x:
        out["essential_cost_review"] = _yn(x["r1.essential_share_coarse"] == "over_70")
    else:
        out["essential_cost_review"] = None

    # expense_referral: none if no event or settled in full (fine); the type if the type is visible
    # and the resolution is instalment_plan/outstanding (fine) or coarse outstanding.
    if no_event or res == ("fine", "settled_in_full"):
        out["expense_referral"] = NONE
    elif etype is not None and res in (("fine", "instalment_plan"), ("fine", "outstanding"),
                                       ("coarse", "outstanding")):
        out["expense_referral"] = etype
    else:
        out["expense_referral"] = None

    # hardship_review: no if no event, an arranged/settled/instalment resolution, or a minor event;
    # yes if a major event is outstanding.
    if no_event or res_val in ("settled_in_full", "instalment_plan", "arranged") or size == "minor":
        out["hardship_review"] = NO
    elif size == "major" and res_val == "outstanding":
        out["hardship_review"] = YES
    else:
        out["hardship_review"] = None

    # plan_monitoring: yes on a fine instalment_plan; no on no event or a resolution that rules
    # an instalment plan out. Coarse 'arranged' cannot settle it.
    if res == ("fine", "instalment_plan"):
        out["plan_monitoring"] = YES
    elif no_event or res_val in ("settled_in_full", "outstanding", "not_applicable"):
        out["plan_monitoring"] = NO
    else:
        out["plan_monitoring"] = None

    out["goal_module"] = x.get("r2.goal")
    status = x.get("r2.document_status")
    out["documents_request"] = spec.DOCUMENTS_REQUEST[status] if status is not None else None
    out["contact_channel"] = x.get("r1.contact_channel")
    return out


# ---------------------------------------------------------------- default-filling renderer (section 4.3)
def render_default(x):
    return OrderedDict((item, spec.DEFAULT_FILL[item] if ans is None else ans)
                       for item, ans in render_strict(x).items())


def render(renderer, x):
    # Functions are looked up at call time, so a test can substitute render_strict by patching.
    if renderer == "strict":
        return render_strict(x)
    if renderer == "default_fill":
        return render_default(x)
    raise ValueError(renderer)


def outcome(correct, output):
    if output is None:
        return "omission"
    return "correct" if output == correct else "unsupported"
