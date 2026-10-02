# Retention strategy

This project uses synthetic data inspired by common online gaming analytics use cases. It does not contain confidential or proprietary Junglee Games data.

The model predicts risk. It does not estimate the causal effect of an intervention. Actions below are routing rules so CRM, Product, Payments, and VIP operations work the same list differently. Overlapping rules are resolved in the order written here, because a high-value player who is also declining should be owned by the VIP desk rather than by a mass journey.

## Risk bands

Bands are policy cuts on predicted probability, set in `config/config.yaml`.

| Band | Default probability | Meaning |
| --- | --- | --- |
| LOW | below 0.20 | Leave on the normal lifecycle |
| MEDIUM | 0.20 to below 0.40 | Watchlist. Light nudge only. No heavy incentive |
| HIGH | 0.40 to below 0.65 | Route to a specific playbook |
| CRITICAL | 0.65 and above | Same playbook as HIGH, marked urgent |

These cuts are not universally optimal. A cheaper channel can sit at a lower probability; a host call should sit higher. The validation snapshot also tunes a single F-beta threshold (beta 1.5, recall-weighted) for the binary "contact / don't contact" view. Bands and that threshold answer different operating questions and are allowed to disagree.

## Playbooks

Evaluated only for HIGH and CRITICAL, first match wins.

1. **High value** — VIP segment is Gold, Platinum, or Diamond, or lifetime rake is at or above the 75th percentile of the scored book. Action: priority VIP retention. A host reviews recent tables, withdrawal experience, and whether the player is owed a service call rather than a generic bonus.
2. **Recent withdrawal** — a withdrawal in the last 7 days. Action: win-back and product-experience review. Cashing out and then going quiet is often a trust or gameplay issue, not an offer-depth issue.
3. **Deposit decline** — prior-week deposits were material (at least 100) and the latest week is at most 60% of that. Action: payment and deposit-friction investigation, plus reactivation comms. Check failures, limits, and bonus credit before spending on media.
4. **Activity decline** — prior week had at least 3 games and the latest week is at most 60% of that. Action: engagement journey (return to preferred variant, not a new product pitch).
5. **Low activity** — 3 or fewer active days, or games in the last 30 days at or below the 40th percentile of the scored book. Action: low-friction re-engagement. Short session, familiar buy-in, no large deposit ask.
6. **Otherwise** — engagement journey.

LOW risk: normal lifecycle engagement. MEDIUM risk: watchlist, light lifecycle nudge, no heavy incentive.

`src/retention_engine.py` implements this order. Quantiles are computed on the book being scored, so the cut moves with the population and does not require a retrain.

## Contact budget

Retention cannot work the whole active base. The operating question is capture in the top 5%, 10%, and 20% of predicted risk. Those figures are in `reports/model_metrics/capture_at_contact_rate.csv` and are repeated in the README from the actual holdout. Use them to size the desk. Do not use accuracy.

## A/B test: how incremental retention would be measured

Nothing in the model training measures incrementality. The design below is what the business should run before a rollout claim.

### Population

Eligible players are those scored HIGH or CRITICAL on a frozen scoring date, excluding anyone already in another test, self-excluded, or in a payments-failure hold. Eligibility is fixed before randomization. Players who become inactive before the test starts are not quietly dropped from one arm.

### Arms

- **Treatment:** the personalized route above (VIP host, payment review, engagement journey, or low-friction re-engagement), within a pre-agreed cost cap.
- **Control:** business as usual. No extra journey because of this model. Organic CRM calendars still run, and they must be the same calendar the treatment arm would have received without the test.

### Randomization

Assign at player level, 50/50, stratified by risk band, VIP segment, and tenure bucket so the arms start balanced on the factors that dominate both risk and value. Freeze the assignment file. Do not re-randomize mid-test. Do not let hosts "pull" control VIPs into treatment.

### Primary metric

D30 retention: share of eligible players with at least one game in the 30 days after assignment. This matches the model's label window so the experiment and the model speak the same language.

### Secondary metrics

D7 retention, games per user, active days, rake (or NGR if the ledger supports it), deposit amount, and deposit conversion. These explain whether retention was "one cheap game" or a real return to play.

### Guardrails

Promo cost per retained player, bonus cost, complaint rate, unsubscribe rate, and responsible-play flags. A treatment that "wins" retention by over-bonusing or by annoying the base fails the test even if the primary metric moves.

### Sample size, significance, intervals

Size the test from the control D30 retention rate you expect in this high-risk pool (it will be lower than the overall base rate) and the smallest lift worth the operational cost. A practical starting point is an 80% power, two-sided 5% test on a difference in proportions. Report a confidence interval on the absolute difference in D30 retention, not only a p-value. Pre-register the primary metric and the guardrails. Do not fish secondaries into the headline.

### Incremental impact and ROI

Incremental retained players = (treatment D30 retention − control D30 retention) × players treated.

Contribution of an incremental retained player should be a finance-agreed margin over the outcome window (rake or NGR, net of payment cost and bonus), not gross deposit. Then:

ROI = (incremental retained players × margin per retained player − treatment cost) / treatment cost.

Treatment cost includes bonus, host time, and message cost. If the interval on incremental players covers zero, ROI is not reportable as a win.

### What would invalidate the read

Changing the model or the playbook mid-test, unequal BAU calendars, dropping players after assignment, or judging the test on a metric that was not primary. A positive model AUC does not shorten this list.
