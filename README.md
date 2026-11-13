# Linked-findings inference pilot, and the `release_audit` toolkit

A fictional two-stage household-report workflow passes small sets of structured findings downstream. The pilot asks how much those findings reveal about a hidden reserve band (low, medium or high) that none of them states. It compares:

- one release (A, B);
- two linked releases (C);
- the linked releases after a declared coarsening (D);
- the report-checklist answers alone (E).

It also measures what report utility each design loses.

Notes on scope:

- **Synthetic.** All data are synthetic, and every probability is invented.
- **The specification.** `PROTOCOL.md` is the specification. Its "Revisions" section records every pre-freeze clarification and the v1.1 post-review revision.
- **Self-attested freeze.** The freeze is self-attested: `FREEZE.json` holds the hashes and git history holds the order of events. Do not call it pre-registered.
- **Requirements.** Python 3.9–3.14, standard library only, no network.

## The one command

| Command | What it does | Runtime |
|---|---|---|
| `python3 run_pilot.py` | Scores the test split into `results/`. Refuses to run unless the files match the latest `FREEZE.json` entry; exits 0 only if every check passes | about 95 s on a 12-core laptop |
| `python3 run_pilot.py --split dev` | Development run into `results_dev/` | about 65 s |
| `python3 run_pilot.py --check-reproducible` | Runs everything twice in temp directories, compares every output byte, and checks against the committed `results/output_manifest.json` | about 3–4 minutes |

`results/per_case_*.csv` and `data/` are large. They are not kept in git: the command regenerates them byte for byte, and `output_manifest.json` lists their SHA-256 hashes.

## 1. The frozen study (v1.0)

`results_v1.0/test/` holds the v1.0 test-split results exactly as committed at `edb8928`. Scenario `main` has 3,000 test households. The attacker was naive Bayes trained on 6,000 labels.

**Confirmatory results:**

| Result | Estimate [95% CI] | Outcome |
|---|---|---|
| H1a: linking beats release 1 (C − A) | +0.081 [0.062, 0.099] | supported |
| H1b: linking beats release 2 (C − B) | +0.068 [0.050, 0.085] | supported |
| H2a: coarsening loses accuracy (D − C) | −0.018 [−0.031, −0.006] | supported for the pre-specified seed |

**Exact population ceilings (Bayes accuracy):**

| View | Ceiling |
|---|---|
| baseline | 0.400 |
| A | 0.517 |
| B | 0.527 |
| C | 0.604 |
| D | 0.5755 |
| E | 0.565 |

**Logical exclusion.** A major expense settled in full rules out `low`. This happens for 5.75% of households, and only in C.

**Controls.** All controls passed.

The H1 and H2a directions are implied by the generator. The sizes are the result.

## 2. Post-review corrections (v1.1)

An independent review (2026-11-13) found no bug that changes a reported number, but several reporting problems. Everything is logged in `PROTOCOL.md` → Revisions v1.1. `results/revision_v1.1_delta.md` compares every v1.0 output cell by cell: **0 frozen numbers changed**.

**H2a is fragile** (`results/h2a_summary.md`):

- **Seed runs.** The criterion is met in 3 of 6 seed runs.
- **Across-seed mean** (post hoc): −0.014, t interval [−0.020, −0.009].
- **The study lead's power analysis was wrong.** It sized H2a from the Bayes gap (−0.029) instead of naive Bayes's best possible gap (−0.020), so realised power was about 0.56.
- **Attackers that can use the removed interaction always see the loss.** `nb_pair` and the sample oracle show D below C in 6 of 6 runs.

**H2b is descriptive.** It is fixed by construction. The exact expected shares of action items conveyed are A 0.521, B 0.458, D 0.805, C and E 1.

**Utility, split three ways** (`results/post_review_corrections.md`). The default-filling renderer answers with no evidence on 51% of items in A, 42% in B and 16% in D. Crediting its lucky guesses had inflated B's action items conveyed from 0.458 to 0.621. Only supported outputs now earn credit.

**S7 and S1 are reworded.** S7's ordering of point estimates is weak evidence. S1's log-loss gain (−0.030 bits) is a secondary measure, not a replacement test.

**Fixes.** None changed a frozen number:

- `nb_pair` falls back to the marginal factors when a joint value is unseen;
- the naive Bayes denominator is correct for optional fields;
- the exposure scan is structural, and its scope is documented;
- check 9 audits the shipped attacker only, and it is not a sandbox;
- band-bearing files are written only after every attacker process finishes;
- the run no longer dirties the repository.

## 3. Exploratory results (v1.1, added after the test results were seen)

**E versus D** (`results/exploratory_e_vs_d.md`):

- **Exact values.** The checklist answers alone (E, Bayes 0.565) leak less than the coarsening D (0.5755). The ordering holds in about 9 of 10 randomly perturbed generators.
- **The test split cannot resolve it.** The sample oracle's E − D interval excludes 0 in 1 of 6 seed runs.
- **One more checklist item reverses it.**
- The defensible claim, in the review's words: *releasing task outputs always dominates the linked fine release (same utility, 0.565 against 0.604 here) and still leaks (16.5 points over baseline, more than either single release); against a coarsening it is not ordered in general.*

**Controls** (`results/exploratory_controls.md`):

- **Label permutation.** With training labels shuffled, no attacker beats the baseline.
- **Id and row order only.** An attacker that sees only the opaque id and row order is at the baseline.
- **nb learning curve.** With 100 to 6,000 labels, linking helps even a 100-label attacker (C − A +0.061). Coarsening's effect is invisible at 100 labels (D − C +0.002). With few labels, the checklist answers are as useful to the attacker as the full linked release.

## 4. Audit your own pipeline: `release_audit`

```
python3 -m release_audit examples/household/spec.json --out /tmp/household
python3 -m release_audit examples/grocery/spec.json --out /tmp/grocery
python3 -m release_audit --data examples/grocery/records.csv --target young_children --spec examples/grocery/spec.json --out /tmp/data
```

**What you describe.** A declarative JSON spec: the hidden target, fields with conditional tables (zeros are hard constraints), declared coarsenings, checklist items as rules, and views.

**What the toolkit computes:**

- **Per view:** Bayes accuracy, mutual information, naive Bayes's unlimited-data accuracy and logical exclusions. These are exact when the raw space fits a limit, and seeded Monte Carlo otherwise, with the error stated.
- **Utility by entailment.**
- **A per-field information budget** with cross-stage synergy. On the household spec it finds the event-size × resolution interaction and its exclusion unaided.
- **A release-design search** with its leakage-versus-utility Pareto frontier.

**Real-data mode** estimates the same tables from labelled records:

- cross-validated naive Bayes, plus a pairwise logistic regression that can find interactions unaided;
- learning curves;
- plug-in MI with its bias caveat.

**Examples:**

- `examples/household/`: the pilot's generator. Its acceptance test reproduces the frozen oracle exactly, and its entailment utility equals the hand-written strict renderer on all 65,664 raw records.
- `examples/grocery/`: a different fictional pipeline. It has three stages, a binary hidden attribute and a latent field, plus a tiny `records.csv`.

**Docs:**

- `docs/tutorial.md`: with an honest time estimate.
- `docs/spec-reference.md`
- `docs/release-design-checklist.md`: each lesson is tied to the result that supports it. It also states the "release task outputs, not coarsened inputs" guidance with its conditions.

## Layout

| Path | Contents |
|---|---|
| `lfi/` | The pilot: spec, generator, views, checklist, isolated attacker, oracle, metrics, validation, reports, post-review outputs |
| `release_audit/` | The reusable toolkit |
| `examples/` | Example specs and their outputs |
| `docs/` | Toolkit documentation |
| `fixtures/` | Hand-checked households and hand-computed attacker known answers |
| `tests/` | Unit tests, mutation tests, toolkit tests and acceptance tests |
| `results/` | v1.1 test-split outputs |
| `results_dev/` | v1.1 dev-split outputs |
| `results_v1.0/` | The frozen v1.0 outputs, verbatim |
