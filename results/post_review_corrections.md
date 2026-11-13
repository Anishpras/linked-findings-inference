# Post-review corrections (v1.1)

Each item is labelled **post-review correction (v1.1)**. Frozen v1.0 numbers are unchanged unless `revision_v1.1_delta.md` says otherwise. Scenario `main`, scored split; exact values by full enumeration.

## H2b is descriptive, not a test

Which views convey more action items is fixed by the generator and the strict renderer, so H2b cannot fail by chance. It is relabelled **descriptive (deterministic)**.

| View | Observed share (scored split) | Exact expected share |
|---|---|---|
| A | 0.5187 (5705 / 10998) | 0.5205 |
| B | 0.4575 (5032 / 10998) | 0.4582 |
| C | 1.0000 (10998 / 10998) | 1.0000 |
| D | 0.8022 (8823 / 10998) | 0.8054 |
| E | 1.0000 (10998 / 10998) | 1.0000 |

## Utility split three ways

v1.0 counted a default that happened to be right as correct, and as an action item conveyed. v1.1 splits every output: **supported-correct** (the view entails the answer), **unsupported-correct** (a lucky default), **unsupported-wrong**, and omission. Only supported outputs earn action-item credit. Exact shares of all item outputs:

| View | Renderer | Supported-correct | Unsupported-correct (lucky) | Unsupported-wrong | Omission | Action items conveyed, v1.0 credit -> supported only (scored split) |
|---|---|---|---|---|---|---|
| A | strict | 0.4900 | 0.0000 | 0.0000 | 0.5100 | 0.5187 -> 0.5187 |
| A | default_fill | 0.4900 | 0.3140 | 0.1960 | 0.0000 | 0.5187 -> 0.5187 |
| B | strict | 0.5803 | 0.0000 | 0.0000 | 0.4197 | 0.4575 -> 0.4575 |
| B | default_fill | 0.5803 | 0.2649 | 0.1548 | 0.0000 | 0.6229 -> 0.4575 |
| C | strict | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |
| C | default_fill | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |
| D | strict | 0.8359 | 0.0000 | 0.0000 | 0.1641 | 0.8022 -> 0.8022 |
| D | default_fill | 0.8359 | 0.0845 | 0.0795 | 0.0000 | 0.8022 -> 0.8022 |
| E | strict | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |
| E | default_fill | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |

**S6 recomputed.** Default-filling outputs made with no evidence (scored split): A 13900 (v1.0 counted 5293), B 11349 (v1.0 counted 4147), C 0 (v1.0 counted 0), D 4445 (v1.0 counted 2175), E 0 (v1.0 counted 0). The predicted pattern of S6 (positive in A, B and D; zero in C and E) still holds. v1.0 understated unsupported claims by the lucky defaults.

## Pass-through items and D's utility

- **Verbatim pass-throughs.** `contact_channel`, `goal_module`, `documents_request` copy one field each. They make up 2.0075 of 3.6793 action items per household (**0.5456**).
- **D on the items coarsening touches.** The items D's strict renderer can fail to settle are `overdraft_guidance`, `expense_referral`, `hardship_review`, `plan_monitoring`. On those, D conveys 0.0871 of 0.8030 action items per household (**0.1085**). D's overall 0.8054 is mostly items that coarsening never touched.

## S7 wording

The population gains shrink as lambda falls by construction (mixing toward the marginal shrinks every gap). The four nb estimates have intervals, and their ordering is weak evidence; see the S7 rows of `hypotheses.csv`, which now give the exact population gains, then the four estimates with intervals.

## S1

S1 is not confirmed on accuracy. The log-loss gain of nb_pair over nb on C is reported as a **secondary measure** (pre-specified under S9), not as a replacement for the accuracy criterion; see row `S1-logloss` of `hypotheses.csv`.
