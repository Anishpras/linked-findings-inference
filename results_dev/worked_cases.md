# Worked cases (scenario `main`, dev split)

Selection rule fixed in PROTOCOL.md section 10: households of the scored split taken in sorted opaque-ID order. Inputs below are the exact scored-row bytes each attacker process received (training rows have the same shape plus `"y"`). Posteriors are (p_low, p_medium, p_high); the predicted band is the argmax with ties broken low, medium, high. `oracle` is the exact Bayes posterior under the true generator (a reference ceiling, not an attacker).

## Case 1: the first household whose nb prediction is correct in C but wrong in both A and B

Household `h0edf7c0855b3c098`; true band **medium**.

```
A: {"id":"h0edf7c0855b3c098","x":{"r1.contact_channel":"email","r1.essential_share":"over_70","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"late_utility"}}
B: {"id":"h0edf7c0855b3c098","x":{"r2.document_status":"complete","r2.goal":"major_purchase","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
C: {"id":"h0edf7c0855b3c098","x":{"r1.contact_channel":"email","r1.essential_share":"over_70","r1.event_code":"none","r1.income_pattern":"regular","r1.payment_flag":"late_utility","r2.document_status":"complete","r2.goal":"major_purchase","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
D: {"id":"h0edf7c0855b3c098","x":{"r1.contact_channel":"email","r1.essential_share_coarse":"over_70","r1.event_type":"none","r1.income_pattern":"regular","r1.payment_difficulty":"any","r2.document_status":"complete","r2.goal":"major_purchase","r2.payment_difficulty":"none","r2.resolution_coarse":"not_applicable"}}
E: {"id":"h0edf7c0855b3c098","x":{"e.budget_session":"yes","e.contact_channel":"email","e.documents_request":"none","e.essential_cost_review":"yes","e.expense_referral":"none","e.goal_module":"major_purchase","e.hardship_review":"no","e.overdraft_guidance":"no","e.plan_monitoring":"no"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) wrong | low (0.640/0.290/0.070) wrong | low (0.640/0.290/0.070) wrong | low (0.700/0.200/0.100) wrong | low (0.632/0.299/0.069) wrong |
| B | low (0.404/0.350/0.245) wrong | high (0.121/0.306/0.573) wrong | high (0.121/0.306/0.573) wrong | high (0.131/0.301/0.567) wrong | high (0.127/0.312/0.561) wrong |
| C | low (0.404/0.350/0.245) wrong | medium (0.315/0.416/0.269) correct | medium (0.317/0.421/0.262) correct | medium (0.315/0.416/0.269) correct | medium (0.323/0.428/0.249) correct |
| D | low (0.404/0.350/0.245) wrong | medium (0.348/0.385/0.267) correct | medium (0.351/0.390/0.260) correct | low (0.375/0.250/0.375) wrong | medium (0.367/0.413/0.220) correct |
| E | low (0.404/0.350/0.245) wrong | medium (0.302/0.382/0.316) correct | medium (0.302/0.382/0.316) correct | low (0.462/0.308/0.231) wrong | medium (0.374/0.400/0.226) correct |

Oracle logical exclusion in C: none.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session (action) | yes | yes | - | yes | yes | yes |
| overdraft_guidance | no | - | - | no | - | no |
| essential_cost_review (action) | yes | yes | - | yes | yes | yes |
| expense_referral | none | none | none | none | none | none |
| hardship_review | no | no | no | no | no | no |
| plan_monitoring | no | no | no | no | no | no |
| goal_module (action) | major_purchase | - | major_purchase | major_purchase | major_purchase | major_purchase |
| documents_request | none | - | none | none | none | none |
| contact_channel (action) | email | email | - | email | email | email |

## Case 2: the first household whose nb prediction in C is wrong while A or B was right

Household `h0234153ae6fdc0d5`; true band **high**.

```
A: {"id":"h0234153ae6fdc0d5","x":{"r1.contact_channel":"email","r1.essential_share":"under_50","r1.event_code":"medical_major","r1.income_pattern":"regular","r1.payment_flag":"none"}}
B: {"id":"h0234153ae6fdc0d5","x":{"r2.document_status":"complete","r2.goal":"major_purchase","r2.payment_flag":"overdraft_fee","r2.resolution":"instalment_plan"}}
C: {"id":"h0234153ae6fdc0d5","x":{"r1.contact_channel":"email","r1.essential_share":"under_50","r1.event_code":"medical_major","r1.income_pattern":"regular","r1.payment_flag":"none","r2.document_status":"complete","r2.goal":"major_purchase","r2.payment_flag":"overdraft_fee","r2.resolution":"instalment_plan"}}
D: {"id":"h0234153ae6fdc0d5","x":{"r1.contact_channel":"email","r1.essential_share_coarse":"up_to_70","r1.event_type":"medical","r1.income_pattern":"regular","r1.payment_difficulty":"none","r2.document_status":"complete","r2.goal":"major_purchase","r2.payment_difficulty":"any","r2.resolution_coarse":"arranged"}}
E: {"id":"h0234153ae6fdc0d5","x":{"e.budget_session":"yes","e.contact_channel":"email","e.documents_request":"none","e.essential_cost_review":"no","e.expense_referral":"medical","e.goal_module":"major_purchase","e.hardship_review":"no","e.overdraft_guidance":"yes","e.plan_monitoring":"yes"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) wrong | high (0.118/0.365/0.517) correct | high (0.118/0.365/0.517) correct | medium (0.161/0.419/0.419) wrong | high (0.098/0.323/0.579) correct |
| B | low (0.404/0.350/0.245) wrong | low (0.451/0.416/0.133) wrong | low (0.451/0.416/0.133) wrong | medium (0.214/0.643/0.143) wrong | low (0.442/0.427/0.130) wrong |
| C | low (0.404/0.350/0.245) wrong | medium (0.156/0.513/0.331) wrong | medium (0.142/0.649/0.209) wrong | medium (0.156/0.513/0.331) wrong | medium (0.126/0.562/0.312) wrong |
| D | low (0.404/0.350/0.245) wrong | medium (0.128/0.457/0.415) wrong | medium (0.125/0.450/0.426) wrong | medium (0.111/0.556/0.333) wrong | high (0.123/0.422/0.455) correct |
| E | low (0.404/0.350/0.245) wrong | low (0.528/0.453/0.019) wrong | low (0.528/0.453/0.019) wrong | low (0.528/0.453/0.019) wrong | medium (0.354/0.506/0.141) wrong |

Oracle logical exclusion in C: none.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session (action) | yes | - | yes | yes | yes | yes |
| overdraft_guidance (action) | yes | - | yes | yes | - | yes |
| essential_cost_review | no | no | - | no | no | no |
| expense_referral (action) | medical | - | - | medical | - | medical |
| hardship_review | no | - | no | no | no | no |
| plan_monitoring (action) | yes | - | yes | yes | - | yes |
| goal_module (action) | major_purchase | - | major_purchase | major_purchase | major_purchase | major_purchase |
| documents_request | none | - | none | none | none | none |
| contact_channel (action) | email | email | - | email | email | email |

## Case 3: the first household with a logical exclusion in C

Household `h04e529f511b5a26a`; true band **high**.

```
A: {"id":"h04e529f511b5a26a","x":{"r1.contact_channel":"post","r1.essential_share":"under_50","r1.event_code":"vehicle_major","r1.income_pattern":"regular","r1.payment_flag":"late_utility"}}
B: {"id":"h04e529f511b5a26a","x":{"r2.document_status":"missing_income_proof","r2.goal":"none","r2.payment_flag":"none","r2.resolution":"settled_in_full"}}
C: {"id":"h04e529f511b5a26a","x":{"r1.contact_channel":"post","r1.essential_share":"under_50","r1.event_code":"vehicle_major","r1.income_pattern":"regular","r1.payment_flag":"late_utility","r2.document_status":"missing_income_proof","r2.goal":"none","r2.payment_flag":"none","r2.resolution":"settled_in_full"}}
D: {"id":"h04e529f511b5a26a","x":{"r1.contact_channel":"post","r1.essential_share_coarse":"up_to_70","r1.event_type":"vehicle","r1.income_pattern":"regular","r1.payment_difficulty":"any","r2.document_status":"missing_income_proof","r2.goal":"none","r2.payment_difficulty":"none","r2.resolution_coarse":"arranged"}}
E: {"id":"h04e529f511b5a26a","x":{"e.budget_session":"yes","e.contact_channel":"post","e.documents_request":"income_proof","e.essential_cost_review":"no","e.expense_referral":"none","e.goal_module":"none","e.hardship_review":"no","e.overdraft_guidance":"no","e.plan_monitoring":"no"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) wrong | medium (0.266/0.503/0.232) wrong | medium (0.266/0.503/0.232) wrong | medium (0.266/0.503/0.232) wrong | medium (0.263/0.449/0.288) wrong |
| B | low (0.404/0.350/0.245) wrong | high (0.171/0.316/0.514) correct | high (0.171/0.316/0.514) correct | high (0.161/0.339/0.500) correct | high (0.147/0.330/0.522) correct |
| C | low (0.404/0.350/0.245) wrong | high (0.107/0.432/0.462) correct | high (0.003/0.229/0.768) correct | high (0.107/0.432/0.462) correct | high (0.000/0.249/0.751) correct |
| D | low (0.404/0.350/0.245) wrong | medium (0.248/0.482/0.270) wrong | medium (0.253/0.470/0.277) wrong | medium (0.248/0.482/0.270) wrong | medium (0.223/0.471/0.306) wrong |
| E | low (0.404/0.350/0.245) wrong | medium (0.257/0.434/0.309) wrong | medium (0.257/0.434/0.309) wrong | medium (0.257/0.434/0.309) wrong | medium (0.282/0.443/0.276) wrong |

Oracle logical exclusion in C: low.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session (action) | yes | yes | - | yes | yes | yes |
| overdraft_guidance | no | - | - | no | - | no |
| essential_cost_review | no | no | - | no | no | no |
| expense_referral | none | - | none | none | - | none |
| hardship_review | no | - | no | no | no | no |
| plan_monitoring | no | - | no | no | - | no |
| goal_module | none | - | none | none | none | none |
| documents_request (action) | income_proof | - | income_proof | income_proof | income_proof | income_proof |
| contact_channel (action) | post | post | - | post | post | post |

## Case 4: the first household whose strict D rendering omits an action item that C conveyed

Household `h00302cdebd614e03`; true band **low**.

```
A: {"id":"h00302cdebd614e03","x":{"r1.contact_channel":"email","r1.essential_share":"50_70","r1.event_code":"none","r1.income_pattern":"irregular","r1.payment_flag":"overdraft_fee"}}
B: {"id":"h00302cdebd614e03","x":{"r2.document_status":"missing_id","r2.goal":"reduce_debt","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
C: {"id":"h00302cdebd614e03","x":{"r1.contact_channel":"email","r1.essential_share":"50_70","r1.event_code":"none","r1.income_pattern":"irregular","r1.payment_flag":"overdraft_fee","r2.document_status":"missing_id","r2.goal":"reduce_debt","r2.payment_flag":"none","r2.resolution":"not_applicable"}}
D: {"id":"h00302cdebd614e03","x":{"r1.contact_channel":"email","r1.essential_share_coarse":"up_to_70","r1.event_type":"none","r1.income_pattern":"irregular","r1.payment_difficulty":"any","r2.document_status":"missing_id","r2.goal":"reduce_debt","r2.payment_difficulty":"none","r2.resolution_coarse":"not_applicable"}}
E: {"id":"h00302cdebd614e03","x":{"e.budget_session":"yes","e.contact_channel":"email","e.documents_request":"id","e.essential_cost_review":"no","e.expense_referral":"none","e.goal_module":"reduce_debt","e.hardship_review":"no","e.overdraft_guidance":"yes","e.plan_monitoring":"no"}}
```

| View | baseline | nb | nb_pair | lookup | oracle |
|---|---|---|---|---|---|
| A | low (0.404/0.350/0.245) correct | low (0.638/0.293/0.069) correct | low (0.638/0.293/0.069) correct | low (0.674/0.261/0.065) correct | low (0.669/0.276/0.055) correct |
| B | low (0.404/0.350/0.245) correct | medium (0.352/0.413/0.236) wrong | medium (0.352/0.413/0.236) wrong | medium (0.357/0.393/0.250) wrong | medium (0.389/0.397/0.214) wrong |
| C | low (0.404/0.350/0.245) correct | low (0.574/0.357/0.069) correct | low (0.574/0.359/0.067) correct | low (0.574/0.357/0.069) correct | low (0.643/0.310/0.046) correct |
| D | low (0.404/0.350/0.245) correct | low (0.504/0.411/0.084) correct | low (0.505/0.414/0.082) correct | low (0.444/0.444/0.111) correct | low (0.576/0.357/0.067) correct |
| E | low (0.404/0.350/0.245) correct | low (0.577/0.371/0.052) correct | low (0.577/0.371/0.052) correct | low (0.542/0.333/0.125) correct | low (0.544/0.371/0.086) correct |

Oracle logical exclusion in C: none.

Strict renderer (`-` = abstained):

| Item | correct | A | B | C | D | E |
|---|---|---|---|---|---|---|
| budget_session (action) | yes | yes | - | yes | yes | yes |
| overdraft_guidance (action) | yes | yes | - | yes | - | yes |
| essential_cost_review | no | no | - | no | no | no |
| expense_referral | none | none | none | none | none | none |
| hardship_review | no | no | no | no | no | no |
| plan_monitoring | no | no | no | no | no | no |
| goal_module (action) | reduce_debt | - | reduce_debt | reduce_debt | reduce_debt | reduce_debt |
| documents_request (action) | id | - | id | id | id | id |
| contact_channel (action) | email | email | - | email | email | email |

