# H2a across seed runs (post-review, v1.1)

Label: the primary result is **frozen v1.0 (confirmatory)**. Everything else on this page is **exploratory, post-review (v1.1)**, added after the test results were seen (independent review of 2026-11-13, sections 2.1 and 4.3).

## Confirmatory result (unchanged)

nb accuracy D - C on the pre-specified seed: **-0.0060 [-0.0280, 0.0160]**, not supported under the frozen criterion.

## All six seed runs (nb)

Seed run 0 is the primary run. Runs 1-5 are the seed replicates of protocol section 3.6, each with its own 10,000 households, split and training. Intervals are paired 95% percentile bootstraps (2,000 resamples of the scored households), which cover test-sample uncertainty only.

| Seed run | D - C accuracy | 95% CI | Meets criterion | D - C log-loss (bits) | 95% CI |
|---|---|---|---|---|---|
| 0 | -0.0060 | [-0.0280, 0.0160] | no | 0.0275 | [0.0052, 0.0495] |
| 1 | -0.0030 | [-0.0250, 0.0190] | no | 0.0666 | [0.0458, 0.0890] |
| 2 | 0.0020 | [-0.0220, 0.0250] | no | 0.0464 | [0.0239, 0.0676] |
| 3 | -0.0030 | [-0.0240, 0.0190] | no | 0.0397 | [0.0171, 0.0619] |
| 4 | -0.0120 | [-0.0350, 0.0100] | no | 0.0341 | [0.0090, 0.0591] |
| 5 | -0.0160 | [-0.0420, 0.0090] | no | 0.0313 | [0.0088, 0.0551] |

**0 of 6 seed runs meet the H2a criterion.**

Across-seed mean (post hoc): **-0.0063**, SD 0.0066, t interval on 5 df [-0.0133, 0.0006]. This combines test-sample, training and generator variability, which the bootstrap does not; it is not a confirmatory test and the seeds are not pooled into one.

## nb_pair and the sample oracle, per seed

| Seed run | nb_pair D - C [95% CI] | sample oracle D - C [95% CI] |
|---|---|---|
| 0 | -0.0170 [-0.0400, 0.0060] | -0.0140 [-0.0390, 0.0110] |
| 1 | -0.0250 [-0.0490, -0.0030] | -0.0390 [-0.0630, -0.0160] |
| 2 | -0.0120 [-0.0360, 0.0110] | -0.0160 [-0.0420, 0.0100] |
| 3 | -0.0040 [-0.0270, 0.0200] | -0.0190 [-0.0420, 0.0050] |
| 4 | -0.0210 [-0.0440, 0.0020] | -0.0150 [-0.0390, 0.0080] |
| 5 | -0.0140 [-0.0400, 0.0130] | -0.0180 [-0.0430, 0.0080] |

Intervals excluding 0 (D below C): nb_pair 1 of 6, sample oracle 1 of 6. These attackers are not uniformly decisive either at this sample size.

## Exact reference gaps (population, `main`)

| Attacker | D - C accuracy (exact) |
|---|---|
| Bayes-optimal (oracle) | -0.0287 (-1148130643/40000000000) |
| nb with unlimited training data (nb_limit) | -0.0199 (-7946254187/400000000000) |
| nb_pair with unlimited training data | -0.0287 |

## The power analysis was wrong (study lead)

The design-time power analysis in protocol section 3.9 was the study lead's, and it was wrong: it sized H2a from the Bayes-optimal gap (-0.0287) when H2a is tested with nb, whose best possible gap is -0.0199. Approximate realised power (normal approximation, paired SE 0.0114 = median across the six seed runs): 0.08 at the across-seed mean, 0.42 at nb's unlimited-data gap, against 0.72 had the attacker been Bayes-optimal.

## Log-loss (secondary, pre-specified under S9)

nb's D - C log-loss difference is 0.0275 to 0.0666 bits, with the interval excluding 0 in 6 of 6 runs. It was pre-specified as a secondary measure (S9) and is reported as such, not as a replacement test.

## How to read H2a

- Report the frozen primary result as the confirmatory result, with this table beside it.
- Do not replace the primary seed, pool the seeds into a new test, or describe H2a as robust or replicated.
