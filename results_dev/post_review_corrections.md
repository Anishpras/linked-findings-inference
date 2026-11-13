# Post-review corrections (v1.1)

Each item is labelled **post-review correction (v1.1)**. Frozen v1.0 numbers are unchanged unless `revision_v1.1_delta.md` says otherwise. Scenario `main`, scored split; exact values by full enumeration.

## H2b is descriptive, not a test

Which views convey more action items is fixed by the generator and the strict renderer, so H2b cannot fail by chance. It is relabelled **descriptive (deterministic)**.

| View | Observed share (scored split) | Exact expected share |
|---|---|---|
| A | 0.5177 (1887 / 3645) | 0.5205 |
| B | 0.4667 (1701 / 3645) | 0.4582 |
| C | 1.0000 (3645 / 3645) | 1.0000 |
| D | 0.8088 (2948 / 3645) | 0.8054 |
| E | 1.0000 (3645 / 3645) | 1.0000 |

## Utility split three ways

v1.0 counted a default that happened to be right as correct, and as an action item conveyed. v1.1 splits every output: **supported-correct** (the view entails the answer), **unsupported-correct** (a lucky default), **unsupported-wrong**, and omission. Only supported outputs earn action-item credit. Exact shares of all item outputs:

| View | Renderer | Supported-correct | Unsupported-correct (lucky) | Unsupported-wrong | Omission | Action items conveyed, v1.0 credit -> supported only (scored split) |
|---|---|---|---|---|---|---|
| A | strict | 0.4900 | 0.0000 | 0.0000 | 0.5100 | 0.5177 -> 0.5177 |
| A | default_fill | 0.4900 | 0.3140 | 0.1960 | 0.0000 | 0.5177 -> 0.5177 |
| B | strict | 0.5803 | 0.0000 | 0.0000 | 0.4197 | 0.4667 -> 0.4667 |
| B | default_fill | 0.5803 | 0.2649 | 0.1548 | 0.0000 | 0.6269 -> 0.4667 |
| C | strict | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |
| C | default_fill | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |
| D | strict | 0.8359 | 0.0000 | 0.0000 | 0.1641 | 0.8088 -> 0.8088 |
| D | default_fill | 0.8359 | 0.0845 | 0.0795 | 0.0000 | 0.8088 -> 0.8088 |
| E | strict | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |
| E | default_fill | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 -> 1.0000 |

**S6 recomputed.** Default-filling outputs made with no evidence (scored split): A 4592 (v1.0 counted 1758), B 3736 (v1.0 counted 1360), C 0 (v1.0 counted 0), D 1466 (v1.0 counted 697), E 0 (v1.0 counted 0). The predicted pattern of S6 (positive in A, B and D; zero in C and E) still holds. v1.0 understated unsupported claims by the lucky defaults.

## Pass-through items and D's utility

- **Verbatim pass-throughs.** `contact_channel`, `goal_module`, `documents_request` copy one field each. They make up 2.0075 of 3.6793 action items per household (**0.5456**).
- **D on the items coarsening touches.** The items D's strict renderer can fail to settle are `overdraft_guidance`, `expense_referral`, `hardship_review`, `plan_monitoring`. On those, D conveys 0.0871 of 0.8030 action items per household (**0.1085**). D's overall 0.8054 is mostly items that coarsening never touched.

## S7 wording

The population gains shrink as lambda falls by construction (mixing toward the marginal shrinks every gap). The four nb estimates have intervals, and their ordering is weak evidence; see the S7 rows of `hypotheses.csv`, which now give the exact population gains, then the four estimates with intervals.

## S1

S1 is not confirmed on accuracy. The log-loss gain of nb_pair over nb on C is reported as a **secondary measure** (pre-specified under S9), not as a replacement for the accuracy criterion; see row `S1-logloss` of `hypotheses.csv`.
