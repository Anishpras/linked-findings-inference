# Release audit from labelled records (target `young_children`)

400 records; classes yes, no; columns order.basket_size, order.delivery_window, order.substitutions_allowed, picking.bulk_items, picking.out_of_stock, delivery.doorstep_instruction, delivery.outcome.

Read these as estimates. The plug-in Bayes accuracy is optimistic (it is scored on the records it was fitted to) and the plug-in MI is biased upward, badly so with many view values and few records; the Miller-Madow value corrects part of that bias. Cross-validated accuracies are from pooled out-of-fold predictions; the standard errors are binomial and ignore fold-to-fold variation. Utility is computed on the observed support only and can overstate what a view conveys. Zeros in observed counts are not hard constraints, so no logical exclusions are reported.

| View | Plug-in Bayes (resub.) | Lookup (CV) | MI plug-in | MI Miller-Madow | nb (CV) | Pairwise logistic (CV) | Utility (observed) |
|---|---|---|---|---|---|---|---|
| order | 0.7100 | 0.6575 | 0.0816 | 0.0527 | 0.6775 +/- 0.0234 | 0.6725 +/- 0.0235 | 0.5892 |
| picking | 0.7500 | 0.7450 | 0.1644 | 0.1517 | 0.7475 +/- 0.0217 | 0.7450 +/- 0.0218 | 0.0868 |
| delivery | 0.7625 | 0.7375 | 0.1010 | 0.0884 | 0.7550 +/- 0.0215 | 0.7400 +/- 0.0219 | 0.2567 |
| linked | 0.9100 | 0.6575 | 0.6565 | 0.6042 | 0.7700 +/- 0.0210 | 0.7225 +/- 0.0224 | 1.0000 |
| coarsened | 0.8000 | 0.7375 | 0.3245 | 0.2614 | 0.7225 +/- 0.0224 | 0.7400 +/- 0.0219 | 0.5196 |
| items_only | 0.7975 | 0.7175 | 0.2779 | 0.2256 | 0.7250 +/- 0.0223 | 0.7175 +/- 0.0225 | 1.0000 |

## Learning curves (cross-validated accuracy by share of each training fold)

| View | Attacker | 0.1 | 0.25 | 0.5 | 1.0 |
|---|---|---|---|---|---|
| order | nb | 0.6525 | 0.6950 | 0.6825 | 0.6775 |
| order | logistic | 0.6450 | 0.6625 | 0.6525 | 0.6725 |
| picking | nb | 0.7075 | 0.7200 | 0.7450 | 0.7475 |
| picking | logistic | 0.6775 | 0.7200 | 0.7300 | 0.7450 |
| delivery | nb | 0.7300 | 0.7500 | 0.7550 | 0.7550 |
| delivery | logistic | 0.7300 | 0.7500 | 0.7500 | 0.7400 |
| linked | nb | 0.7100 | 0.7875 | 0.7825 | 0.7700 |
| linked | logistic | 0.6625 | 0.7450 | 0.7300 | 0.7225 |
| coarsened | nb | 0.6800 | 0.7475 | 0.7275 | 0.7225 |
| coarsened | logistic | 0.6100 | 0.7100 | 0.7125 | 0.7400 |
| items_only | nb | 0.7325 | 0.7300 | 0.7300 | 0.7250 |
| items_only | logistic | 0.6450 | 0.7100 | 0.7125 | 0.7175 |
