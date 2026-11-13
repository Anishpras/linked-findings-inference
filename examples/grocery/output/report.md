# Release audit: grocery delivery (fictional, three stages)

A fictional grocery-delivery pipeline with three stages that each pass a few findings downstream: order (from the customer), picking (from the warehouse) and delivery (from the driver). The hidden attribute is whether the household has young children (binary). A latent field, household size, is never released but drives basket size and bulk items. One invented hard constraint spans stages: households without young children never ask for 'no bell' on an afternoon slot, so linking the order and delivery stages can rule a value out. Every probability is invented; nothing here describes a real service or real customers.

Exact enumeration over 2916 raw records with positive probability.

Hidden target `young_children` with values yes, no and prior 0.3000, 0.7000. A frequency baseline is right 0.7000 of the time; the prior entropy is 0.8813 bits.

## Views

Bayes accuracy is the best any attacker can do; nb_limit is naive Bayes with unlimited training data; MI is I(target; view). Utility is the expected share of action items the view entails.

| View | Bayes accuracy | MI (bits) | nb_limit | Excluding mass | Utility |
|---|---|---|---|---|---|
| order | 0.7040 | 0.0419 | 0.7040 | 0.0000 | 0.5923 |
| picking | 0.7602 | 0.1424 | 0.7602 | 0.0000 | 0.0829 |
| delivery | 0.7492 | 0.0733 | 0.7492 | 0.0000 | 0.2511 |
| linked | 0.8002 | 0.2564 | 0.7865 | 0.0330 | 1.0000 |
| coarsened | 0.7190 | 0.1225 | 0.7190 | 0.0000 | 0.4667 |
| items_only | 0.7692 | 0.1843 | 0.7522 | 0.0330 | 1.0000 |

### Logical exclusions (largest view values)

A view value that has probability zero under some target value rules that value out, whatever the attacker. These come from zeros in the spec's tables.

| View | Released values | Rules out | Mass |
|---|---|---|---|
| linked | order.basket_size=medium, order.delivery_window=afternoon, order.substitutions_allowed=yes, picking.bulk_items=some, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0020 |
| linked | order.basket_size=medium, order.delivery_window=afternoon, order.substitutions_allowed=yes, picking.bulk_items=many, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0017 |
| linked | order.basket_size=large, order.delivery_window=afternoon, order.substitutions_allowed=yes, picking.bulk_items=some, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0015 |
| linked | order.basket_size=large, order.delivery_window=afternoon, order.substitutions_allowed=yes, picking.bulk_items=many, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0014 |
| linked | order.basket_size=medium, order.delivery_window=afternoon, order.substitutions_allowed=no, picking.bulk_items=some, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0013 |
| linked | order.basket_size=small, order.delivery_window=afternoon, order.substitutions_allowed=yes, picking.bulk_items=some, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0012 |
| linked | order.basket_size=medium, order.delivery_window=afternoon, order.substitutions_allowed=no, picking.bulk_items=many, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0012 |
| linked | order.basket_size=large, order.delivery_window=afternoon, order.substitutions_allowed=no, picking.bulk_items=some, picking.out_of_stock=none, delivery.doorstep_instruction=no_bell, delivery.outcome=on_time | no | 0.0010 |
| items_only | large_vehicle=yes, substitution_notice=no, doorstep_note=no_bell, follow_up_call=no, slot_reminder=afternoon | no | 0.0119 |
| items_only | large_vehicle=no, substitution_notice=no, doorstep_note=no_bell, follow_up_call=no, slot_reminder=afternoon | no | 0.0089 |
| items_only | large_vehicle=yes, substitution_notice=yes, doorstep_note=no_bell, follow_up_call=no, slot_reminder=afternoon | no | 0.0032 |
| items_only | large_vehicle=yes, substitution_notice=no, doorstep_note=no_bell, follow_up_call=yes, slot_reminder=afternoon | no | 0.0030 |
| items_only | large_vehicle=no, substitution_notice=yes, doorstep_note=no_bell, follow_up_call=no, slot_reminder=afternoon | no | 0.0024 |
| items_only | large_vehicle=no, substitution_notice=no, doorstep_note=no_bell, follow_up_call=yes, slot_reminder=afternoon | no | 0.0022 |
| items_only | large_vehicle=yes, substitution_notice=yes, doorstep_note=no_bell, follow_up_call=yes, slot_reminder=afternoon | no | 0.0008 |
| items_only | large_vehicle=no, substitution_notice=yes, doorstep_note=no_bell, follow_up_call=yes, slot_reminder=afternoon | no | 0.0006 |

### Utility by item (share of action items conveyed)

| View | large_vehicle | substitution_notice | doorstep_note | follow_up_call | slot_reminder |
|---|---|---|---|---|---|
| order | 0.6668 | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| picking | 0.4983 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| delivery | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| linked | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| coarsened | 0.0000 | 1.0000 | 0.6081 | 1.0000 | 0.3850 |
| items_only | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Per-field information budget

Against the full linked view (every released field): MI 0.2564 bits, Bayes accuracy 0.8002.

| Field | Stage | MI alone | MI lost if dropped | Bayes lost if dropped | MI lost by each coarsening |
|---|---|---|---|---|---|
| picking.bulk_items | picking | 0.1424 | 0.1073 | 0.0462 | any 0.0294 |
| delivery.doorstep_instruction | delivery | 0.0733 | 0.0881 | 0.0355 | attended 0.0843 |
| order.basket_size | order | 0.0261 | 0.0103 | 0.0018 | two_level 0.0016 |
| order.delivery_window | order | 0.0164 | 0.0448 | 0.0119 | daypart 0.0392 |
| delivery.outcome | delivery | 0.0007 | 0.0000 | 0.0000 | - |
| picking.out_of_stock | picking | 0.0000 | 0.0000 | 0.0000 | any 0.0000 |
| order.substitutions_allowed | order | 0.0000 | 0.0000 | 0.0000 | - |

### Cross-stage synergy (top pairs)

Synergy = I(target; a, b) - I(target; a) - I(target; b). A large positive value is an interaction that only linking the stages reveals.

| Field a | Field b | MI of pair | Synergy (bits) | Exclusion only when linked |
|---|---|---|---|---|
| order.delivery_window | delivery.doorstep_instruction | 0.1274 | 0.0378 | yes |
| order.delivery_window | delivery.outcome | 0.0174 | 0.0003 | no |
| order.substitutions_allowed | delivery.outcome | 0.0007 | 0.0000 | no |
| picking.out_of_stock | delivery.outcome | 0.0007 | 0.0000 | no |
| order.basket_size | picking.out_of_stock | 0.0261 | 0.0000 | no |
| order.substitutions_allowed | delivery.doorstep_instruction | 0.0733 | 0.0000 | no |
| order.substitutions_allowed | picking.out_of_stock | 0.0000 | 0.0000 | no |
| order.delivery_window | picking.out_of_stock | 0.0164 | 0.0000 | no |

### Logical exclusions created only by linking

- order.delivery_window=afternoon, delivery.doorstep_instruction=no_bell rules out no (mass 0.0330)

## Release designs: leakage against utility

985 designs evaluated (exhaustive over 972 field-option combinations plus items designs). The frontier lists designs that no other design beats on both mutual information and utility.

| Design | MI (bits) | Bayes accuracy | Utility |
|---|---|---|---|
| order.substitutions_allowed, picking.out_of_stock | 0.0000 | 0.7000 | 0.1011 |
| order.substitutions_allowed, picking.out_of_stock, delivery.outcome | 0.0007 | 0.7000 | 0.1713 |
| order.delivery_window(daypart), order.substitutions_allowed, picking.out_of_stock | 0.0016 | 0.7000 | 0.2864 |
| order.delivery_window(daypart), order.substitutions_allowed, picking.out_of_stock, delivery.outcome | 0.0024 | 0.7000 | 0.3567 |
| order.delivery_window(daypart), order.substitutions_allowed, picking.out_of_stock, delivery.doorstep_instruction(attended) | 0.0060 | 0.7000 | 0.3964 |
| order.delivery_window(daypart), order.substitutions_allowed, picking.out_of_stock, delivery.doorstep_instruction(attended), delivery.outcome | 0.0065 | 0.7000 | 0.4667 |
| order.delivery_window, order.substitutions_allowed, picking.out_of_stock | 0.0164 | 0.7000 | 0.5825 |
| order.delivery_window, order.substitutions_allowed, picking.out_of_stock, delivery.outcome | 0.0174 | 0.7000 | 0.6527 |
| order.delivery_window, order.substitutions_allowed, picking.out_of_stock, delivery.doorstep_instruction(attended) | 0.0214 | 0.7000 | 0.6925 |
| order.delivery_window, order.substitutions_allowed, picking.out_of_stock, delivery.doorstep_instruction(attended), delivery.outcome | 0.0221 | 0.7000 | 0.7627 |
| order.basket_size, order.delivery_window, order.substitutions_allowed, picking.out_of_stock, delivery.outcome | 0.0429 | 0.7040 | 0.7637 |
| order.basket_size, order.delivery_window, order.substitutions_allowed, picking.out_of_stock, delivery.doorstep_instruction(attended) | 0.0468 | 0.7052 | 0.8034 |
| order.basket_size, order.delivery_window, order.substitutions_allowed, picking.out_of_stock, delivery.doorstep_instruction(attended), delivery.outcome | 0.0475 | 0.7052 | 0.8737 |
| order.basket_size, order.delivery_window, order.substitutions_allowed, picking.out_of_stock, delivery.doorstep_instruction, delivery.outcome | 0.1492 | 0.7540 | 0.9445 |
| items only | 0.1843 | 0.7692 | 1.0000 |

Declared views for comparison: order MI 0.0419, utility 0.5923; picking MI 0.1424, utility 0.0829; delivery MI 0.0733, utility 0.2511; linked MI 0.2564, utility 1.0000; coarsened MI 0.1225, utility 0.4667; items_only MI 0.1843, utility 1.0000.

## Caveats

- Every number is conditional on the spec's probabilities. Exact values are exact for the spec, not for the world.
- Bayes accuracy and MI bound any attacker that sees the view; a real attacker with finite data does worse (see nb_limit and, for data, the learning curves of real-data mode).
- Utility by entailment assumes the downstream task is exactly the declared checklist.
