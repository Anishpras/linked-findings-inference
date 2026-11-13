# E (checklist answers only) versus D (coarsened linked releases): exploratory, post-review (v1.1)

Label: **exploratory, post-review (v1.1)**. E - D was not a pre-specified comparison (it is absent from protocol section 6). It was raised after the test results were seen and examined in the independent review (section 4.4).

## The defensible claim (review section 4.4, verbatim)

> releasing task outputs always dominates the linked fine release (same utility, 0.565 against 0.604 here) and still leaks (16.5 points over baseline, more than either single release); against a coarsening it is not ordered in general.

## Exact values

| Scenario | View | Bayes accuracy | MI (bits) | nb_limit |
|---|---|---|---|---|
| independence | C | 0.4000 | 0.0000 | 0.4000 |
| independence | D | 0.4000 | 0.0000 | 0.4000 |
| independence | E | 0.4000 | 0.0000 | 0.4000 |
| dep_025 | C | 0.4207 | 0.0279 | 0.4186 |
| dep_025 | D | 0.4159 | 0.0221 | 0.4159 |
| dep_025 | E | 0.4140 | 0.0194 | 0.4110 |
| dep_050 | C | 0.4758 | 0.1072 | 0.4715 |
| dep_050 | D | 0.4620 | 0.0861 | 0.4620 |
| dep_050 | E | 0.4582 | 0.0764 | 0.4486 |
| dep_075 | C | 0.5382 | 0.2290 | 0.5318 |
| dep_075 | D | 0.5167 | 0.1859 | 0.5167 |
| dep_075 | E | 0.5098 | 0.1676 | 0.5016 |
| main | C | 0.6042 | 0.3889 | 0.5953 |
| main | D | 0.5755 | 0.3148 | 0.5755 |
| main | E | 0.5650 | 0.2896 | 0.5582 |
| prev_balanced | C | 0.6076 | 0.4111 | 0.5990 |
| prev_balanced | D | 0.5785 | 0.3336 | 0.5785 |
| prev_balanced | E | 0.5672 | 0.3094 | 0.5527 |
| prev_skewed | C | 0.7437 | 0.2822 | 0.7342 |
| prev_skewed | D | 0.7263 | 0.2243 | 0.7263 |
| prev_skewed | E | 0.7238 | 0.2027 | 0.7095 |

Exact E - D Bayes accuracy: -0.0105 in `main`, -0.0024 in `prev_skewed`. "E keeps full utility" holds by definition (utility is the checklist and E is the checklist), for any generator.

## Per seed run (`main`)

| Seed run | Model | E - D accuracy [95% CI] | E - D log-loss [95% CI] |
|---|---|---|---|
| 0 | nb | -0.0157 [-0.0327, 0.0013] | 0.0575 [0.0352, 0.0783] |
| 0 | nb_pair | -0.0143 [-0.0317, 0.0027] | 0.0587 [0.0366, 0.0796] |
| 0 | oracle | -0.0010 [-0.0167, 0.0143] | 0.0204 [0.0066, 0.0340] |
| 1 | nb | -0.0053 [-0.0227, 0.0117] | 0.0644 [0.0402, 0.0904] |
| 1 | nb_pair | -0.0063 [-0.0240, 0.0113] | 0.0651 [0.0407, 0.0911] |
| 1 | oracle | -0.0043 [-0.0200, 0.0107] | 0.0098 [-0.0038, 0.0241] |
| 2 | nb | -0.0093 [-0.0277, 0.0100] | 0.0346 [0.0101, 0.0572] |
| 2 | nb_pair | -0.0137 [-0.0320, 0.0050] | 0.0381 [0.0139, 0.0602] |
| 2 | oracle | 0.0000 [-0.0150, 0.0160] | 0.0156 [0.0008, 0.0295] |
| 3 | nb | -0.0343 [-0.0513, -0.0167] | 0.0874 [0.0607, 0.1133] |
| 3 | nb_pair | -0.0373 [-0.0547, -0.0197] | 0.0882 [0.0612, 0.1145] |
| 3 | oracle | -0.0220 [-0.0367, -0.0070] | 0.0284 [0.0131, 0.0437] |
| 4 | nb | -0.0227 [-0.0400, -0.0047] | 0.0800 [0.0548, 0.1049] |
| 4 | nb_pair | -0.0240 [-0.0420, -0.0060] | 0.0790 [0.0539, 0.1037] |
| 4 | oracle | -0.0130 [-0.0280, 0.0023] | 0.0275 [0.0130, 0.0419] |
| 5 | nb | -0.0033 [-0.0213, 0.0147] | 0.0526 [0.0285, 0.0755] |
| 5 | nb_pair | -0.0043 [-0.0223, 0.0137] | 0.0526 [0.0287, 0.0752] |
| 5 | oracle | -0.0110 [-0.0253, 0.0037] | 0.0193 [0.0050, 0.0334] |

Accuracy intervals excluding 0: nb 2 of 6, nb_pair 2 of 6, sample oracle 1 of 6. nb is misspecified on E (its unlimited-data accuracy is 0.5582 against an exact 0.5650), so it overstates the gap.

## Variants (review section 4.4 table, exact, `main`)

| View | Bayes accuracy | MI (bits) | nb_limit |
|---|---|---|---|
| C (linked fine releases) | 0.6042 | 0.3889 | 0.5953 |
| D | 0.5755 | 0.3148 | 0.5755 |
| D without income_pattern | 0.5667 | 0.2936 | 0.5667 |
| E | 0.5650 | 0.2896 | 0.5582 |
| E plus one item that needs income_pattern | 0.5762 | 0.3110 | 0.5600 |
| E plus one item 'major expense settled in full' | 0.5793 | 0.3252 | 0.5666 |
| E plus both | 0.5871 | 0.3456 | 0.5783 |
| E without goal_module | 0.5380 | 0.2218 | 0.5305 |
| baseline | 0.4000 | 0.0000 | 0.4000 |

D keeps `income_pattern`, which the checklist never uses, while coarsening the fields the checklist needs at fine grain. One more checklist item and E leaks more than D.

## Robustness to the generator's probabilities (port of the reviewer's script)

Same schema, checklist and coarsening; 400 random generators per setting. Ported from the reviewer's `a4.py` with attribution in `lfi/exploratory.py`; random draws use only `Random.random()`, so they differ from the reviewer's (who reported 93%, 90%, 91% and 93% for Bayes accuracy and 93% to 96% for MI).

| Setting | P(Bayes acc E < D) | P(MI E < D) | E - D accuracy gap: median [5%, 95%] |
|---|---|---|---|
| local perturbation sigma=0.25 | 0.925 | 0.968 | -0.0144 [-0.0362, 0.0019] |
| local perturbation sigma=0.5 | 0.885 | 0.900 | -0.0239 [-0.0717, 0.0122] |
| local sigma=0.5 + random prevalence | 0.887 | 0.920 | -0.0204 [-0.0707, 0.0051] |
| fully random Dirichlet(1) conditionals + random prevalence | 0.922 | 0.940 | -0.0473 [-0.1441, 0.0063] |

The ordering is fairly robust to the probabilities and not robust to the checklist or to the choice of D (variants above). Against a coarsening, E and D are not ordered in general.
