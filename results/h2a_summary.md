# H2a across seed runs (post-review, v1.1)

Label: the primary result is **frozen v1.0 (confirmatory)**. Everything else on this page is **exploratory, post-review (v1.1)**, added after the test results were seen (independent review of 2026-11-13, sections 2.1 and 4.3).

## Confirmatory result (unchanged)

nb accuracy D - C on the pre-specified seed: **-0.0183 [-0.0313, -0.0057]**, supported under the frozen criterion.

## All six seed runs (nb)

Seed run 0 is the primary run. Runs 1-5 are the seed replicates of protocol section 3.6, each with its own 10,000 households, split and training. Intervals are paired 95% percentile bootstraps (2,000 resamples of the scored households), which cover test-sample uncertainty only.

| Seed run | D - C accuracy | 95% CI | Meets criterion | D - C log-loss (bits) | 95% CI |
|---|---|---|---|---|---|
| 0 | -0.0183 | [-0.0313, -0.0057] | yes | 0.0465 | [0.0338, 0.0581] |
| 1 | -0.0130 | [-0.0260, 0.0003] | no | 0.0436 | [0.0293, 0.0575] |
| 2 | -0.0047 | [-0.0190, 0.0087] | no | 0.0421 | [0.0300, 0.0542] |
| 3 | -0.0160 | [-0.0297, -0.0030] | yes | 0.0432 | [0.0299, 0.0562] |
| 4 | -0.0133 | [-0.0273, 0.0010] | no | 0.0529 | [0.0392, 0.0652] |
| 5 | -0.0200 | [-0.0330, -0.0073] | yes | 0.0480 | [0.0349, 0.0602] |

**3 of 6 seed runs meet the H2a criterion.**

Across-seed mean (post hoc): **-0.0142**, SD 0.0054, t interval on 5 df [-0.0199, -0.0085]. This combines test-sample, training and generator variability, which the bootstrap does not; it is not a confirmatory test and the seeds are not pooled into one.

## nb_pair and the sample oracle, per seed

| Seed run | nb_pair D - C [95% CI] | sample oracle D - C [95% CI] |
|---|---|---|
| 0 | -0.0280 [-0.0417, -0.0150] | -0.0330 [-0.0463, -0.0183] |
| 1 | -0.0173 [-0.0327, -0.0033] | -0.0177 [-0.0327, -0.0040] |
| 2 | -0.0283 [-0.0430, -0.0147] | -0.0273 [-0.0417, -0.0130] |
| 3 | -0.0253 [-0.0383, -0.0120] | -0.0250 [-0.0390, -0.0107] |
| 4 | -0.0253 [-0.0390, -0.0107] | -0.0227 [-0.0363, -0.0093] |
| 5 | -0.0273 [-0.0413, -0.0140] | -0.0237 [-0.0373, -0.0107] |

Intervals excluding 0 (D below C): nb_pair 6 of 6, sample oracle 6 of 6. Both attackers that can use the size x resolution interaction, which the coarsening removes, show D below C in every run; the fragility is specific to nb, which cannot.

## Exact reference gaps (population, `main`)

| Attacker | D - C accuracy (exact) |
|---|---|
| Bayes-optimal (oracle) | -0.0287 (-1148130643/40000000000) |
| nb with unlimited training data (nb_limit) | -0.0199 (-7946254187/400000000000) |
| nb_pair with unlimited training data | -0.0287 |

## The power analysis was wrong (study lead)

The design-time power analysis in protocol section 3.9 was the study lead's, and it was wrong: it sized H2a from the Bayes-optimal gap (-0.0287) when H2a is tested with nb, whose best possible gap is -0.0199. Approximate realised power (normal approximation, paired SE 0.0068 = median across the six seed runs): 0.56 at the across-seed mean, 0.84 at nb's unlimited-data gap, against 0.99 had the attacker been Bayes-optimal. The pre-specified seed happened to land on the passing side.

## Log-loss (secondary, pre-specified under S9)

nb's D - C log-loss difference is 0.0421 to 0.0529 bits, with the interval excluding 0 in 6 of 6 runs. It was pre-specified as a secondary measure (S9) and is reported as such, not as a replacement test.

## How to read H2a

- Report the frozen primary result as the confirmatory result, with this table beside it.
- Do not replace the primary seed, pool the seeds into a new test, or describe H2a as robust or replicated.
