# src/dss/

Decision support component (owner: Nguyễn Duy Thịnh). Reads only from `dm.*`, writes results to `dss.*`.

Final design (report section 5): one decision, supported at one moment.
- **When the seller hands an order over to the carrier**, predict the probability that it will be late
  (tuned HistGradientBoosting) plus the rule "already past the estimated date" (certainly late).
- Each day the riskiest orders are flagged RED (top 5%) / YELLOW (next 10%) with three reasons and an action
  (warn the customer, voucher, faster shipping); a voucher is only worth it above the expected-cost threshold
  `p* = C_intervene / (C_late * effect)`.
- The model is retrained every month on orders whose estimated date has passed (no future labels).

Targets (report table `tab:chitieu`) and results on the test months 06-08/2018:

| Target | Threshold | Result |
|---|---|---|
| Late orders caught when flagging 10% of orders | >= 40% | 42.6% (model), 46.5% with the rule |
| ROC-AUC | >= 0.70 | 0.744 |
| Every test month | >= 30% | 40.5%, 43.0%, 44.1% |
| Late rate RED vs GREEN | >= 5x | 30.8% vs 2.4% (13.0x) |

Model selection: an extended search (60 HGB settings per feature set, 4 LR settings, carrier-backlog
features, rank-average ensemble) on validation 01-05/2018. The five candidates are within noise of each
other on any single period, so they are compared over all 14 walk-forward months. The production model is the
tuned HGB with backlog features (`hgb_tuned_backlog`): best mean recall@10 over 14 months (33.1%) and over
2018 (36.9%), better than the first small-grid model (`hgb_v1`) in every period and in 8 of 14 months.
Because the test months are part of this comparison, the report says the test figures are slightly optimistic.
`results/best_config.json` stores the final model ("final") and the search result ("ensemble");
`score_delay.py` reads "final".

| File | Role |
|---|---|
| `features.py` | Labels (incl. open orders already past their estimated date) and point-in-time features from `dm.*` |
| `evaluate_baseline.py` | First evaluation (static model, random vs time split) - kept as the "before" reference |
| `evaluate_models.py` | Random search on 01-05/2018 (~1.5 h; `--reuse` skips it), walk-forward 07/2017-08/2018, test 06-08/2018. It also evaluates the approval moment, which stayed below target (~21-25%) and is listed as future work |
| `score_delay.py` | Monthly scoring of the orders handed over in the test months, RED/YELLOW/GREEN, three reasons, actions -> `dss.delay_risk_score`, `dss.model_registry`; capacity curve, confusion matrix and expected-cost backtest |
| `results/` | CSV/JSON outputs used by the report figures |

Cost assumptions of the expected-cost policy are constants at the top of `score_delay.py` (`COST`).
