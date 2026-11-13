# `release_audit` spec reference

A spec is one JSON file that describes a pipeline's releases as a small probabilistic model, the downstream task, and the releases you want to compare. Worked examples:

- `examples/household/spec.json`: two stages, three-valued target, one hard constraint across stages.
- `examples/grocery/spec.json`: three stages, binary target, a latent field.

## Top level

| Key | Required | Meaning |
|---|---|---|
| `name` | no | Shown in reports. |
| `description` | no | Shown in reports. |
| `target` | yes | The hidden attribute (see below). |
| `fields` | yes | The raw fields and their conditional tables. |
| `items` | no | The downstream task as checklist items. Utility is measured against these. |
| `views` | no | What each candidate release contains. Defaults are described below. |
| `search` | no | Options for the release-design search. |
| `limits` | no | `max_records` (enumeration limit, default 500,000), `mc_samples` (default 200,000). |

## `target`

```json
{"name": "reserve_band", "values": ["low", "medium", "high"], "prior": ["0.40", "0.35", "0.25"]}
```

The target must have at least two distinct values. `prior` is a list in value order, or an object `{value: probability}`, and must sum to exactly 1.

## Probabilities

Write probabilities as strings (`"0.45"`, `"1/3"`) or integers (`0`, `1`). They are read as exact fractions, so every row must sum to **exactly** 1. JSON floats are accepted and read as the exact decimal written, but strings are clearer. A probability of exactly 0 is a **hard constraint**: the tools report the logical exclusions it creates.

## `fields`

Each field is one finding that some stage can release.

| Key | Meaning |
|---|---|
| `name` | Unique; must differ from the target's name. Prefixing the stage (`r1.goal`) keeps reports readable. |
| `stage` | Which release the field belongs to. Fields in different stages are "cross-stage" for the synergy scan. |
| `latent` | `true` for a field that drives others but is never released, such as household size in the grocery example. A field with no `stage` is also latent. |
| `values` | Distinct strings. |
| `parents` | Names of other fields and/or the target. Optional. Cycles are rejected. |
| `p` | For a field without parents: one probability per value. |
| `cpt` | For a field with parents: rows keyed by the parents' values joined with `\|`, in `parents` order. |
| `coarsenings` | Named total maps from this field's values to coarser values, e.g. `{"coarse": {"under_50": "up_to_70", "50_70": "up_to_70", "over_70": "over_70"}}`. The search and the budget try each one. |

Each `cpt` row is a list of probabilities in value order, or an object `{value: probability}` in which missing values count as 0. Rules for keys:

- `*` in a key position matches any value.
- Rows apply in file order, so a later row overrides an earlier one.
- Every combination of parent values must end up covered.

Example: a resolution that depends on an event code and the target.

```json
{"name": "r2.resolution", "stage": "r2", "values": ["not_applicable", "settled_in_full", "instalment_plan", "outstanding"],
 "parents": ["r1.event_code", "reserve_band"],
 "cpt": {"none|*": ["1", "0", "0", "0"],
         "home_major|low": ["0", "0.00", "0.45", "0.55"], "...": "..."}}
```

The fields form a discrete Bayesian network whose root may be the target. **The numbers are assumptions.** Every result is exact *for the spec*, and only as good as the spec.

## `items` (the task)

An item is one output the downstream task needs. It is defined by ordered rules over raw fields, and the first rule whose `when` holds gives the value.

```json
{"name": "hardship_review", "no_action": ["no"],
 "rules": [{"when": {"all": [{"field": "r1.event_code", "in": ["vehicle_major", "medical_major", "home_major"]},
                             {"field": "r2.resolution", "eq": "outstanding"}]}, "value": "yes"},
           {"value": "no"}]}
```

**Conditions** (`when`):

| Form | Meaning |
|---|---|
| omitted or `true` | always holds |
| `{"field": f, "in": [...]}` | the field's value is in the list |
| `{"field": f, "not_in": [...]}` | the field's value is not in the list |
| `{"field": f, "eq": v}` | the field's value equals `v` |
| `{"field": f, "ne": v}` | the field's value differs from `v` |
| `{"all": [...]}` | every listed condition holds |
| `{"any": [...]}` | at least one listed condition holds |
| `{"not": c}` | condition `c` does not hold |

**Values:**

| Form | Meaning |
|---|---|
| `"literal"` | a fixed string |
| `{"field": f}` | copies the field's value verbatim |
| `{"field": f, "map": {...}}` | maps the field's value; the map must cover every value |

**Rules for items:**

- **Action items.** An item is an action item for a record unless its value is listed in `no_action`. An empty `no_action` means the item is always an action item, as with a contact channel.
- **The target is off limits.** Items may not read the target. Validation rejects an item that does.

**Utility by entailment.** For a view and a record, an item is *conveyed* if its value is the same for every positive-probability raw record that yields the same released value. Utility is the expected share of action items conveyed. This is what a renderer that answers only when the evidence settles the answer can output. On the household spec it equals the pilot's hand-written strict renderer on all 65,664 raw records, which is a test.

## `views` (candidate releases)

```json
"views": {
  "A": {"description": "release 1 only", "fields": {"r1.goal": "keep", "r1.share": "keep"}},
  "D": {"fields": {"r1.share": {"coarsen": "coarse", "as": "r1.share_coarse"},
                   "r2.res": {"map": {"a": "x", "b": "x", "c": "c"}}, "r2.goal": "keep"}},
  "E": {"items": "all"},
  "E+": {"items": ["goal_module"], "fields": {"r1.income_pattern": "keep"}}
}
```

**Per field:**

| Option | Meaning |
|---|---|
| `"keep"` | release the value as it is |
| `"drop"` (or not listed) | do not release the field |
| `{"coarsen": name}` | apply a declared coarsening |
| `{"map": {...}}` | apply an inline total map |

`"as"` renames the released field. Renaming affects reports only, not any measure.

**Items in a view.** `"items": "all"` or a list releases task outputs, alone or alongside fields.

**Defaults.** Without a `views` section you get one view per stage, `linked` (every released field) and `items_only` (if the spec has items).

## `search`

```json
"search": {"fields": {"r1.contact_channel": ["keep", "drop"]}, "max_designs": 5000, "items_plus_fields": 1}
```

| Key | Default | Meaning |
|---|---|---|
| `fields` | keep, each coarsening, drop | Options to try per released field. |
| `max_designs` | 5000 | Above this many field-option combinations, the search walks greedily from the full linked design and says the frontier is approximate. |
| `items_plus_fields` | 1 | The search adds "items only", plus items with up to this many fields in their keep or coarsened options. |

## What is computed

| Output | Exact mode | Monte Carlo mode (raw space above `max_records`) |
|---|---|---|
| Bayes accuracy | exact fraction | bracketed: resubstitution plug-in (optimistic) and held-out plug-in classifier with SE (usually pessimistic) |
| Mutual information (bits) | exact probabilities, double-precision logs | plug-in (biased upward) and Miller-Madow corrected |
| `nb_limit` | exact accuracy of naive Bayes with unlimited training data | plug-in estimate |
| Logical exclusions, determination | exact mass and the largest view values | not reported (a sampled zero is not a hard constraint) |
| Utility by entailment | exact | on the sampled support (may overstate) |

Per-field budget (exact mode, or estimated in Monte Carlo mode):

- MI alone;
- MI and Bayes accuracy lost when the field is dropped from the full linked view;
- MI lost by each coarsening;
- cross-stage pairwise synergy;
- exclusions created only by linking.

Outputs land in the `--out` directory: `report.md`, `views.csv`, `items.csv`, `budget_fields.csv`, `budget_pairs.csv`, `designs.csv` and `frontier.csv`.

## Real-data mode

```
python3 -m release_audit --data records.csv --target <column> [--spec spec.json] --out DIR
```

**Input.** A CSV of categorical columns; empty cells are missing.

**Views.** With `--spec`, the spec's views, coarsenings and items are applied to the records' columns (fields absent from the CSV are skipped). Without a spec, views are one per stage (a column `stage.name` belongs to `stage`) plus `linked`.

**Outputs per view:**

- plug-in Bayes accuracy (resubstitution, optimistic) and a cross-validated lookup;
- plug-in and Miller-Madow MI;
- k-fold naive Bayes and pairwise logistic regression (accuracy, SE, log-loss);
- learning curves;
- utility on the observed support.

**No logical exclusions.** Observed zeros are not hard constraints, so none are reported.

**Speed.** The pairwise logistic regression is pure Python and slow beyond a few thousand records.
