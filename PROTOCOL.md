# Protocol: Can several minimal findings reveal a hidden attribute?

Version 1.0 (pre-specification draft, 2026-11-13). Fictional workflow, synthetic data, Python standard library only.

## 1. Question

In a fictional household-report workflow, raw records never reach the downstream system. Instead, two stages each release a small set of structured findings. How much can someone infer about a hidden **reserve band** (low, medium or high) from:

- one release;
- two releases linked to the same household;
- a coarser version of the two releases;
- the answers on the report checklist alone?

What useful report information does each design lose?

**H1 (linking).** Two linked releases support more accurate inference of the band than either release alone, although neither release contains the band.

**H2 (coarsening).** Coarsening the linked releases reduces that inference while keeping more report information than either single release.

Both are hypotheses. A null result or a utility loss counts as a result. For a Bayes-optimal attacker, H1's direction is guaranteed in information terms: the pair (A, B) carries at least as much information about the band as A or B does. So the pilot measures four things:

- the size of the gain under a documented generator;
- how much of the gain comes from cross-release interaction rather than additive evidence;
- whether learned attackers realise the gain;
- what coarsening and minimal outputs change, and at what utility cost.

## 2. Threat model

- **What the attacker sees.** Only the representation a downstream system would receive in a given condition.
- **Linkage.** In conditions C and D the attacker is told that both releases belong to the same household. Linkage itself is out of scope; estimating it would need a separate experiment.
- **Attacker's knowledge.** The attacker has 6,000 labelled training households from the same generator, in the same representation. This is a strong, upper-bound attacker for its model family. Real attackers may have fewer labels, or only public base rates.
- **What the attacker never sees:**
  - the band, except in the labelled positive control;
  - case IDs that encode attributes;
  - seeds, filenames and file order that correlates with labels;
  - any other condition's representation.
- **Process isolation.** The attacker runs as a separate process (`python3 -I`) in a fresh empty directory, with its input on stdin only.

## 3. Workflow and data

### 3.1 Household and band

Each synthetic household has a hidden band:

| Band | Meaning |
|---|---|
| `low` | liquid reserve under one month of essential costs |
| `medium` | one to three months |
| `high` | more than three months |

The band exists only in the scoring data. There is no free text and there are no shared templates: households are independent draws from the generator, so a template-grouped hold-out does not apply. Splits are by household.

### 3.2 Release 1 (intake findings)

| Field | Values |
|---|---|
| `r1.income_pattern` | `regular`, `irregular` |
| `r1.essential_share` | `under_50`, `50_70`, `over_70` (essential costs as a share of income) |
| `r1.event_code` | `none`, or `<type>_<size>`: type is `vehicle`, `medical` or `home`; size is `minor` or `major` (an unexpected expense reported at intake) |
| `r1.payment_flag` | `none`, `late_utility`, `overdraft_fee`, `both` |
| `r1.contact_channel` | `email`, `phone`, `post` |

### 3.3 Release 2 (follow-up findings)

| Field | Values |
|---|---|
| `r2.resolution` | `not_applicable` (no event), `settled_in_full`, `instalment_plan`, `outstanding` |
| `r2.payment_flag` | `none`, `late_utility`, `overdraft_fee`, `both` |
| `r2.goal` | `none`, `build_buffer`, `reduce_debt`, `major_purchase` |
| `r2.document_status` | `complete`, `missing_id`, `missing_income_proof` |

### 3.4 Generator (main scenario, dependence strength λ = 1)

**Prevalence:** π = low 0.40, medium 0.35, high 0.25.

**Conditional distributions** (probabilities in the listed value order):

| Field | Distribution |
|---|---|
| `income_pattern` | P(irregular \| band): low 0.50, medium 0.35, high 0.25 |
| `essential_share` | (under_50, 50_70, over_70): low (0.15, 0.40, 0.45); medium (0.30, 0.45, 0.25); high (0.50, 0.35, 0.15) |
| event | P(event) = 0.50, independent of band. Type uniform, independent. P(major \| event) = 0.40, independent. **`event_code` alone carries no band information by design.** |
| `r1.payment_flag` | (none, late_utility, overdraft_fee, both): low (0.45, 0.20, 0.20, 0.15); medium (0.65, 0.15, 0.12, 0.08); high (0.85, 0.07, 0.06, 0.02) |
| `contact_channel` | (0.60, 0.30, 0.10), independent |
| `resolution` given an event (settled_in_full, instalment_plan, outstanding) | **minor:** low (0.60, 0.25, 0.15); medium (0.75, 0.18, 0.07); high (0.85, 0.12, 0.03). **major:** low (**0.00**, 0.45, 0.55); medium (0.25, 0.55, 0.20); high (0.80, 0.17, 0.03) |
| `r2.payment_flag` | low (0.50, 0.18, 0.18, 0.14); medium (0.70, 0.13, 0.10, 0.07); high (0.88, 0.06, 0.05, 0.01) |
| `goal` | (none, build_buffer, reduce_debt, major_purchase): low (0.25, 0.35, 0.30, 0.10); medium (0.30, 0.25, 0.25, 0.20); high (0.35, 0.10, 0.15, 0.40) |
| `document_status` | (0.70, 0.15, 0.15), independent |

**Correlations the generator imposes, and what depends on them:**

- **Moderate additive signals.** Five fields carry moderate band signal: `income_pattern`, `essential_share`, both `payment_flag`s and `goal`. Each is plausible (irregular income, high essential costs and payment difficulty go with smaller reserves; saving goals differ by reserve), but the strengths are invented. These signals give additive gains to linking.
- **Cross-release interaction (the synergy).**
  - An event's size (release 1) and its resolution (release 2) interact.
  - A major expense settled in full is strong evidence of a high reserve. A minor expense settled in full is weak evidence.
  - Size alone carries no information. Resolution alone carries some, because it mixes minor and major events.
- **One hard constraint.** A low-reserve household cannot settle a major expense in full: P = 0, because a major expense exceeds one month of essential costs. The visible pair (`major`, `settled_in_full`) therefore *logically excludes* the low band. Only the linked view shows that pair. This is by construction, and the report says so.
- **Signal-free fields.** `contact_channel`, `document_status` and the event's type and occurrence carry no signal. They give the report utility without leakage.
- **Simplification.** The two payment flags are conditionally independent given the band.

**All conclusions are conditional on these numbers.** The sensitivity scenarios (section 3.6) show how results move when the dependence strength or the prevalence changes. No claim is made about real households.

### 3.5 Conditions (views) on the same test households

| Code | Attacker and renderer input |
|---|---|
| A | release 1 only |
| B | release 2 only |
| C | release 1 and release 2, linked as one record |
| D | release 1 and release 2 after the declared coarsening below |
| E (secondary, pre-specified) | the nine checklist answers only (section 4): the minimal output the report needs |

**Declared coarsening (condition D).** Fields are renamed so that granularity is explicit.

| Fine field | Coarse field | Mapping |
|---|---|---|
| `r1.essential_share` | `r1.essential_share_coarse` | `under_50` and `50_70` → `up_to_70`; `over_70` → `over_70` |
| `r1.event_code` | `r1.event_type` | size dropped: `medical_major` → `medical`; `none` → `none` |
| `r1.payment_flag`, `r2.payment_flag` | `r1.payment_difficulty`, `r2.payment_difficulty` | `none` → `none`; anything else → `any` |
| `r2.resolution` | `r2.resolution_coarse` | `settled_in_full` and `instalment_plan` → `arranged`; `outstanding` → `outstanding`; `not_applicable` → `not_applicable` |

`income_pattern`, `contact_channel`, `goal` and `document_status` are unchanged. D is coarsening only; dropping fields is condition E's job.

**Feature encoding.** Every condition is a flat map from field name to string value. The same encoding and fitting method is used across conditions.

### 3.6 Scenarios

Every scenario has its own households. They are reported separately and never pooled.

| Scenario | Role | Settings |
|---|---|---|
| `independence` | Control | λ = 0: every field is drawn from its band-independent marginal. Expected: every attacker is near the frequency baseline. |
| `dep_025`, `dep_050`, `dep_075` | Sensitivity: dependence strength | λ = 0.25, 0.50, 0.75 |
| `main` | Primary | λ = 1, π main |
| `prev_balanced` | Sensitivity: prevalence | λ = 1, π = (1/3, 1/3, 1/3) |
| `prev_skewed` | Sensitivity: prevalence | λ = 1, π = (0.70, 0.20, 0.10) |
| `positive_control` | Labelled positive control, excluded from main results | λ = 1, π main, plus a field `r1.reserve_band` and `r2.reserve_band` equal to the band. The field appears in both releases and coarsening keeps it. Conditions A–D only. |

**Dependence mixing.** For a field f with main distribution P(f | b):

P_λ(f | b) = (1 − λ) · M(f) + λ · P(f | b), where M(f) = Σ_b π_main(b) · P(f | b).

The resolution distribution is mixed per event size in the same way. Under the prevalence variants the distributions stay at λ = 1. Only the hard zero makes logical exclusion possible, so exclusion can occur only when λ = 1.

**Seed replicates (secondary).** The `main` scenario is regenerated with five further master seeds. This shows how much generator and training sampling moves the headline numbers. The bootstrap captures only test-sample uncertainty.

### 3.7 Sample sizes and splits

- **Households and split.** Each scenario (and each seed replicate) has 10,000 households. Each is assigned once, by seeded shuffle, to train (6,000), dev (1,000) or test (3,000). (Raised from 3,000 households before the freeze; see section 3.9.)
- **Views stay together.** Every view of a household, and both of its releases, stay in that household's split.
- **Dev split.** Used only for building and checking the code before the freeze. Hyperparameters are fixed in this protocol, not tuned.
- **Test split.** Scored once, after the freeze.
- **Hand-checked examples.** Six handwritten households in `fixtures/hand_examples.json` belong to no split.

### 3.8 Seeds and determinism

- **Master seed:** 20261113.
- **Sub-seeds:** each purpose (generate, split, ids, bootstrap, replicate k) gets its own seed: `int.from_bytes(sha256(f"{master}:{scenario}:{purpose}").digest()[:8], "big")`.
- **Sampling:** only `random.Random(seed).random()` with cumulative sums. Shuffles sort by `rng.random()` keys. This keeps output identical across Python 3.9–3.14.
- **Opaque IDs:** households get IDs from an HMAC of a secret derived from the seed. The attacker never sees the secret or the mapping. Test rows are shuffled before the attacker sees them.

### 3.9 Design-time power analysis and exact population ceilings (study lead, pre-freeze)

Added by the study lead before the freeze. It uses only the generator in this protocol and no data.

Enumerating the generator exactly gives the population Bayes accuracy of each view in `main`:

| View | Bayes accuracy |
|---|---|
| baseline | 0.400 |
| A | 0.517 |
| B | 0.527 |
| C | 0.604 |
| D | 0.5755 (corrected in v1.1; first printed as 0.576, see Revisions v1.1 A.7.8) |
| E | 0.565 |

The probability mass on which C logically excludes a band is 0.0575. For A, B, D and E it is 0.

- **Direction at the population level.** H1's and H2's directions are implied by the generator at the population level: C's ceiling exceeds A's and B's, and D's is below C's.
- **What the confirmatory tests ask.** They ask whether learned attackers, given finite labelled samples, realise these gaps on a 3,000-household test set.
- **Sizes.** The C−D population gap is only about 3 points. With 600 test households the paired 95% CI half-width is also about 3 points, so H2a would have been badly underpowered. The sizes were therefore raised from 3,000 to 10,000 households per scenario (train 6,000, dev 1,000, test 3,000), including the seed replicates.

## 4. Report checklist and renderers

### 4.1 Checklist

The checklist has nine items. The correct answers come from the full raw record and are fixed before any view is compared.

| Item | Values | Correct answer |
|---|---|---|
| `budget_session` | yes/no | yes iff either payment flag ≠ `none` |
| `overdraft_guidance` | yes/no | yes iff either payment flag ∈ {`overdraft_fee`, `both`} |
| `essential_cost_review` | yes/no | yes iff `essential_share` = `over_70` |
| `expense_referral` | `none`, `vehicle`, `medical`, `home` | the event type iff an event occurred and resolution ∈ {`instalment_plan`, `outstanding`}; otherwise `none` |
| `hardship_review` | yes/no | yes iff size = `major` and resolution = `outstanding` |
| `plan_monitoring` | yes/no | yes iff resolution = `instalment_plan` |
| `goal_module` | `none`, `build_buffer`, `reduce_debt`, `major_purchase` | the goal |
| `documents_request` | `none`, `id`, `income_proof` | from `document_status` |
| `contact_channel` | `email`, `phone`, `post` | the channel |

An **action item** is a (household, item) pair whose correct answer is `yes`, or not `none` for categorical items. `contact_channel` is always an action item.

### 4.2 Strict renderer (primary)

The strict renderer is deterministic. It reads only the supplied view and abstains when the evidence is unavailable. It uses partial evidence when that is logically enough:

| Item | Rule |
|---|---|
| `budget_session` | `yes` if any visible flag (fine, or coarse `any`) shows difficulty. `no` if both stages' flags are visible and show none. Otherwise abstain. |
| `overdraft_guidance` | `yes` if any visible fine flag ∈ {`overdraft_fee`, `both`}. `no` if both stages are visible and each is fine `none`/`late_utility` or coarse `none`. Otherwise abstain, which covers coarse `any` and a missing stage. |
| `essential_cost_review` | Answer from the fine or coarse share. Abstain if release 1 is missing. |
| `expense_referral` | `none` if `event_code`/`event_type` = `none`, or resolution is `not_applicable` or `settled_in_full`. The type if the type is visible and resolution ∈ {`instalment_plan`, `outstanding`, coarse `outstanding`}. Otherwise abstain, which covers coarse `arranged`, an unknown type or a missing stage. |
| `hardship_review` | `no` if there is no event, or resolution ∈ {`settled_in_full`, `instalment_plan`, `arranged`}, or size = `minor`. `yes` if size = `major` and resolution = `outstanding`. Otherwise abstain. |
| `plan_monitoring` | `yes` if resolution = `instalment_plan`. `no` if there is no event, or resolution ∈ {`settled_in_full`, `outstanding`, `not_applicable`, coarse `outstanding`}. Otherwise abstain, which covers coarse `arranged` and a missing release 2 when an event exists. |
| `goal_module`, `documents_request` | From release 2. Abstain if it is missing. |
| `contact_channel` | From release 1. Abstain if it is missing. |
| Condition E | Answers read directly. |

### 4.3 Default-filling renderer (secondary)

This renderer follows the same rules, but wherever the strict renderer abstains it emits a default:

- `no` for yes/no items;
- `none` for categorical items;
- `email` for `contact_channel`.

It shows how unsupported claims arise when a renderer does not abstain.

### 4.4 Utility outcomes per (household, item)

| Outcome | Definition |
|---|---|
| correct | output = correct answer |
| omission | abstained |
| unsupported | output given and ≠ correct answer |

**Reported per view, scenario and renderer:**

- action items conveyed correctly / total action items;
- all items correct / total items;
- omissions;
- unsupported outputs;
- per-item breakdown.

## 5. Attackers

All attackers use identical inputs (the training rows and labels for one view, and the test rows for the same view) and never abstain.

| Attacker | Method |
|---|---|
| `baseline` | Predicts the most frequent training band. Ties break in the order low, medium, high. |
| `nb` | Categorical naive Bayes over all visible fields: class prior with add-1 smoothing; per field, P(value \| band) with add-α smoothing (α = 1) over the values seen in training for that field, plus one slot for unseen values. A test value never seen in training for that field contributes no factor (it is skipped). The count of skipped values is reported. |
| `nb_pair` | Same as `nb`, except one schema-linked cross-release pair becomes one joint categorical feature. In C the pair is (`r1.event_code`, `r2.resolution`); in D it is (`r1.event_type`, `r2.resolution_coarse`). Identical to `nb` in A, B and E. The pair is "schema-linked" because the follow-up resolution refers to the intake event; anyone reading the schema knows they belong together. |
| `lookup` | Joint categorical lookup over the full visible tuple. If the tuple occurs at least m = 5 times in training, predict the argmax of the add-1-smoothed band counts for that tuple; otherwise fall back to `nb`. Reported: training coverage (the share of test households whose tuple has ≥ 5 training occurrences) and accuracy on covered and fallback households. |

**Tie-breaking:** argmax ties break in the order low, medium, high.

**Reference ceiling (not an attacker): `oracle`.** The exact Bayes posterior under the true generator for that scenario, P(b \| view) ∝ π(b) · P(view \| b).

- **Computation:** enumerate every raw household with its probability given b, map it to the view, and accumulate.
- **What it gives:**
  - the generator-limited ceiling for each view, both on the test sample and as the exact population value Σ_v max_b π(b) P(v \| b);
  - the logical-deduction counts.

**Logical deduction**, reported separately from statistical inference:

- a view value *excludes* band b if P(view \| b) = 0;
- it *determines* the band if exactly one band has non-zero probability.

The count of test households in each category is reported per view and scenario.

**Direct exposure**, distinct from inference through correlated features: a scan of every attacker input for any field whose key contains `reserve` or `band`, and any value equal to `low`, `medium` or `high`. Expected: test-set size in the positive control, 0 elsewhere.

## 6. Measures

These are computed on the test split, per scenario, view and attacker, with counts and denominators:

| Measure | Definition |
|---|---|
| Accuracy | correct / 3,000 |
| Macro recall | mean of per-band recall; bands absent from the test set are reported, not dropped silently |
| Confusion matrix | 3 × 3 |
| Mean probability on the true band | secondary; more sensitive than argmax accuracy |
| Paired changes | C − A, C − B, D − C, D − A, D − B, E − C and E − baseline, for accuracy and macro recall, with discordant counts (correct in one view only) |
| Utility | section 4.4 |
| The trade-off | per view, `nb` accuracy and macro recall against action items conveyed by the strict renderer |
| Exposures and deductions | section 5 |
| Information (S9, secondary) | from the oracle enumeration, per scenario and view (and the baseline): the exact population mutual information I(band; view) in bits, the exact Bayes log-loss H(band \| view) in bits, and the prior entropy H(band). Per attacker: the mean test log-loss in bits, −log2 p(true band), with probabilities clipped below at 1e-12, and the paired bootstrap CI of the log-loss difference for the same comparisons as accuracy |

**Intervals.**

- 95% percentile bootstrap: 2,000 resamples of test households, seeded.
- Paired differences resample households jointly across views.
- Uncertainty source: finite test sample only. The seed replicates show generator and training variability.
- No correction for multiple comparisons. Only the hypotheses in section 7 are confirmatory.

## 7. Pre-specified hypotheses and predictions

Everything below is pre-specified before the test set is scored.

**Confirmatory** (scenario `main`, attacker `nb`, test split):

- **H1a:** accuracy C − A > 0, with a 95% CI excluding 0.
- **H1b:** accuracy C − B > 0, with a 95% CI excluding 0.
- **H2a:** accuracy D − C < 0, with a 95% CI excluding 0.
- **H2b:** strict-renderer action items conveyed: D > max(A, B) and D < C. This is a descriptive comparison of counts.

**Secondary** (reported whatever the outcome):

| Code | Comparison | Prediction |
|---|---|---|
| S1 | `nb_pair` on C − `nb` on C | positive (interaction value) |
| S2 | E − baseline | positive: the checklist answers alone still leak |
| S3 | logical exclusions | > 0 in C; 0 in A, B and D (by construction) |
| S4 | D − A and D − B | **no directional prediction:** whether coarsened linked releases still leak more than one fine release is an open question |
| S5 | `lookup` coverage in C | low; `lookup` mostly falls back to `nb` there |
| S6 | default-filling renderer | unsupported outputs > 0 in A, B and D; 0 in C and E |
| S7 | `dep_*` scenarios | gains shrink as λ falls |
| S8 | `prev_*` scenarios | report accuracy and macro recall together; no further prediction |
| S9 | information measures (section 6) | reported; no directional prediction. Secondary only: they do not change the confirmatory hypotheses. They were added because accuracy barely moves when prevalence is skewed |

**Controls** (pass criteria):

- **Independence:** for every attacker and view, |accuracy − baseline accuracy| ≤ 0.05.
- **Positive control:** `nb` accuracy ≥ 0.99 in A–D, and the direct-exposure count = 3,000 in each.
- **All other scenarios:** direct exposures = 0.

## 8. Validation checks (run on every invocation)

| # | Check |
|---|---|
| 1 | The hand-checked examples reproduce their expected views, checklist answers and strict-renderer outputs. |
| 2 | Split isolation: train, dev and test households are disjoint; no test household or its ID appears in attacker training input; every view of a household is in its split. |
| 3 | Deterministic regeneration: regenerating each scenario from its seed reproduces byte-identical data. |
| 4 | The band has been removed: no attacker input outside the positive control contains the band field or band value strings. |
| 5 | Exact denominators: 3,000 test households per scenario, and 9 checklist items for each. |
| 6 | Controls behave as specified in section 7. |
| 7 | The generator matches its specification. Empirical frequencies in the training split are within sampling tolerance of the specified distributions; the check uses a generous bound such as 4 standard errors and reports any miss. |
| 8 | The oracle's exact population probabilities sum to 1 for each band. The hard zero holds in the data: no low-band household has (major, settled_in_full) when λ = 1. |
| 9 | The attacker process sees only stdin. Its working directory is a fresh empty temp directory, and its environment is minimal. |
| 10 | Reproducibility: `python3 run_pilot.py --check-reproducible` runs the whole pipeline twice in temp directories and compares every output byte. |

**Mutation tests** (in `tests/`) show that the checks have teeth. Each deliberately broken variant must be detected:

- a band leaked into release 2;
- the split shuffled per view rather than per household;
- the strict renderer guessing instead of abstaining;
- `nb` with the unseen-value rule removed.

## 9. Freeze

`python3 run_pilot.py --freeze` records SHA-256 hashes of these files in `FREEZE.json`, after the implementation passes its checks on the dev split and before the test split is scored:

- this protocol;
- the hand examples;
- every source file.

The full run refuses to score the test split unless the hashes match. Changes made after the freeze are logged below under "Revisions", with the reason, and re-frozen under a new label. The freeze is self-attested, not an external registration.

## 10. Outputs

**Command:** `python3 run_pilot.py` writes the following under `results/` and exits 0 only if every validation check passes.

**Data:**

- `data/<scenario>/households.jsonl`: the scoring data, with band and split;
- `data/<scenario>/views/<view>.jsonl`: exactly what the attacker and renderer receive.

**Per case:**

- `per_case_predictions.csv`: scenario, view, attacker, household, true band, prediction, probabilities;
- `per_case_report_checks.csv`: scenario, view, renderer, household, item, correct answer, output, outcome.

**Summaries:**

- `summary_inference.csv`, `summary_paired.csv`, `summary_utility.csv`;
- `confusion.csv`, `controls.csv`, `exposure_and_deduction.csv`, `lookup_coverage.csv`, `seed_replicates.csv`.

**Worked cases:** `worked_cases.md`. The selection rule is fixed in advance: in `main`/test, taking households in sorted opaque-ID order, show:

- the first household whose `nb` prediction is correct in C but wrong in both A and B;
- the first whose C prediction is wrong while A or B was right;
- the first with a logical exclusion in C;
- the first whose D rendering omits an item that C conveyed.

**Run metadata:** `run_info.json` records the Python version, platform, seeds, fixture version, file hashes and freeze status.

## 11. Worked example (hand example H1)

The hidden band is `medium`. The raw finding values are:

- release 1: income `regular`, share `50_70`, event `medical_major`, payment flag `overdraft_fee`, channel `phone`;
- release 2: resolution `instalment_plan`, payment flag `none`, goal `build_buffer`, documents `missing_income_proof`.

**Exact input to each condition**, in the shape of one JSONL row per household. Training rows also carry `"y"`; test rows do not.

```json
A: {"r1.contact_channel":"phone","r1.essential_share":"50_70","r1.event_code":"medical_major","r1.income_pattern":"regular","r1.payment_flag":"overdraft_fee"}
B: {"r2.document_status":"missing_income_proof","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"instalment_plan"}
C: {"r1.contact_channel":"phone","r1.essential_share":"50_70","r1.event_code":"medical_major","r1.income_pattern":"regular","r1.payment_flag":"overdraft_fee","r2.document_status":"missing_income_proof","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"instalment_plan"}
D: {"r1.contact_channel":"phone","r1.essential_share_coarse":"up_to_70","r1.event_type":"medical","r1.income_pattern":"regular","r1.payment_difficulty":"any","r2.document_status":"missing_income_proof","r2.goal":"build_buffer","r2.payment_difficulty":"none","r2.resolution_coarse":"arranged"}
E: {"e.budget_session":"yes","e.contact_channel":"phone","e.documents_request":"income_proof","e.essential_cost_review":"no","e.expense_referral":"medical","e.goal_module":"build_buffer","e.hardship_review":"no","e.overdraft_guidance":"yes","e.plan_monitoring":"yes"}
```

**Strict-renderer outputs** (✓ correct, – abstained):

| Item | A | B | C | D | E |
|---|---|---|---|---|---|
| budget_session | yes ✓ | – | yes ✓ | yes ✓ | yes ✓ |
| overdraft_guidance | yes ✓ | – | yes ✓ | – (coarse `any`) | yes ✓ |
| essential_cost_review | no ✓ | – | no ✓ | no ✓ | no ✓ |
| expense_referral | – (resolution unknown) | – (type unknown) | medical ✓ | – (`arranged`) | medical ✓ |
| hardship_review | – | no ✓ | no ✓ | no ✓ | no ✓ |
| plan_monitoring | – | yes ✓ | yes ✓ | – (`arranged`) | yes ✓ |
| goal_module | – | build_buffer ✓ | ✓ | ✓ | ✓ |
| documents_request | – | income_proof ✓ | ✓ | ✓ | ✓ |
| contact_channel | phone ✓ | – | ✓ | ✓ | ✓ |
| **Correct / 9** | 4 | 4 | 9 | 6 | 9 |

**Hand example H2 (logical exclusion).** Release 1 shows `home_major` and release 2 shows `settled_in_full`. Neither release alone rules anything out:

- a low-band household can report a major event;
- a low-band household can settle a minor one.

Linked, the pair excludes `low`. Coarsening removes the size, so D cannot exclude it either.

## Revisions

### Pre-freeze clarifications

All entries below were made before the freeze and before any test-split household was scored. Development used the dev split only.

**R1. Sample sizes and section 3.9 (study lead, design-time power analysis; no data used).**
- Households per scenario went from 3,000 to 10,000, split train 6,000 / dev 1,000 / test 3,000. This applies to every scenario, including the seed replicates.
- Updated accordingly: section 2 (labelled examples), section 3.7, section 6 (accuracy denominator), section 7 (positive-control exposure count 3,000) and section 8 (check 5).
- Section 3.9 was added with the study lead's exact population ceilings.
- **Oracle cross-check (implementer).** The implemented oracle reproduces the section 3.9 values to 3 decimals for baseline (0.400000), A (0.517181), B (0.527066), C (0.604169) and E (0.564987), and the exclusion mass exactly (0.0575).
- **D does not match.** The oracle gives 0.575466, which rounds to 0.575, not 0.576. The exact value is 920745939/1600000000 = 0.575466211875, in `population_oracle.csv`.
- An independent factorised computation, sharing no code with the oracle's enumeration or `lfi/views.py`, gives the same 0.575466. No alternative reading of the declared coarsening that was tried yields a value in [0.5755, 0.5765).
- The stated 0.576 is consistent with double rounding (0.575466 → 0.5755 → 0.576). Neither value was adjusted. Section 3.9 keeps the study lead's figures as given, and this discrepancy has been reported to the study lead.

**R2. Information measures, S9 (study lead).** Added to sections 6 and 7 before the freeze and before any test result existed. They are secondary and do not change the confirmatory hypotheses.
- Exact population I(band; view), H(band | view) and H(band) come from the oracle enumeration. The probabilities are exact rationals; log2 is taken in double precision and the terms are summed with `math.fsum`.
- Attacker mean test log-loss uses −log2 max(p, 1e-12), with paired bootstrap CIs for the accuracy comparisons.

**R3. Implementation clarifications (implementer).** None changes a hypothesis, prediction, measure or hyperparameter.
1. *Seeds.*
   - Sub-seed purposes are `generate`, `split`, `ids`, `attacker_order` and `bootstrap`.
   - Seed replicate k (1–5) uses master seed `subseed(20261113, "main", "replicate_k")`. Its own sub-seeds are derived from that master in the same way, so each replicate has its own 10,000 households, split and IDs.
2. *Sampling.*
   - Every household consumes exactly 12 `random()` draws in a fixed order: band, income, share, event occurrence, event type, event size, release-1 flag, channel, resolution, release-2 flag, goal, documents. Unused draws, such as type when there is no event, are ignored.
   - Inverse-CDF thresholds are exact Fraction partial sums converted to float, so a zero-probability value can never be drawn.
3. *Opaque IDs.* An ID is `"h"` plus the first 16 hex characters of HMAC-SHA256 of the generation index. The key is sha256 of a fixed prefix plus the 8-byte `ids` sub-seed.
4. *Attacker input format.*
   - The attacker receives JSON lines: `{"id": <opaque id>, "x": <view map>}` for scored rows, and the same plus `"y": <band>` for training rows. The section 11 flat map is the `"x"` object.
   - Training rows come first, then scored rows. Each block is in a seeded order (`attacker_order`) unrelated to labels.
   - Each line of `data/<scenario>/views/<view>.jsonl` is byte-identical to that household's scored line. The renderer receives only the `"x"` map.
5. *Isolation.*
   - The script is copied into its own fresh temporary directory. The working directory is a second, fresh and empty temporary directory.
   - The command is `<interpreter> -I <script>` with `env={}`.
   - The child still sees `LC_CTYPE` (set by the interpreter's own PEP 538 locale coercion) and, on macOS, `__CF_USER_TEXT_ENCODING` (injected by the OS). Check 9 allows exactly these two.
   - This is process-level isolation, not an OS sandbox. Check 9 therefore also inspects the attacker's source: it may import only json, sys and fractions, and use no file, argv or environment access.
6. *Attackers.*
   - Arithmetic is exact (Fraction), so argmax ties are genuine and broken low, medium, high.
   - `nb`'s unseen-value slot enters only the denominator. A field absent from training is also skipped.
   - `baseline` reports the add-1 smoothed class prior as its probabilities, which are used for mean p(true band) and log-loss.
   - `lookup`'s covered posterior is (n_tuple,band + 1) / (n_tuple + 3).
7. *Oracle.*
   - Each independent block of the raw record is rescaled to integer numerators over a common denominator, so P(view | band) is an exact rational and exclusion is an exact integer zero.
   - In the positive control, view keys that carry the band but have zero mass under every band, which only arise from the impossible (low, major, settled_in_full) record, are outside the support and are skipped.
8. *Bootstrap.*
   - Each resample is a multiplicity vector built from int(u·n) draws. The same vectors are used for every view and model, which makes the comparisons paired.
   - The percentile interval is the sorted values at 0-based positions 50 and 1949 (B = 2,000).
   - Macro recall is computed per resample over the bands present.
   - CIs are reported for accuracy, macro recall and log-loss. Mean p(true band) is a point estimate only.
   - All float sums use `math.fsum`, because Python 3.12 changed `sum()` of floats.
9. *Check 7 tolerance.* A cell fails if |p̂ − p| > 4 SE + 1/n, where the 1/n term is a continuity allowance for small cells. A specified zero requires a count of 0. The check covers the training split of every scenario and replicate.
10. *Check 10.*
    - Every invocation runs each attacker input twice, in independent isolated processes, and compares the outputs byte for byte.
    - The full two-run comparison of every output byte is `--check-reproducible`. It runs the whole pipeline twice in temporary directories and also compares against the committed `output_manifest.json`. Its result is written to `<results>/reproducibility_check.json`.
11. *Additional safeguards*, which also gate exit 0:
    - attacker known answers (`fixtures/attacker_known_answers.json`, hand-computed exact posteriors);
    - the strict renderer is never unsupported;
    - oracle information monotonicity (A, B, D and E cannot exceed C);
    - every scored view value lies in the oracle's support under its true band;
    - unit and mutation tests run as a check;
    - `--freeze` refuses unless the last dev run passed with identical files.
12. *Direct exposure.* Every attacker line is scanned. For training rows the label `"y"` is excluded and everything else is scanned. The protocol's count is the number of scored rows (households) exposed; training-row exposures are also reported.
13. *Operationalising secondary predictions.*
    - S3 is judged on scored-split counts.
    - S5's "low; mostly falls back" means coverage < 0.5.
    - S7's "gains shrink as λ falls" means the nb accuracy gains C−A and C−B are non-decreasing over λ = 0.25, 0.50, 0.75, 1 (dep_025, dep_050, dep_075, main). Independence (λ = 0) and the exact population gains are shown alongside.
    - "Worked case 4": "an item that C conveyed" means an action item that C's strict renderer output correctly and D's abstained on.
14. *Extra descriptive comparisons.* These are not hypotheses: nb_pair − nb on C and D, lookup − nb on C, and oracle − nb per view, with the same paired bootstrap. The seed replicates report point estimates only.
15. *Outputs.*
    - Additional files: `population_oracle.csv`, `generator_check.csv`, `hypotheses.csv`, `utility_by_item.csv`, `tradeoff.csv`, `seed_replicates_paired.csv`, `validation.json` and `output_manifest.json`. Per-case files cover the eight primary scenarios only, not the replicates.
    - Dev runs write to `results_dev/`.
    - The per-case CSVs and `data/` are too large for git (the test-run `per_case_report_checks.csv` exceeds 100 MB). They are regenerated byte-identically by the one command, and their SHA-256 hashes are committed in `output_manifest.json`.

### Revision v1.1 (reason: independent review)

**Context.**
- **What prompted it.** An independent senior review, dated 2026-11-13, examined the project at commit `edb8928`. The review is kept outside the repository in `linked-findings-inference-reports/fable_review_2026-11-13.md`. It found no bug that changes a reported number, and three must-fix reporting issues. The study lead accepted the review in full.
- **What stays.** The frozen v1.0 confirmatory results remain the pre-specified record. They are kept verbatim in `results_v1.0/test/` and `results_v1.0/dev/`, copied from commit `edb8928`, minus the stale `results_dev/reproducibility_check.json`.
- **How the new material is labelled.** Every output added or changed in v1.1 carries one of two labels:
  - **post-review correction (v1.1)**: a correction or relabelling of a v1.0 output;
  - **exploratory, post-review (v1.1)**: new, not pre-specified, and added after the test results were seen.
- **The test split was scored again.** The v1.1 run re-scores the test split. The data are identical (`data/` is byte-identical to v1.0), so this is the test split's second scored run, made by design. The reviewer also scored it three times while checking reproducibility.
- **Changed frozen numbers.** The pipeline writes `results/revision_v1.1_delta.md`, a cell-by-cell comparison with the v1.0 outputs. It is the authoritative list of every changed frozen number. None was expected: every fix below either never triggered in the v1.0 data or only adds columns, rows and labels.

**The power analysis was wrong, and the error was the study lead's.** Section 3.9 sized H2a from the Bayes-optimal C − D gap (−0.029). H2a is tested with `nb`, which cannot use the size × resolution interaction that the coarsening removes. `nb`'s best possible gap, with unlimited training data, is −0.020. Realised power was therefore about 0.6, not the level the sizing implied. The pre-specified seed met the criterion, but only 3 of the 6 seed runs do (`results/h2a_summary.md`). H2a stays the confirmatory result for the frozen seed, and it is not described as robust or replicated.

**A. Corrections and reporting**

1. **H2a across seeds (exploratory).** `results/h2a_seed_runs.csv` and `results/h2a_summary.md` report:
   - all six seed runs, with paired 95% CIs for accuracy and log-loss;
   - the count meeting the criterion;
   - the across-seed mean with a t interval on 5 df, labelled post hoc;
   - `nb_pair` and the sample oracle per seed;
   - the exact reference gaps;
   - approximate realised power.

   The seed replicates now get paired bootstraps for the keys these tables use; previously they had point estimates only. `population_oracle.csv` gains `nb_limit`, `nb_limit_exact` and `nb_pair_limit`: the exact infinite-training accuracy of `nb` and `nb_pair`, computed from the oracle tables, for every scenario and view.
2. **H2b** is relabelled **descriptive (deterministic)**. Its outcome is fixed by the generator and the renderer. The exact expected shares of action items conveyed (strict renderer, `main`) are A 0.5205, B 0.4582, C 1, D 0.8054, E 1.
3. **Utility, split three ways.** Every renderer output is classified as one of:
   - supported-correct (the view entails the answer);
   - unsupported-correct (a lucky default);
   - unsupported-wrong;
   - omission.

   Only supported outputs earn action-item credit. The v1.0 columns keep their protocol 4.4 meaning, and the v1.1 columns are added beside them (`summary_utility.csv`, `utility_by_item.csv`, `per_case_report_checks.csv`). Also new:
   - exact expectations in `utility_exact.csv`;
   - S6 recomputed (row `S6-corrected`);
   - the share of action items that are verbatim pass-throughs;
   - D's utility on the four items its coarsening affects (`post_review_corrections.md`).
4. **S7** now gives the exact population gains first, then the four `nb` estimates with CIs. The outcome text says that the frozen R3.13 rule's ordering of point estimates is weak evidence.
5. **S1.** The log-loss gain of `nb_pair` over `nb` is reported as a secondary measure (row `S1-logloss`, pre-specified under S9). It is not a replacement for the accuracy criterion.
6. **E versus D** is its own exploratory section (`exploratory_e_vs_d.md`, `e_vs_d.csv`). It reports:
   - exact values for every scenario;
   - per-seed paired results;
   - the review's section 4.4 table, computed exactly;
   - a random-generator robustness check, ported from the reviewer's script with attribution in `lfi/exploratory.py`. The port uses only `Random.random()`.

   It states the defensible claim exactly as the review words it.
7. **Fixes.** Each entry says whether any frozen number changes.
   1. **`nb_pair` fallback** (review 2.6). When a joint value was never seen in training, `nb_pair` falls back to the two marginal `nb` factors, each subject to the unseen-value rule, and counts the fallback.
      - Frozen numbers: none change, because no unseen joint value occurred in any v1.0 run (skip counts 0).
      - Fixture: `fixtures/attacker_known_answers.json` (v1.1.0) changes T2 and T3 accordingly. Those values were computed by hand.
   2. **`NaiveBayes` denominator** (review 2.6). It now counts only training rows that carry the field, which is correct for optional fields.
      - Frozen numbers: none change, because every row carries every field.
      - Fixture: a hand-computed optional-field dataset is added.
   3. **Exposure scan is structural** (review 2.5). It matches keys exactly against a configured target-field list and string values exactly against the target labels, with the scope documented in `lfi/exposure.py`. Frozen numbers: none change (the counts are identical).
   4. **Check 9 states its scope.** It audits the shipped attacker's source only, and it is not a sandbox. Its deny-list now includes `getattr`, `.open` and `.codecs`, which catches the reviewer's mutant. Frozen numbers: none change.
   5. **Band-bearing outputs are written last.** `data/` and `per_case_predictions.csv` are written to a private staging directory that no attacker process is told about. They are moved into place only after every attacker process has finished, and `data/` from an earlier run is deleted before any attacker runs. **This is not a sandbox:** a hostile attacker process could still search the disk. Frozen numbers: none change.
   6. **The single command no longer dirties the repository.** `run_pilot.py` removes only the files it writes, so the committed `reproducibility_check.json` survives a plain run. Frozen numbers: none change.
   7. **Stale file removed.** `results_dev/reproducibility_check.json`, from the Python 3.9 run, is deleted. Frozen numbers: none change.
   8. **Section 3.9 D value corrected to 0.5755.** The exact value is 0.575466. The first printing said 0.576, and R1 records the cross-check. Frozen numbers: none change; no output used the printed value.
8. **New exploratory controls** (`exploratory_controls.md`, `exploratory_controls.csv`, `learning_curve.csv`):
   - a label-permutation control inside `main`, with training labels shuffled;
   - an attacker that sees only the opaque id and row order;
   - an `nb` learning curve on `main` at 100, 300, 1,000, 3,000 and 6,000 training labels. A weaker attacker gives a fairer picture than the protocol's upper-bound one.

**B. Reusable toolkit.** `release_audit/` (`python3 -m release_audit`; see `docs/`) is new. It is not part of the pilot's inference.
- **Acceptance test.** `examples/household/spec.json` must reproduce the frozen oracle's Bayes accuracy (exactly), mutual information (within 1e-12) and `nb_limit` for views A–E in `main`. Its entailment utility must equal the frozen strict renderer on all 65,664 raw records.
- **Where its tests run.** They are in `tests/`, so they run inside check `x_unit_and_mutation_tests`.

**C. Freeze v1.1.**
- **What it covers.** The protocol, the fixtures, every source file, and now also `release_audit/*.py` and the example specs and records.
- **When.** It was recorded after a passing dev run and before the v1.1 test run.
- **Values fixed in advance.** Bootstrap seeds, the label-permutation seed (`subseed(master, "main", "label_permutation")`), the learning-curve sizes and the robustness seeds (`subseed(master, "e_vs_d_robustness", "setting_k")`).

### Revision v1.1.1 (reason: post-freeze bug in the toolkit's Monte Carlo reporting)

**Found after the v1.1 freeze and the v1.1 test run**, while checking the toolkit's Monte Carlo fallback end to end.

**The bug.** In Monte Carlo mode, `release_audit`:
- headlined the optimistic resubstitution accuracy and the upward-biased plug-in MI;
- reported "logical exclusions" and "exclusions only when linked" that were only unsampled cells.

**The fix.** In Monte Carlo mode:
- **Bayes accuracy** is now reported as a bracket: held-out plug-in classifier (usually pessimistic) and resubstitution (optimistic).
- **MI** headlines the Miller-Madow value.
- **Exclusions and determination** are not established (`None`), and none are reported.
- **The design search** uses the Miller-Madow MI and the held-out accuracy.

A test is added (`test_no_exclusions_claimed_from_samples`).

**Impact.**
- **Exact mode:** unchanged. The committed example outputs are byte-identical, as the committed-output tests confirm.
- **The pilot:** it does not use the toolkit, so no pilot number changes. `results/revision_v1.1_delta.md` is regenerated by the rerun.
- **Next steps:** re-frozen as v1.1.1, then rerun.
