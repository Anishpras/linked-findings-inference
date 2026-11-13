# Worked cases (scenario `main`, test split)

Selection rule fixed in PROTOCOL.md section 10: households of the scored split taken in sorted opaque-ID order. Inputs below are the exact scored-row bytes each attacker process received (training rows have the same shape plus `"y"`). Posteriors are (p_low, p_medium, p_high); the predicted band is the argmax with ties broken low, medium, high. `oracle` is the exact Bayes posterior under the true generator (a reference ceiling, not an attacker).

## Case 1: the first household whose nb prediction is correct in C but wrong in both A and B

Household `h0081857659ed78cc`; true band **medium**.

```
A: {"id":"h0081857659ed78cc","x":{"r1.contact_channel":"email","r1.essential_share":"under_50","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"none"}}
B: {"id":"h0081857659ed78cc","x":{"r2.document_status":"complete","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
C: {"id":"h0081857659ed78cc","x":{"r1.contact_channel":"email","r1.essential_share":"under_50","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"none","r2.document_status":"complete","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
D: {"id":"h0081857659ed78cc","x":{"r1.contact_channel":"email","r1.essential_share_coarse":"up_to_70","r1.event_type":"none","r1.income_pattern":"regular","r1.payment_difficulty":"none","r2.document_status":"complete","r2.goal":"build_buffer","r2.payment_difficulty":"none","r2.resolution_coarse":"not_applicable"}}
E: {"id":"h0081857659ed78cc","x":{"e.budget_session":"no","e.contact_channel":"email","e.documents_request":"none","e.essential_cost_review":"no","e.expense_referral":"none","e.goal_module":"build_buffer","e.hardship_review":"no","e.overdraft_guidance":"no","e.plan_monitoring":"no"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) wrong | high (0.107/0.307/0.585) wrong | high (0.107/0.307/0.585) wrong | high (0.100/0.274/0.625) wrong | high (0.098/0.323/0.579) wrong |
| B | low (0.404/0.350/0.245) wrong | low (0.461/0.396/0.143) wrong | low (0.461/0.396/0.143) wrong | low (0.488/0.362/0.150) wrong | low (0.457/0.400/0.144) wrong |
| C | low (0.404/0.350/0.245) wrong | medium (0.151/0.428/0.421) correct | medium (0.153/0.436/0.411) correct | medium (0.318/0.409/0.273) correct | medium (0.138/0.453/0.409) correct |
| D | low (0.404/0.350/0.245) wrong | medium (0.226/0.468/0.306) correct | medium (0.228/0.474/0.298) correct | medium (0.278/0.426/0.296) correct | medium (0.217/0.485/0.298) correct |
| E | low (0.404/0.350/0.245) wrong | medium (0.148/0.442/0.410) correct | medium (0.148/0.442/0.410) correct | medium (0.275/0.458/0.267) correct | medium (0.238/0.468/0.294) correct |

Oracle logical exclusion in C: none.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session | no | - | - | no | no | no |
| overdraft_guidance | no | - | - | no | no | no |
| essential_cost_review | no | no | - | no | no | no |
| expense_referral | none | none | none | none | none | none |
| hardship_review | no | no | no | no | no | no |
| plan_monitoring | no | no | no | no | no | no |
| goal_module (action) | build_buffer | - | build_buffer | build_buffer | build_buffer | build_buffer |
| documents_request | none | - | none | none | none | none |
| contact_channel (action) | email | email | - | email | email | email |

## Case 2: the first household whose nb prediction in C is wrong while A or B was right

Household `h008da1576f370052`; true band **high**.

```
A: {"id":"h008da1576f370052","x":{"r1.contact_channel":"phone","r1.essential_share":"under_50","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"none"}}
B: {"id":"h008da1576f370052","x":{"r2.document_status":"complete","r2.goal":"none","r2.payment_flag":"late_utility","r2.resolution":"not_applicable"}}
C: {"id":"h008da1576f370052","x":{"r1.contact_channel":"phone","r1.essential_share":"under_50","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"none","r2.document_status":"complete","r2.goal":"none","r2.payment_flag":"late_utility","r2.resolution":"not_applicable"}}
D: {"id":"h008da1576f370052","x":{"r1.contact_channel":"phone","r1.essential_share_coarse":"up_to_70","r1.event_type":"none","r1.income_pattern":"regular","r1.payment_difficulty":"none","r2.document_status":"complete","r2.goal":"none","r2.payment_difficulty":"any","r2.resolution_coarse":"not_applicable"}}
E: {"id":"h008da1576f370052","x":{"e.budget_session":"yes","e.contact_channel":"phone","e.documents_request":"none","e.essential_cost_review":"no","e.expense_referral":"none","e.goal_module":"none","e.hardship_review":"no","e.overdraft_guidance":"no","e.plan_monitoring":"no"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) wrong | high (0.113/0.316/0.571) correct | high (0.113/0.316/0.571) correct | high (0.124/0.381/0.495) correct | high (0.098/0.323/0.579) correct |
| B | low (0.404/0.350/0.245) wrong | low (0.495/0.376/0.129) wrong | low (0.495/0.376/0.129) wrong | low (0.536/0.357/0.107) wrong | low (0.488/0.370/0.142) wrong |
| C | low (0.404/0.350/0.245) wrong | medium (0.178/0.438/0.385) wrong | medium (0.180/0.445/0.376) wrong | medium (0.178/0.438/0.385) wrong | medium (0.151/0.431/0.417) wrong |
| D | low (0.404/0.350/0.245) wrong | medium (0.308/0.445/0.247) wrong | medium (0.310/0.450/0.240) wrong | medium (0.200/0.467/0.333) wrong | medium (0.283/0.457/0.260) wrong |
| E | low (0.404/0.350/0.245) wrong | medium (0.241/0.451/0.307) wrong | medium (0.241/0.451/0.307) wrong | medium (0.243/0.595/0.162) wrong | medium (0.282/0.443/0.276) wrong |

Oracle logical exclusion in C: none.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session (action) | yes | - | yes | yes | yes | yes |
| overdraft_guidance | no | - | - | no | - | no |
| essential_cost_review | no | no | - | no | no | no |
| expense_referral | none | none | none | none | none | none |
| hardship_review | no | no | no | no | no | no |
| plan_monitoring | no | no | no | no | no | no |
| goal_module | none | - | none | none | none | none |
| documents_request | none | - | none | none | none | none |
| contact_channel (action) | phone | phone | - | phone | phone | phone |

## Case 3: the first household with a logical exclusion in C

Household `h00716deb0a4c7484`; true band **high**.

```
A: {"id":"h00716deb0a4c7484","x":{"r1.contact_channel":"post","r1.essential_share":"under_50","r1.event_code":"vehicle_major","r1.income_pattern":"regular","r1.payment_flag":"none"}}
B: {"id":"h00716deb0a4c7484","x":{"r2.document_status":"missing_income_proof","r2.goal":"none","r2.payment_flag":"none","r2.resolution":"settled_in_full"}}
C: {"id":"h00716deb0a4c7484","x":{"r1.contact_channel":"post","r1.essential_share":"under_50","r1.event_code":"vehicle_major","r1.income_pattern":"regular","r1.payment_flag":"none","r2.document_status":"missing_income_proof","r2.goal":"none","r2.payment_flag":"none","r2.resolution":"settled_in_full"}}
D: {"id":"h00716deb0a4c7484","x":{"r1.contact_channel":"post","r1.essential_share_coarse":"up_to_70","r1.event_type":"vehicle","r1.income_pattern":"regular","r1.payment_difficulty":"none","r2.document_status":"missing_income_proof","r2.goal":"none","r2.payment_difficulty":"none","r2.resolution_coarse":"arranged"}}
E: {"id":"h00716deb0a4c7484","x":{"e.budget_session":"no","e.contact_channel":"post","e.documents_request":"income_proof","e.essential_cost_review":"no","e.expense_referral":"none","e.goal_module":"none","e.hardship_review":"no","e.overdraft_guidance":"no","e.plan_monitoring":"no"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) wrong | high (0.107/0.354/0.539) correct | high (0.107/0.354/0.539) correct | high (0.107/0.354/0.539) correct | high (0.098/0.323/0.579) correct |
| B | low (0.404/0.350/0.245) wrong | high (0.171/0.316/0.514) correct | high (0.171/0.316/0.514) correct | high (0.161/0.339/0.500) correct | high (0.147/0.330/0.522) correct |
| C | low (0.404/0.350/0.245) wrong | high (0.030/0.214/0.756) correct | high (0.001/0.083/0.917) correct | high (0.030/0.214/0.756) correct | high (0.000/0.106/0.894) correct |
| D | low (0.404/0.350/0.245) wrong | high (0.083/0.336/0.581) correct | high (0.084/0.324/0.592) correct | high (0.083/0.336/0.581) correct | high (0.065/0.314/0.621) correct |
| E | low (0.404/0.350/0.245) wrong | high (0.059/0.260/0.681) correct | high (0.059/0.260/0.681) correct | medium (0.100/0.500/0.400) wrong | high (0.097/0.319/0.585) correct |

Oracle logical exclusion in C: low.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session | no | - | - | no | no | no |
| overdraft_guidance | no | - | - | no | no | no |
| essential_cost_review | no | no | - | no | no | no |
| expense_referral | none | - | none | none | - | none |
| hardship_review | no | - | no | no | no | no |
| plan_monitoring | no | - | no | no | - | no |
| goal_module | none | - | none | none | none | none |
| documents_request (action) | income_proof | - | income_proof | income_proof | income_proof | income_proof |
| contact_channel (action) | post | post | - | post | post | post |

## Case 4: the first household whose strict D rendering omits an action item that C conveyed

Household `h0078dfa4e1367c63`; true band **low**.

```
A: {"id":"h0078dfa4e1367c63","x":{"r1.contact_channel":"email","r1.essential_share":"over_70","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"both"}}
B: {"id":"h0078dfa4e1367c63","x":{"r2.document_status":"complete","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
C: {"id":"h0078dfa4e1367c63","x":{"r1.contact_channel":"email","r1.essential_share":"over_70","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"both","r2.document_status":"complete","r2.goal":"build_buffer","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
D: {"id":"h0078dfa4e1367c63","x":{"r1.contact_channel":"email","r1.essential_share_coarse":"over_70","r1.event_type":"none","r1.income_pattern":"regular","r1.payment_difficulty":"any","r2.document_status":"complete","r2.goal":"build_buffer","r2.payment_difficulty":"none","r2.resolution_coarse":"not_applicable"}}
E: {"id":"h0078dfa4e1367c63","x":{"e.budget_session":"yes","e.contact_channel":"email","e.documents_request":"none","e.essential_cost_review":"yes","e.expense_referral":"none","e.goal_module":"build_buffer","e.hardship_review":"no","e.overdraft_guidance":"yes","e.plan_monitoring":"no"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) correct | low (0.725/0.237/0.038) correct | low (0.725/0.237/0.038) correct | low (0.667/0.282/0.051) correct | low (0.725/0.244/0.030) correct |
| B | low (0.404/0.350/0.245) correct | low (0.461/0.396/0.143) correct | low (0.461/0.396/0.143) correct | low (0.488/0.362/0.150) correct | low (0.457/0.400/0.144) correct |
| C | low (0.404/0.350/0.245) correct | low (0.740/0.240/0.020) correct | low (0.740/0.241/0.019) correct | low (0.667/0.222/0.111) correct | low (0.736/0.248/0.015) correct |
| D | low (0.404/0.350/0.245) correct | low (0.702/0.263/0.035) correct | low (0.701/0.265/0.034) correct | low (0.600/0.320/0.080) correct | low (0.692/0.278/0.030) correct |
| E | low (0.404/0.350/0.245) correct | low (0.842/0.150/0.008) correct | low (0.842/0.150/0.008) correct | low (0.724/0.224/0.053) correct | low (0.795/0.189/0.015) correct |

Oracle logical exclusion in C: none.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session (action) | yes | yes | - | yes | yes | yes |
| overdraft_guidance (action) | yes | yes | - | yes | - | yes |
| essential_cost_review (action) | yes | yes | - | yes | yes | yes |
| expense_referral | none | none | none | none | none | none |
| hardship_review | no | no | no | no | no | no |
| plan_monitoring | no | no | no | no | no | no |
| goal_module (action) | build_buffer | - | build_buffer | build_buffer | build_buffer | build_buffer |
| documents_request | none | - | none | none | none | none |
| contact_channel (action) | email | email | - | email | email | email |

