# Exploratory controls (post-review, v1.1)

Label: **exploratory, post-review (v1.1)** (review section 4.6). Scenario `main`, scored split; intervals use main's bootstrap resamples. Each input went through the same isolated attacker once.

## Label-permutation control

Training labels shuffled among the training rows (seeded); features unchanged. Any accuracy above the frequency baseline would mean leakage from somewhere other than the features. Baseline accuracy 0.3890.

| View | Attacker | Accuracy [95% CI] | Minus baseline |
|---|---|---|---|
| A | baseline | 0.3890 [0.3727, 0.4060] | 0.0000 |
| A | nb | 0.3823 [0.3657, 0.3993] | -0.0067 |
| A | nb_pair | 0.3823 [0.3657, 0.3993] | -0.0067 |
| A | lookup | 0.3530 [0.3357, 0.3707] | -0.0360 |
| B | baseline | 0.3890 [0.3727, 0.4060] | 0.0000 |
| B | nb | 0.3660 [0.3493, 0.3827] | -0.0230 |
| B | nb_pair | 0.3660 [0.3493, 0.3827] | -0.0230 |
| B | lookup | 0.3653 [0.3487, 0.3827] | -0.0237 |
| C | baseline | 0.3890 [0.3727, 0.4060] | 0.0000 |
| C | nb | 0.3580 [0.3417, 0.3753] | -0.0310 |
| C | nb_pair | 0.3570 [0.3403, 0.3747] | -0.0320 |
| C | lookup | 0.3577 [0.3413, 0.3747] | -0.0313 |
| D | baseline | 0.3890 [0.3727, 0.4060] | 0.0000 |
| D | nb | 0.3703 [0.3537, 0.3877] | -0.0187 |
| D | nb_pair | 0.3763 [0.3590, 0.3937] | -0.0127 |
| D | lookup | 0.3700 [0.3523, 0.3873] | -0.0190 |
| E | baseline | 0.3890 [0.3727, 0.4060] | 0.0000 |
| E | nb | 0.3580 [0.3413, 0.3750] | -0.0310 |
| E | nb_pair | 0.3580 [0.3413, 0.3750] | -0.0310 |
| E | lookup | 0.3463 [0.3303, 0.3637] | -0.0427 |

Largest accuracy above baseline: 0.0000 (A, baseline).

## Id-and-row-order-only attacker

Features: two leading and the last character of the opaque id, and the row's position decile in the attacker's input. Labels are the true training labels.

| Attacker | Accuracy [95% CI] | Minus baseline |
|---|---|---|
| baseline | 0.3890 [0.3727, 0.4060] | 0.0000 |
| nb | 0.3863 [0.3687, 0.4037] | -0.0027 |
| nb_pair | 0.3863 [0.3687, 0.4037] | -0.0027 |
| lookup | 0.3863 [0.3687, 0.4037] | -0.0027 |

## nb learning curve

Nested training subsets (the first n rows in the attacker's seeded order). The 6,000-label point is the primary run. A weaker attacker is a fairer picture than the protocol's strong, upper-bound one.

| n_train | A nb [95% CI] | B nb [95% CI] | C nb [95% CI] | D nb [95% CI] | E nb [95% CI] |
|---|---|---|---|---|---|
| 100 | 0.4440 [0.4270, 0.4610] | 0.5070 [0.4887, 0.5263] | 0.5050 [0.4870, 0.5230] | 0.5067 [0.4890, 0.5240] | 0.5153 [0.4973, 0.5327] |
| 300 | 0.4667 [0.4483, 0.4837] | 0.5200 [0.5020, 0.5373] | 0.5397 [0.5213, 0.5573] | 0.5353 [0.5167, 0.5523] | 0.5443 [0.5267, 0.5620] |
| 1000 | 0.5140 [0.4963, 0.5320] | 0.5197 [0.5027, 0.5377] | 0.5783 [0.5603, 0.5960] | 0.5563 [0.5383, 0.5747] | 0.5563 [0.5387, 0.5737] |
| 3000 | 0.5187 [0.5010, 0.5357] | 0.5323 [0.5153, 0.5493] | 0.5963 [0.5787, 0.6137] | 0.5833 [0.5653, 0.6007] | 0.5633 [0.5457, 0.5807] |
| 6000 | 0.5193 [0.5017, 0.5363] | 0.5327 [0.5150, 0.5503] | 0.6003 [0.5823, 0.6177] | 0.5820 [0.5637, 0.5983] | 0.5663 [0.5480, 0.5840] |
| unlimited (exact) | 0.5172 | 0.5271 | 0.5953 | 0.5755 | 0.5582 |
| Bayes ceiling | 0.5172 | 0.5271 | 0.6042 | 0.5755 | 0.5650 |

nb gains by training size: 100: C-A 0.0610, D-C 0.0017; 300: C-A 0.0730, D-C -0.0043; 1000: C-A 0.0643, D-C -0.0220; 3000: C-A 0.0777, D-C -0.0130; 6000: C-A 0.0810, D-C -0.0183.
