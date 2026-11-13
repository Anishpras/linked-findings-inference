# Release-design checklist

These lessons come from the linked-findings pilot. They follow the independent review of 2026-11-13, section 7.4, and each is tied to the result that supports it. The pilot is synthetic and every probability in it is invented. So each item is a lesson about mechanisms that the exact computations make visible, not a measured rate for real pipelines.

## The checklist

1. **A stable key across stages is the linkage.** If two stages' findings carry the same household identifier, anyone holding both can join them, and the linked release is what leaks.
   - *Supporting result:* in the pilot's data files, views A and B share the same opaque household IDs.
   - Linking A and B raises the exact Bayes ceiling from 0.517 and 0.527 (one release) to 0.604 (both, linked), against a 0.400 baseline.
   - Neither release contains the hidden band.
   - The confirmatory nb gains on the test split were +0.081 [0.062, 0.099] over A and +0.068 [0.050, 0.085] over B (`results/hypotheses.csv`, H1a and H1b, frozen v1.0).
2. **A field passed through verbatim leaks at full strength.** Copying a field into an output gives the output that field's entire information.
   - *Supporting result:* `goal_module` copies `r2.goal`, which alone carries 0.091 bits, the most of any field.
   - Removing `goal_module` from the checklist output drops its mutual information from 0.290 to 0.222 bits (`results/exploratory_e_vs_d.md`).
   - Verbatim pass-throughs make up 55% of all action items (`results/post_review_corrections.md`).
3. **List hard constraints that span stages, because they give exclusions.** A combination that is impossible for some value of the hidden attribute rules that value out outright, whatever the attacker. If the combination spans stages, only linking reveals it.
   - *Supporting result:* a major expense settled in full is impossible for the `low` band. Only the linked release shows the pair, and it rules out `low` for 5.75% of households (exactly).
   - The toolkit's budget finds this automatically ("logical exclusions created only by linking"), as it does for the grocery example's afternoon/no-bell constraint.
4. **A renderer that fills defaults makes claims without evidence.** If a report generator fills in a default when the evidence is missing, some of its outputs are right only by luck, and none of them is supported.
   - *Supporting result:* the default-filling renderer emits an answer with no supporting evidence on 51.0% of items in A, 42.0% in B and 16.4% in D (exact).
   - Roughly half to two-thirds of those happen to be right. Crediting them inflated B's action items conveyed from 0.458 to 0.621.
   - Only supported outputs should count (`results/post_review_corrections.md`).
5. **Task outputs still leak.** Releasing only what the task needs is not a privacy guarantee.
   - *Supporting result:* the nine checklist answers alone (view E) give an exact Bayes ceiling of 0.565, 16.5 points over the 0.400 baseline and more than either single release.
   - The confirmatory-era S2 estimate was +0.177 [0.156, 0.199] over the baseline.
6. **Coarsen the fields the task does not need before the ones it does.** A coarsening chosen without the task in view can cost utility and still leak.
   - *Supporting result:* the pilot's coarsening D keeps `income_pattern`, which the checklist never uses, while coarsening the very fields the checklist needs at fine grain.
   - D conveys only 10.8% of action items on the four items its coarsening touches.
   - In the exact design search, D (0.315 bits, utility 0.805) is dominated, for example by a design at 0.259 bits with utility 0.895 (`examples/household/output/report.md`).
7. **Check any design against the exact ceiling, not against one attacker.** A single learned attacker can understate leakage, or overstate a difference between designs.
   - *Supporting result:* naive Bayes cannot see the size × resolution interaction. Its best possible D − C gap is −0.020 against the Bayes gap of −0.029.
   - H2a's accuracy criterion was met in only 3 of 6 seed runs (`results/h2a_summary.md`).
   - On E, naive Bayes is misspecified (unlimited-data accuracy 0.558 against an exact 0.565), so it overstates the E − D gap.
   - `release_audit` reports the exact ceiling, nb_limit and learning curves side by side.

## "Release task outputs, not coarsened inputs": the guidance and its conditions

This is stated last because it holds only under conditions.

- **It holds against the linked fine release, always.** Task outputs are a deterministic function of the linked raw findings, so they can never leak more, and by definition they keep the full utility. Here the exact ceiling is 0.565 against 0.604.
- **Against a coarsening, it is not ordered in general.** It depends on the task.
  - In the pilot, E leaks less than the declared coarsening D (0.565 against 0.575 exactly). The ordering also held in about nine of ten randomly perturbed generators (`results/exploratory_e_vs_d.md`).
  - But one more checklist item that needs `income_pattern`, or one that flags "major expense settled in full", makes E leak more than D.
  - The comparison was not pre-specified; it is exploratory.
- **It assumes the task is fixed and known.** If the checklist changes, recompute. The toolkit's design search computes the frontier for your own task, with its exceptions visible.
- **It does not make the outputs safe.** Item 5 above still applies.
