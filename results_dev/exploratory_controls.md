# Exploratory controls (post-review, v1.1)

Label: **exploratory, post-review (v1.1)** (review section 4.6). Scenario `main`, scored split; intervals use main's bootstrap resamples. Each input went through the same isolated attacker once.

## Label-permutation control

Training labels shuffled among the training rows (seeded); features unchanged. Any accuracy above the frequency baseline would mean leakage from somewhere other than the features. Baseline accuracy 0.3810.

| View | Attacker | Accuracy [95% CI] | Minus baseline |
|---|---|---|---|
| A | baseline | 0.3810 [0.3500, 0.4100] | 0.0000 |
| A | nb | 0.3710 [0.3400, 0.4000] | -0.0100 |
| A | nb_pair | 0.3710 [0.3400, 0.4000] | -0.0100 |
| A | lookup | 0.3690 [0.3390, 0.3980] | -0.0120 |
| B | baseline | 0.3810 [0.3500, 0.4100] | 0.0000 |
| B | nb | 0.3550 [0.3260, 0.3840] | -0.0260 |
| B | nb_pair | 0.3550 [0.3260, 0.3840] | -0.0260 |
| B | lookup | 0.3610 [0.3310, 0.3900] | -0.0200 |
| C | baseline | 0.3810 [0.3500, 0.4100] | 0.0000 |
| C | nb | 0.3490 [0.3190, 0.3790] | -0.0320 |
| C | nb_pair | 0.3430 [0.3130, 0.3720] | -0.0380 |
| C | lookup | 0.3650 [0.3340, 0.3960] | -0.0160 |
| D | baseline | 0.3810 [0.3500, 0.4100] | 0.0000 |
| D | nb | 0.3600 [0.3290, 0.3890] | -0.0210 |
| D | nb_pair | 0.3620 [0.3310, 0.3910] | -0.0190 |
| D | lookup | 0.3510 [0.3210, 0.3810] | -0.0300 |
| E | baseline | 0.3810 [0.3500, 0.4100] | 0.0000 |
| E | nb | 0.3560 [0.3240, 0.3850] | -0.0250 |
| E | nb_pair | 0.3560 [0.3240, 0.3850] | -0.0250 |
| E | lookup | 0.3500 [0.3200, 0.3790] | -0.0310 |

Largest accuracy above baseline: 0.0000 (A, baseline).

## Id-and-row-order-only attacker

Features: two leading and the last character of the opaque id, and the row's position decile in the attacker's input. Labels are the true training labels.

| Attacker | Accuracy [95% CI] | Minus baseline |
|---|---|---|
| baseline | 0.3810 [0.3500, 0.4100] | 0.0000 |
| nb | 0.3580 [0.3300, 0.3880] | -0.0230 |
| nb_pair | 0.3580 [0.3300, 0.3880] | -0.0230 |
| lookup | 0.3580 [0.3300, 0.3880] | -0.0230 |

## nb learning curve

Nested training subsets (the first n rows in the attacker's seeded order). The 6,000-label point is the primary run. A weaker attacker is a fairer picture than the protocol's strong, upper-bound one.

| n_train | A nb [95% CI] | B nb [95% CI] | C nb [95% CI] | D nb [95% CI] | E nb [95% CI] |
|---|---|---|---|---|---|
| 100 | 0.4710 [0.4390, 0.5030] | 0.4710 [0.4400, 0.5030] | 0.4940 [0.4620, 0.5260] | 0.4970 [0.4680, 0.5280] | 0.4750 [0.4450, 0.5070] |
| 300 | 0.4780 [0.4470, 0.5090] | 0.4820 [0.4520, 0.5150] | 0.5230 [0.4920, 0.5560] | 0.5250 [0.4960, 0.5560] | 0.5040 [0.4750, 0.5350] |
| 1000 | 0.4960 [0.4660, 0.5270] | 0.5020 [0.4730, 0.5330] | 0.5660 [0.5370, 0.5960] | 0.5660 [0.5370, 0.5980] | 0.5260 [0.4960, 0.5580] |
| 3000 | 0.5070 [0.4770, 0.5380] | 0.5120 [0.4810, 0.5430] | 0.5650 [0.5360, 0.5960] | 0.5590 [0.5300, 0.5910] | 0.5320 [0.5030, 0.5630] |
| 6000 | 0.5140 [0.4840, 0.5440] | 0.5130 [0.4820, 0.5450] | 0.5570 [0.5270, 0.5880] | 0.5510 [0.5220, 0.5820] | 0.5350 [0.5050, 0.5670] |
| unlimited (exact) | 0.5172 | 0.5271 | 0.5953 | 0.5755 | 0.5582 |
| Bayes ceiling | 0.5172 | 0.5271 | 0.6042 | 0.5755 | 0.5650 |

nb gains by training size: 100: C-A 0.0230, D-C 0.0030; 300: C-A 0.0450, D-C 0.0020; 1000: C-A 0.0700, D-C 0.0000; 3000: C-A 0.0580, D-C -0.0060; 6000: C-A 0.0430, D-C -0.0060.
