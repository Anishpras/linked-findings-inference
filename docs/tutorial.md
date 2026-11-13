# Tutorial: audit a multi-stage release with `release_audit`

**Goal.** You run a pipeline in which several stages each pass a few structured findings downstream. You want to know three things:

- how much the findings reveal about an attribute none of them states;
- what linking stages adds;
- which release keeps the downstream task working at the least leakage.

**Time, honestly:**

| Task | Time |
|---|---|
| Read this page and run the examples | about 30 minutes |
| First spec for a pipeline with 8 to 12 fields | roughly 3 to 6 hours |
| Re-run after an edit | seconds to about a minute |
| Real-data mode, a few hundred records | seconds |
| Real-data mode, tens of thousands of records | many minutes; mostly the pure-Python pairwise logistic regression |

Most of the time for a first spec goes on deciding the conditional probabilities and writing the item rules. Those numbers are assumptions, and the results are only as good as they are. A re-run takes seconds to about a minute when the raw space is a few hundred thousand records or fewer. The release-design search grows with the product of per-field options; the household example's 3,903 designs take about 30 seconds on 8 cores.

Standard library only (Python 3.9 or later). Run every command from the repository root.

## 1. Run the two examples

```
python3 -m release_audit examples/household/spec.json --out /tmp/household
python3 -m release_audit examples/grocery/spec.json --out /tmp/grocery
```

Open `report.md` in each output directory. The household example is the pilot's generator, and its numbers are the pilot's exact ceilings:

| View | What it is | Bayes accuracy |
|---|---|---|
| A | release 1 | 0.517 |
| B | release 2 | 0.527 |
| C | both, linked | 0.604 |
| D | linked, after the declared coarsening | 0.575 |
| E | checklist answers only | 0.565 |

A frequency baseline gets 0.400.

## 2. Read the report

**Views table.** One row per candidate release:

| Column | Meaning |
|---|---|
| Bayes accuracy | the best any attacker can do with that release |
| MI | mutual information with the hidden attribute, in bits |
| nb_limit | naive Bayes with unlimited training data; how far a simple attacker gets |
| Excluding mass | how often the release rules a value out outright |
| Utility | the share of the task's action items the release still settles |

**Logical exclusions.** Released values that are impossible under some target value. They come from zeros in your tables. In the household example, a major expense that is settled in full rules out `low`. Only the linked release shows that pair.

**Per-field information budget:**

- what each field reveals alone;
- what dropping it from the full linked release would remove;
- what each declared coarsening buys;
- **cross-stage synergy**: pairs that say more together than apart.

The household report finds the event-size × resolution interaction with no hint: event code is worth 0 bits alone, but the pair carries 0.040 bits of synergy and is the only pair that creates exclusions.

**Release designs.** Every combination of keep, coarsen or drop per field, plus "items only" and "items plus one field". The frontier lists the designs no other design beats on both leakage and utility. In the household example the pilot's coarsening D is dominated, and releasing the checklist answers ("items only") reaches full utility at lower leakage than linking.

## 3. Write a spec for your pipeline

Copy `examples/grocery/spec.json` and edit it. `docs/spec-reference.md` lists every key.

1. **Target.** The attribute that must not be inferable, with its prior.
2. **Fields.** One per finding that some stage releases:
   - `stage` says which release it is in;
   - `parents` and `cpt` say how it depends on the target and on other fields;
   - add `latent` fields for causes that are never released, such as household size in the grocery example;
   - put a `0` wherever a combination is impossible: those zeros drive the logical-exclusion results.
3. **Coarsenings.** The coarser versions of each field you would consider releasing.
4. **Items.** What the downstream task needs, as rules over raw fields. Mark the values that mean "nothing to do" in `no_action`.
5. **Views.** The releases you want compared, or leave `views` out to get one per stage, all linked, and items only.

Validation is strict. A row that does not sum to exactly 1, an unknown parent, a missing parent combination, or an item that reads the target is an error with a message that names the problem.

## 4. Check the spec against data, if you have it

If you have labelled records:

```
python3 -m release_audit --data records.csv --target young_children --spec examples/grocery/spec.json --out /tmp/grocery_data
```

`examples/grocery/records.csv` holds 400 records drawn from the spec. Make your own with:

```
python3 -m release_audit SPEC --sample N --sample-out FILE
```

Real-data mode estimates the same tables from the records, with honest uncertainty:

- **Cross-validated attackers.** Naive Bayes, and a pairwise logistic regression that can find an interaction it was not told about.
- **Learning curves.** A weaker attacker with fewer labels is often the realistic one.
- **Plug-in estimates.** The plug-in mutual information and Bayes accuracy are labelled as biased. On the grocery sample the plug-in says 0.91 for the linked view where the exact value is 0.80.

## 5. What the numbers do and do not mean

- **The spec is the ground truth here, not the world.** Exact means exact for the spec. Every probability you write is an assumption.
- **Bayes accuracy and mutual information are ceilings.** Real attackers with finite data do worse. Use nb_limit and the learning curves to see how much worse.
- **Utility assumes the task is exactly your checklist.** If the task changes, the frontier changes. One extra item in the household example makes "items only" leak more than coarsening D.
- **Linkage is assumed.** The tool asks what linked releases reveal, not how easy linking is. A stable key shared across stages is the linkage.

See `docs/release-design-checklist.md` for the design lessons, each tied to the result behind it.
