# Model card

This project uses synthetic data inspired by common online gaming analytics use cases. It does not contain confidential or proprietary Junglee Games data.

Numbers below are copied from `reports/model_metrics/metrics.json` after the 100,000-player run (`python -m src.pipeline --n-users 100000`). They are not targets.

## Intended use

Rank currently active players by the probability they play no game in the next 30 days, so a limited CRM and VIP capacity can be aimed at the risky slice. The score is an input to the routing rules in `docs/retention_strategy.md`.

## Out of scope

- Causal effect of a bonus, host call, or journey.
- Already-dormant reactivation (no game in the prior 30 days).
- Responsible-play enforcement. A high score is not a vulnerability label.
- Pricing, stake limits, or eligibility for credit.

## Data

Synthetic players and events from `python -m src.data_generation`. Labels and features from `sql/` via `python -m src.feature_engineering`. Population: registered before the prediction date and at least one game in the prior 30 days.

Snapshots:

| Split | Prediction date | Role |
| --- | --- | --- |
| train | 2025-04-15 | Fit |
| valid | 2025-05-15 | Threshold and model choice (PR-AUC) |
| test | 2025-06-15 | One-shot reported performance |

## Target

`churned = 1` when summed `games_played` in `[prediction_date, prediction_date + 30 days)` is zero.

## Features

See `docs/feature_dictionary.md`. The estimator does not see the label, the outcome-window game count, gender, or snapshot ranks.

## Training

Class imbalance is handled with class weights (logistic regression, random forest, histogram gradient boosting, LightGBM) or `scale_pos_weight` / sample weights (XGBoost, sklearn gradient boosting). Hyperparameters are a small grid, chosen by stratified cross-validated average precision on a subsample of April, then refit on all April rows. The May snapshot picks an F-beta threshold with beta 1.5. June is not used to pick the model or the threshold.

## Population actually scored

| Snapshot | Prediction date | Players | Churn rate |
| --- | --- | --- | --- |
| train | 2025-04-15 | 88,892 | 16.3% |
| valid | 2025-05-15 | 82,706 | 17.1% |
| test | 2025-06-15 | 71,164 | 21.6% |

## June holdout at each model's May-tuned threshold

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC | Threshold | May PR-AUC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest (champion) | 0.653 | 0.354 | 0.728 | 0.476 | 0.721 | 0.372 | 0.46 | 0.648 |
| logistic_regression | 0.642 | 0.345 | 0.728 | 0.468 | 0.716 | 0.367 | 0.64 | 0.529 |
| xgboost | 0.658 | 0.354 | 0.705 | 0.471 | 0.712 | 0.367 | 0.53 | 0.633 |
| hist_gradient_boosting | 0.655 | 0.353 | 0.715 | 0.473 | 0.717 | 0.367 | 0.53 | 0.629 |
| lightgbm | 0.656 | 0.353 | 0.705 | 0.470 | 0.716 | 0.366 | 0.53 | 0.635 |
| gradient_boosting | 0.654 | 0.354 | 0.724 | 0.476 | 0.716 | 0.361 | 0.56 | 0.628 |

Champion confusion matrix on June at 0.46: TN 35,277, FP 20,488, FN 4,191, TP 11,208.

Random 70/30 split inside June, same random-forest hyperparameters and the same 0.46 threshold: ROC-AUC 0.773, PR-AUC 0.455. The temporal April→June numbers above are the ones to quote.

## Selection rule

Highest PR-AUC on May. ROC-AUC breaks ties. Accuracy is not used. Random forest won May PR-AUC (0.648 vs 0.529 for logistic regression). On June the gap shrank to 0.372 vs 0.367. The forest is the champion because validation ranking was clearly better; the holdout does not support a claim that the forest is much stronger out of time.

## Calibration

Class weighting lifts the score level. On June the mean predicted probability is 0.529 while the observed churn rate is 0.216. The May-tuned threshold of 0.46 therefore contacts about 44.5% of the June book (31,696 players). Risk bands at 0.20 / 0.40 / 0.65 were set as policy on a probability scale and, on this uncalibrated June distribution, put 28,927 players in CRITICAL. Use rank (top 5/10/20%) for capacity planning until a calibrator fit on May is frozen and the score PSI is back under the act line.

## Ethical and product notes

Gender is collected on the synthetic profile for EDA and is not a scoring feature. VIP segment is used because the route and the economics differ by tier, not as a fairness target. Stake and rake features can proxy ability to spend; that is intentional for a value-aware retention desk and is a reason not to automate large incentives from the score alone.

## Limitations

- Synthetic behavioral mechanisms are simpler than a live economy. Treat the level of AUC as evidence the pipeline is coherent, and re-estimate on production history before a launch.
- One anchor game is sometimes inserted by the generator so cohort labels are identifiable. Stochastic play still dominates volume for engaged players. The label itself is always the presence or absence of games in the outcome window.
- Tree contributions explain the score, not the effect of changing a feature in the product.
- Bands at 0.20 / 0.40 / 0.65 are policy.

## Maintenance

See `docs/model_monitoring.md`. Retrain on a new temporal split when matured PR-AUC or recall at the frozen threshold drops, or when feature PSI stays in the act zone for a behavioral reason.
