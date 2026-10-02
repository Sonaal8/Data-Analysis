# Model monitoring

This project uses synthetic data inspired by common online gaming analytics use cases. It does not contain confidential or proprietary Junglee Games data.

This is the canonical monitoring note. `monitoring/model_monitoring.md` points here and records the latest numerical check.

The June holdout is a backtest. In production the score is issued on day T and the label arrives only after day T+30. Monitoring has to look at inputs and scores every week, and at performance only once labels mature.

## What is watched

| Layer | Question | Metric |
| --- | --- | --- |
| Data | Did the extract break? | Row counts, null rates, duplicate player-snapshot keys, share of players with a game in the feature window |
| Features | Did behavior drift? | PSI and mean/quantile shift versus the training month, for recency, games, deposits, rake, bonus dependency, inactivity gap |
| Scores | Is the desk seeing a different book? | PSI of predicted probability, share in HIGH and CRITICAL, mean probability |
| Outcomes | Did ranking quality decay? | ROC-AUC, PR-AUC, recall, precision, calibration, once the 30-day label matures |
| Operations | Did the route get used? | Contact rate, action mix, bonus cost, complaints. These are not model-fit metrics |

## PSI

Population stability index compares a reference distribution (April training snapshot) with a later one (June scoring snapshot), using quantile bins of the reference. A conventional reading used by this project:

- below 0.10: stable enough to keep scoring
- 0.10 to 0.25: watch, inspect which features moved
- above 0.25: do not treat the score as interchangeable with last month's score until someone explains the shift

These cutoffs are guidelines. A known product launch can push PSI without the model being "wrong."

The latest April-versus-June feature PSI and a simulated engagement drop are written to `reports/model_metrics/feature_psi.csv` and `reports/model_metrics/monitoring.json` by `python -m src.monitoring`.

## Performance and calibration

When labels mature, recompute the same metrics as the model card on the matured book: ROC-AUC, PR-AUC, precision, recall, and F1 at the frozen threshold. Also bin players by predicted probability and compare the bin's average score with the observed churn rate. A model that ranks well but is over-confident will overload the CRITICAL band.

Do not refit the threshold on the same month you use to claim performance.

## Degradation

Compare the matured month with the original May/June card. A drop in PR-AUC matters more than a drop in accuracy. If recall at the frozen threshold falls, the desk is missing churners it used to catch. If precision falls, the desk is calling players who would have stayed.

## Simulation in this repository

`src/monitoring.py` does two things:

1. It measures real feature PSI between the April reference and the June book.
2. It copies the June feature matrix, reduces recent games, sessions, and rake by 30%, adds four days to recency, and rescores. Labels are not altered. The mean score and the score PSI are the alert. This shows the monitor firing **before** anyone could know the new outcomes.

## What to do when behavior changes

- If a feature pipeline bug moved a definition (window off by one day, bonus double count), stop scoring and fix the SQL. Do not retrain over a broken feature.
- If a real product change moved behavior (new variant, new bonus mechanic), keep scoring but flag the PSI, and wait for one matured label window before retraining.
- Retrain on a fresh temporal split. Do not shuffle the new month into the old training rows and call the random-split AUC the new quality.
- Re-issue the threshold and the band cuts as an explicit policy decision. Do not silently inherit last quarter's 0.40 cut if the score distribution has shifted.
- Tell CRM the rank order may still be useful while the probability level is not. Those are different failures.

## Cadence

- Daily: row counts, nulls, score-volume by band.
- Weekly: feature PSI, score PSI, action mix, cost.
- Every matured 30-day window: ROC-AUC, PR-AUC, recall, precision, calibration, lift at 10% contact.
- Retrain when matured PR-AUC or recall at the operating threshold drops materially, or when a watched feature stays above the act PSI for two scoring cycles and the cause is behavioral rather than a bug.
