# Release audit: household (linked-findings pilot, scenario main)

Fictional two-stage household-report workflow from PROTOCOL.md sections 3-4 (scenario main, lambda = 1). Release r1 is intake findings, release r2 is follow-up findings; the hidden target is the reserve band. Every probability is invented. The acceptance test checks that this spec reproduces the frozen oracle values exactly.

Exact enumeration over 65664 raw records with positive probability.

Hidden target `reserve_band` with values low, medium, high and prior 0.4000, 0.3500, 0.2500. A frequency baseline is right 0.4000 of the time; the prior entropy is 1.5589 bits.

## Views

Bayes accuracy is the best any attacker can do; nb_limit is naive Bayes with unlimited training data; MI is I(target; view). Utility is the expected share of action items the view entails.

| View | Bayes accuracy | MI (bits) | nb_limit | Excluding mass | Utility |
|---|---|---|---|---|---|
| A | 0.5172 | 0.1878 | 0.5172 | 0.0000 | 0.5205 |
| B | 0.5271 | 0.2179 | 0.5271 | 0.0000 | 0.4582 |
| C | 0.6042 | 0.3889 | 0.5953 | 0.0575 | 1.0000 |
| D | 0.5755 | 0.3148 | 0.5755 | 0.0000 | 0.8054 |
| E | 0.5650 | 0.2896 | 0.5582 | 0.0000 | 1.0000 |

### Logical exclusions (largest view values)

A view value that has probability zero under some target value rules that value out, whatever the attacker. These come from zeros in the spec's tables.

| View | Released values | Rules out | Mass |
|---|---|---|---|
| C | r1.income_pattern=regular, r1.essential_share=under_50, r1.event_code=home_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=major_purchase, r2.document_status=complete | low | 0.0007 |
| C | r1.income_pattern=regular, r1.essential_share=under_50, r1.event_code=medical_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=major_purchase, r2.document_status=complete | low | 0.0007 |
| C | r1.income_pattern=regular, r1.essential_share=under_50, r1.event_code=vehicle_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=major_purchase, r2.document_status=complete | low | 0.0007 |
| C | r1.income_pattern=regular, r1.essential_share=under_50, r1.event_code=home_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=none, r2.document_status=complete | low | 0.0006 |
| C | r1.income_pattern=regular, r1.essential_share=under_50, r1.event_code=medical_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=none, r2.document_status=complete | low | 0.0006 |
| C | r1.income_pattern=regular, r1.essential_share=under_50, r1.event_code=vehicle_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=none, r2.document_status=complete | low | 0.0006 |
| C | r1.income_pattern=regular, r1.essential_share=50_70, r1.event_code=home_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=major_purchase, r2.document_status=complete | low | 0.0005 |
| C | r1.income_pattern=regular, r1.essential_share=50_70, r1.event_code=medical_major, r1.payment_flag=none, r1.contact_channel=email, r2.resolution=settled_in_full, r2.payment_flag=none, r2.goal=major_purchase, r2.document_status=complete | low | 0.0005 |

### Utility by item (share of action items conveyed)

| View | budget_session | overdraft_guidance | essential_cost_review | expense_referral | hardship_review | plan_monitoring | goal_module | documents_request | contact_channel |
|---|---|---|---|---|---|---|---|---|---|
| A | 0.6741 | 0.6140 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| B | 0.5942 | 0.5406 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| C | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| D | 1.0000 | 0.0000 | 1.0000 | 0.3820 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 1.0000 |
| E | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Per-field information budget

Against the full linked view (every released field): MI 0.3889 bits, Bayes accuracy 0.6042.

| Field | Stage | MI alone | MI lost if dropped | Bayes lost if dropped | MI lost by each coarsening |
|---|---|---|---|---|---|
| r2.goal | r2 | 0.0914 | 0.0587 | 0.0265 | - |
| r1.essential_share | r1 | 0.0865 | 0.0554 | 0.0254 | coarse 0.0205 |
| r1.payment_flag | r1 | 0.0850 | 0.0544 | 0.0229 | any 0.0025 |
| r2.payment_flag | r2 | 0.0846 | 0.0545 | 0.0224 | any 0.0041 |
| r2.resolution | r2 | 0.0629 | 0.0697 | 0.0270 | coarse 0.0412 |
| r1.income_pattern | r1 | 0.0318 | 0.0192 | 0.0083 | - |
| r1.event_code | r1 | 0.0000 | 0.0281 | 0.0088 | type 0.0281 |
| r2.document_status | r2 | 0.0000 | 0.0000 | 0.0000 | - |
| r1.contact_channel | r1 | 0.0000 | 0.0000 | 0.0000 | - |

### Cross-stage synergy (top pairs)

Synergy = I(target; a, b) - I(target; a) - I(target; b). A large positive value is an interaction that only linking the stages reveals.

| Field a | Field b | MI of pair | Synergy (bits) | Exclusion only when linked |
|---|---|---|---|---|
| r1.event_code | r2.resolution | 0.1029 | 0.0400 | yes |
| r1.contact_channel | r2.payment_flag | 0.0846 | 0.0000 | no |
| r1.contact_channel | r2.document_status | 0.0000 | 0.0000 | no |
| r1.contact_channel | r2.goal | 0.0914 | 0.0000 | no |
| r1.contact_channel | r2.resolution | 0.0629 | 0.0000 | no |
| r1.payment_flag | r2.document_status | 0.0850 | 0.0000 | no |
| r1.essential_share | r2.document_status | 0.0865 | 0.0000 | no |
| r1.income_pattern | r2.document_status | 0.0318 | 0.0000 | no |

### Logical exclusions created only by linking

- r1.event_code=home_major, r2.resolution=settled_in_full rules out low (mass 0.0192)
- r1.event_code=medical_major, r2.resolution=settled_in_full rules out low (mass 0.0192)
- r1.event_code=vehicle_major, r2.resolution=settled_in_full rules out low (mass 0.0192)

## Release designs: leakage against utility

3903 designs evaluated (exhaustive over 3888 field-option combinations plus items designs). The frontier lists designs that no other design beats on both mutual information and utility.

| Design | MI (bits) | Bayes accuracy | Utility |
|---|---|---|---|
| r1.contact_channel, r2.document_status | 0.0000 | 0.4000 | 0.3533 |
| r1.event_code(type), r1.contact_channel, r2.resolution(coarse), r2.document_status | 0.0370 | 0.4157 | 0.3770 |
| r1.event_code, r1.contact_channel, r2.resolution(coarse), r2.document_status | 0.0427 | 0.4200 | 0.3932 |
| r1.essential_share(coarse), r1.contact_channel, r2.document_status | 0.0538 | 0.4425 | 0.4362 |
| r1.event_code(type), r1.contact_channel, r2.resolution, r2.document_status | 0.0629 | 0.4318 | 0.4536 |
| r1.payment_flag(any), r1.contact_channel, r2.document_status | 0.0815 | 0.4475 | 0.4566 |
| r1.contact_channel, r2.payment_flag, r2.document_status | 0.0846 | 0.4450 | 0.4994 |
| r1.payment_flag, r1.contact_channel, r2.document_status | 0.0850 | 0.4475 | 0.5191 |
| r1.contact_channel, r2.goal, r2.document_status | 0.0914 | 0.4650 | 0.5456 |
| r1.event_code, r1.payment_flag, r1.contact_channel, r2.resolution(coarse), r2.document_status | 0.1237 | 0.4675 | 0.5590 |
| r1.event_code(type), r1.contact_channel, r2.resolution(coarse), r2.goal, r2.document_status | 0.1247 | 0.4788 | 0.5693 |
| r1.event_code, r1.contact_channel, r2.resolution(coarse), r2.goal, r2.document_status | 0.1298 | 0.4836 | 0.5855 |
| r1.essential_share(coarse), r1.payment_flag, r1.contact_channel, r2.document_status | 0.1333 | 0.4816 | 0.6020 |
| r1.essential_share(coarse), r1.contact_channel, r2.goal, r2.document_status | 0.1394 | 0.4868 | 0.6285 |
| r1.event_code(type), r1.contact_channel, r2.resolution, r2.goal, r2.document_status | 0.1475 | 0.4932 | 0.6459 |
| r1.payment_flag(any), r1.contact_channel, r2.goal, r2.document_status | 0.1636 | 0.5018 | 0.6489 |
| r1.contact_channel, r2.payment_flag, r2.goal, r2.document_status | 0.1667 | 0.4981 | 0.6917 |
| r1.payment_flag, r1.contact_channel, r2.goal, r2.document_status | 0.1668 | 0.5021 | 0.7114 |
| r1.essential_share(coarse), r1.event_code(type), r1.contact_channel, r2.resolution, r2.goal, r2.document_status | 0.1923 | 0.5178 | 0.7288 |
| r1.event_code(type), r1.payment_flag, r1.contact_channel, r2.resolution(coarse), r2.goal, r2.document_status | 0.1970 | 0.5194 | 0.7351 |
| r1.event_code, r1.payment_flag, r1.contact_channel, r2.resolution(coarse), r2.goal, r2.document_status | 0.2018 | 0.5207 | 0.7513 |
| r1.essential_share(coarse), r1.payment_flag, r1.contact_channel, r2.goal, r2.document_status | 0.2103 | 0.5335 | 0.7943 |
| r1.event_code(type), r1.payment_flag, r1.contact_channel, r2.resolution, r2.goal, r2.document_status | 0.2178 | 0.5289 | 0.8117 |
| r1.essential_share(coarse), r1.event_code(type), r1.payment_flag, r1.contact_channel, r2.resolution(coarse), r2.goal, r2.document_status | 0.2388 | 0.5458 | 0.8180 |
| r1.essential_share(coarse), r1.event_code, r1.payment_flag, r1.contact_channel, r2.resolution(coarse), r2.goal, r2.document_status | 0.2433 | 0.5475 | 0.8342 |
| r1.essential_share(coarse), r1.event_code(type), r1.payment_flag, r1.contact_channel, r2.resolution, r2.goal, r2.document_status | 0.2585 | 0.5535 | 0.8946 |
| r1.event_code(type), r1.payment_flag, r1.contact_channel, r2.resolution, r2.payment_flag, r2.goal, r2.document_status | 0.2818 | 0.5612 | 0.9009 |
| items only | 0.2896 | 0.5650 | 1.0000 |

Declared views for comparison: A MI 0.1878, utility 0.5205; B MI 0.2179, utility 0.4582; C MI 0.3889, utility 1.0000; D MI 0.3148, utility 0.8054; E MI 0.2896, utility 1.0000.

## Caveats

- Every number is conditional on the spec's probabilities. Exact values are exact for the spec, not for the world.
- Bayes accuracy and MI bound any attacker that sees the view; a real attacker with finite data does worse (see nb_limit and, for data, the learning curves of real-data mode).
- Utility by entailment assumes the downstream task is exactly the declared checklist.
