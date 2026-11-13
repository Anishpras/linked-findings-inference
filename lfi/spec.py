"""Single source of truth: bands, fields, distributions, scenarios, views, coarsening,
checklist vocabulary, seeds, sizes and fixed hyperparameters (PROTOCOL.md sections 3-7).

Every probability is an exact Fraction written from the protocol's decimal strings, so the
oracle can use exact arithmetic and the hard zero is exactly zero. Other modules must take
their numbers from here rather than restating them.
"""
from collections import OrderedDict
from fractions import Fraction


def _p(*values):
    return tuple(Fraction(v) for v in values)


# ---------------------------------------------------------------- seeds and sizes (sections 3.7-3.8, 3.9)
MASTER_SEED = 20261113
N_HOUSEHOLDS = 10000                       # raised from 3,000 pre-freeze (PROTOCOL.md section 3.9)
SPLIT_SIZES = (("train", 6000), ("dev", 1000), ("test", 3000))
SCORED_SPLITS = ("dev", "test")
N_REPLICATES = 5
FIXTURE_VERSION = "1.1.0"

# ---------------------------------------------------------------- fixed hyperparameters (sections 5-7)
BANDS = ("low", "medium", "high")          # also the argmax tie-break order
ALPHA = 1                                  # nb add-alpha smoothing
LOOKUP_MIN_COUNT = 5                       # lookup coverage threshold m
N_BOOTSTRAP = 2000
CI_LEVEL = Fraction(95, 100)
LOGLOSS_CLIP = 1e-12                       # S9: probabilities clipped below at 1e-12
INDEPENDENCE_TOLERANCE = Fraction(5, 100)  # |accuracy - baseline accuracy| <= 0.05
POSITIVE_CONTROL_MIN_ACCURACY = Fraction(99, 100)
GENERATOR_CHECK_SE = 4                     # check 7: 4 standard errors (+ 1/n, see Revisions)

# ---------------------------------------------------------------- field vocabularies (sections 3.2-3.3)
INCOME = ("regular", "irregular")
SHARE = ("under_50", "50_70", "over_70")
EVENT_OCCURS = ("no", "yes")
EVENT_TYPES = ("vehicle", "medical", "home")
EVENT_SIZES = ("minor", "major")
FLAGS = ("none", "late_utility", "overdraft_fee", "both")
CHANNELS = ("email", "phone", "post")
RESOLUTIONS = ("settled_in_full", "instalment_plan", "outstanding")   # given an event
NO_EVENT_RESOLUTION = "not_applicable"
GOALS = ("none", "build_buffer", "reduce_debt", "major_purchase")
DOCUMENTS = ("complete", "missing_id", "missing_income_proof")

EVENT_CODES = ("none",) + tuple("%s_%s" % (t, s) for t in EVENT_TYPES for s in EVENT_SIZES)

R1_FIELDS = ("r1.income_pattern", "r1.essential_share", "r1.event_code", "r1.payment_flag",
             "r1.contact_channel")
R2_FIELDS = ("r2.resolution", "r2.payment_flag", "r2.goal", "r2.document_status")
RAW_FIELDS = R1_FIELDS + R2_FIELDS         # the raw record is exactly the linked view C

# ---------------------------------------------------------------- main generator, lambda = 1 (section 3.4)
PI_MAIN = OrderedDict(zip(BANDS, _p("0.40", "0.35", "0.25")))

# Band-dependent fields: generator field -> (value order, {band: probabilities}).
BAND_DEPENDENT = OrderedDict([
    ("r1.income_pattern", (INCOME, {          # P(irregular | band): 0.50, 0.35, 0.25
        "low": _p("0.50", "0.50"), "medium": _p("0.65", "0.35"), "high": _p("0.75", "0.25")})),
    ("r1.essential_share", (SHARE, {
        "low": _p("0.15", "0.40", "0.45"), "medium": _p("0.30", "0.45", "0.25"),
        "high": _p("0.50", "0.35", "0.15")})),
    ("r1.payment_flag", (FLAGS, {
        "low": _p("0.45", "0.20", "0.20", "0.15"), "medium": _p("0.65", "0.15", "0.12", "0.08"),
        "high": _p("0.85", "0.07", "0.06", "0.02")})),
    ("r2.payment_flag", (FLAGS, {
        "low": _p("0.50", "0.18", "0.18", "0.14"), "medium": _p("0.70", "0.13", "0.10", "0.07"),
        "high": _p("0.88", "0.06", "0.05", "0.01")})),
    ("r2.goal", (GOALS, {
        "low": _p("0.25", "0.35", "0.30", "0.10"), "medium": _p("0.30", "0.25", "0.25", "0.20"),
        "high": _p("0.35", "0.10", "0.15", "0.40")})),
])

# Resolution given an event: size -> {band: (settled_in_full, instalment_plan, outstanding)}.
# The (major, low, settled_in_full) zero is the protocol's one hard constraint.
RESOLUTION = OrderedDict([
    ("minor", {"low": _p("0.60", "0.25", "0.15"), "medium": _p("0.75", "0.18", "0.07"),
               "high": _p("0.85", "0.12", "0.03")}),
    ("major", {"low": _p("0.00", "0.45", "0.55"), "medium": _p("0.25", "0.55", "0.20"),
               "high": _p("0.80", "0.17", "0.03")}),
])

# Band-independent fields (identical in every scenario, unaffected by mixing).
BAND_INDEPENDENT = OrderedDict([
    ("event_occurs", (EVENT_OCCURS, _p("0.50", "0.50"))),
    ("event_type", (EVENT_TYPES, (Fraction(1, 3),) * 3)),
    ("event_size", (EVENT_SIZES, _p("0.60", "0.40"))),
    ("r1.contact_channel", (CHANNELS, _p("0.60", "0.30", "0.10"))),
    ("r2.document_status", (DOCUMENTS, _p("0.70", "0.15", "0.15"))),
])

# ---------------------------------------------------------------- scenarios (section 3.6)
SCENARIOS = OrderedDict([
    ("independence", {"lam": Fraction(0), "pi": PI_MAIN, "role": "control"}),
    ("dep_025", {"lam": Fraction(1, 4), "pi": PI_MAIN, "role": "sensitivity_dependence"}),
    ("dep_050", {"lam": Fraction(1, 2), "pi": PI_MAIN, "role": "sensitivity_dependence"}),
    ("dep_075", {"lam": Fraction(3, 4), "pi": PI_MAIN, "role": "sensitivity_dependence"}),
    ("main", {"lam": Fraction(1), "pi": PI_MAIN, "role": "primary"}),
    ("prev_balanced", {"lam": Fraction(1), "role": "sensitivity_prevalence",
                       "pi": OrderedDict(zip(BANDS, (Fraction(1, 3),) * 3))}),
    ("prev_skewed", {"lam": Fraction(1), "role": "sensitivity_prevalence",
                     "pi": OrderedDict(zip(BANDS, _p("0.70", "0.20", "0.10")))}),
    ("positive_control", {"lam": Fraction(1), "pi": PI_MAIN, "role": "positive_control",
                          "band_field": True}),
])
DEP_SEQUENCE = ("dep_025", "dep_050", "dep_075", "main")   # S7: lambda = 0.25, 0.50, 0.75, 1

# ---------------------------------------------------------------- views and coarsening (section 3.5)
VIEWS = ("A", "B", "C", "D", "E")
POSITIVE_CONTROL_VIEWS = ("A", "B", "C", "D")
BAND_FIELD_R1 = "r1.reserve_band"
BAND_FIELD_R2 = "r2.reserve_band"

COARSE_SHARE = {"under_50": "up_to_70", "50_70": "up_to_70", "over_70": "over_70"}
COARSE_FLAG = {"none": "none", "late_utility": "any", "overdraft_fee": "any", "both": "any"}
COARSE_RESOLUTION = {"settled_in_full": "arranged", "instalment_plan": "arranged",
                     "outstanding": "outstanding", "not_applicable": "not_applicable"}
COARSE_RENAME = {"r1.essential_share": "r1.essential_share_coarse", "r1.event_code": "r1.event_type",
                 "r1.payment_flag": "r1.payment_difficulty", "r2.payment_flag": "r2.payment_difficulty",
                 "r2.resolution": "r2.resolution_coarse"}

# Schema-linked cross-release pairs used by nb_pair (section 5). The attacker script keeps its own
# copy (it may import nothing from this package); validate.check_attacker_static compares them.
SCHEMA_PAIRS = (("r1.event_code", "r2.resolution"), ("r1.event_type", "r2.resolution_coarse"))

# ---------------------------------------------------------------- checklist (section 4)
ITEMS = ("budget_session", "overdraft_guidance", "essential_cost_review", "expense_referral",
         "hardship_review", "plan_monitoring", "goal_module", "documents_request", "contact_channel")
YES_NO_ITEMS = ("budget_session", "overdraft_guidance", "essential_cost_review", "hardship_review",
                "plan_monitoring")
DOCUMENTS_REQUEST = {"complete": "none", "missing_id": "id", "missing_income_proof": "income_proof"}
DEFAULT_FILL = {item: ("no" if item in YES_NO_ITEMS else "none") for item in ITEMS}
DEFAULT_FILL["contact_channel"] = "email"
RENDERERS = ("strict", "default_fill")

# ---------------------------------------------------------------- attackers and comparisons (sections 5-7)
ATTACKERS = ("baseline", "nb", "nb_pair", "lookup")
SCORED_MODELS = ATTACKERS + ("oracle",)    # oracle is a reference ceiling, not an attacker
PAIRED_VIEW_COMPARISONS = (("C", "A"), ("C", "B"), ("D", "C"), ("D", "A"), ("D", "B"), ("E", "C"))
# "E - baseline": attacker X on view E minus the baseline attacker on view E.
