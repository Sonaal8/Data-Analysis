# Feature dictionary

This project uses synthetic data inspired by common online gaming analytics use cases. It does not contain confidential or proprietary Junglee Games data.

All features are computed from events with `event_date < prediction_date`. The prediction date is the first day of the outcome window. `games_in_label_window` and `churned` are labels, not features. `games_per_active_day` is stored because the frequency taxonomy asks for it; it equals `avg_games_per_active_day` and is omitted from the estimator so the linear model is not handed a duplicated column.

Change features use `(recent − previous) / (previous + 1)`. The `+ 1` keeps a zero prior week from exploding the ratio. A negative value is a decline.

| Feature | Definition | Business meaning | Why it may predict churn |
| --- | --- | --- | --- |
| games_7d | Sum of `games_played` in [T−7, T) | How much they played this week | A quiet week is the start of a lapse, especially if the prior week was busy |
| games_14d | Sum of `games_played` in [T−14, T) | Two-week volume | Smooths a single dead day without ignoring a real fade |
| games_30d | Sum of `games_played` in [T−30, T) | Monthly playing volume | Low monthly volume raises the chance the next month is empty |
| active_days_7d | Distinct game dates in [T−7, T) | Breadth of the week, not just one long sitting | One binge day is less sticky than several return days |
| active_days_30d | Distinct game dates in [T−30, T) | How many days the habit showed up | Habit, more than a single session length, is what retention is trying to protect |
| sessions_7d | Session rows in [T−7, T) | App opens and sittings this week | Sessions can fall before games do, when the player opens the app and leaves |
| sessions_30d | Session rows in [T−30, T) | Monthly visit count | Fewer visits, fewer chances to take a seat |
| avg_session_duration | Mean session length in [T−30, T). 0 if none | How long a visit lasts, including lobby time | Shrinking visits often precede a stop, but a few long sessions can also be a cash-out pattern |
| total_play_time | Sum of game `duration_minutes` in [T−30, T) | Time actually in contests | Separates a player who taps in and out from one who is still in seats |
| avg_games_per_active_day | `games_30d / active_days_30d` | Intensity on days they show up | Distinguishes a grinder from a light daily visitor |
| days_since_last_game | T minus the last game date before T | Recency of play | The strongest simple marker in most gaming lapse models. Someone last seen three weeks ago is not in the same state as someone who played yesterday |
| days_since_last_login | T minus last session before T. Tenure if they never logged in during the extract | Recency of opening the product | A login without a game is a different failure from no login at all |
| days_since_last_deposit | T minus last deposit before T. Tenure if they never deposited, with `never_deposited = 1` | How stale the wallet funding is | Players often stop funding before they stop sitting down |
| days_since_last_withdrawal | T minus last withdrawal before T. Tenure if none, with `never_withdrew = 1` | How recently they cashed out | A withdrawal in the last few days plus silence is a win-back and experience problem, not a generic "play more" problem |
| never_deposited | 1 if no deposit before T | The recency fill is tenure, not a real deposit | Stops the model from reading "days since deposit = tenure" as if a deposit happened |
| never_withdrew | 1 if no withdrawal before T | Same idea for withdrawals | Many healthy players never withdraw. The flag keeps that from looking like a long gap after a cash-out |
| games_per_day | `games_30d / 30` | Volume spread across the calendar month | Comparable across players with different active-day counts |
| games_per_active_day | Same value as `avg_games_per_active_day` | Frequency taxonomy alias | Kept for analysts. Not passed to the estimator |
| sessions_per_active_day | Sessions divided by distinct session dates in 30 days | Whether visits are single sittings or split across the day | Rising sessions per day with falling games can mean failed attempts to play |
| deposit_amount_7d | Sum of deposit amounts in [T−7, T) | This week's funding | A drop against last week is an early wallet signal |
| deposit_amount_30d | Sum of deposits in [T−30, T) | Monthly funding | Low funding limits how long paid play can continue |
| withdrawal_amount_30d | Sum of withdrawals in [T−30, T) | Cash taken off the platform | High cash-out relative to deposits is a leave signal for some VIPs and a healthy cash-out for others. The model has to learn which, from context |
| net_deposit_30d | Deposits minus withdrawals in 30 days | Net money left on the platform this month | A sharply negative net deposit is not the same as a player who never had money in |
| rake_7d | Sum of rake in [T−7, T) | This week's direct revenue contribution | Revenue fading faster than headcount is the VIP problem |
| rake_30d | Sum of rake in [T−30, T) | Monthly revenue contribution | Ties engagement to value |
| avg_entry_fee | Games-weighted average buy-in in 30 days: sum(entry fee × games) / games | The stakes they actually chose | A move down the stake ladder often comes before a stop |
| total_entry_fee | Sum of entry fee × games in 30 days | Total stakes sat down at | Volume of money risked, distinct from rake |
| games_change_7d_vs_previous_7d | (games_7d − games in [T−14, T−7)) / (prior + 1) | Week-on-week change in play | A negative change is the "they used to play" pattern CRM can still catch |
| games_change_14d_vs_previous_14d | (games in [T−14, T) − games in [T−28, T−14)) / (prior + 1) | Two-week change | Confirms a fade that is not just one odd week |
| deposit_change_7d_vs_previous_7d | Same ratio on deposit amounts | Week-on-week funding change | Funding can drop while games are still happening on leftover balance |
| rake_change_7d_vs_previous_7d | Same ratio on rake | Week-on-week revenue change | A VIP can stay "active" on tiny stakes while rake collapses |
| session_change_7d_vs_previous_7d | Same ratio on session counts | Week-on-week visits | Visits falling is the top of the lapse funnel |
| game_frequency_std | Sample standard deviation of daily game counts across the 30 calendar days, zeros included | How uneven play was | Erratic play is less stable than a flat habit, even at the same total |
| deposit_frequency_std | Sample standard deviation of daily deposit amounts across the 30 days, zeros included | How uneven funding was | One large deposit and then nothing is different from a weekly top-up |
| session_duration_std | Sample standard deviation of session length in the 30-day window. 0 if fewer than two sessions | How uneven visits were | A collapse from long sessions to short ones shows up here even if the mean is moderate |
| lifetime_games | Sum of `games_played` on all dates before T | Career volume inside the extract | Separates a new light player from a veteran who has gone quiet |
| lifetime_deposit | Sum of deposits before T | Career funding | High lifetime deposit with a recent stop is a save worth a host |
| lifetime_rake | Sum of rake before T | Career revenue contribution | The value side of "high value, declining" |
| player_tenure_days | T minus registration date | How long they have been a customer | New accounts lapse differently from veterans. Tenure is the clock; it is not a substitute for recent behavior |
| vip_segment | Segment on the player record (Regular through Diamond) | Commercial tier | Tiers do not all lapse the same way, and the route for a Diamond player is not a mass SMS |
| preferred_game_type | Mode of game type by `games_played` in the 30-day window. Ties break alphabetically | The product they actually play | A retention message about the wrong variant is noise |
| preferred_game_variant | Mode of variant in the 30-day window | Stake and format inside the type (101 vs 201, best of 2 vs best of 3, points level) | Even more specific than type. Useful for the journey, weaker as a global driver |
| tournament_affinity | Share of 30-day games with `tournament_flag = 1` | Taste for tournaments | Tournament players are scheduled; missing the next event is a different lapse than skipping a cash table |
| pool_affinity | Share of 30-day games that are Pool Rummy | Taste for pool | Product mix shifts sometimes precede a stop |
| points_affinity | Share of 30-day games that are Points Rummy | Taste for points | Same idea |
| deals_affinity | Share of 30-day games that are Deals Rummy | Taste for deals | Same idea |
| bonus_received_30d | Sum of `bonus_amount` in [T−30, T) from the bonus table | Incentive taken onto the account | High bonus with low deposit is a subsidy pattern |
| bonus_used_30d | Sum of bonus amount where `bonus_used_flag = 1` in the window | Incentive actually consumed | Unused bonus is not engagement |
| cashback_received_30d | Sum of cashback transactions in the window | Post-play rebate | Cashback-heavy players can be margin-negative if play is thin |
| bonus_dependency_ratio | bonus received / (deposits + bonus received) in 30 days. 0 if both are 0 | How much of the month's funding was incentive | Promotion-sensitive players leave when the offer stops. The ratio is a flag for that desk, not a reason to send a larger offer by default |
| activity_decline_flag | 1 when prior-week games ≥ 3 and this week ≤ 60% of that | A clear fade, not just a low base | Gives CRM a binary the journey can key off, while the model still sees the raw counts |
| deposit_decline_flag | 1 when prior-week deposits ≥ 100 and this week ≤ 60% of that | A clear funding fade | Routes to payments and reactivation rather than a content journey |
| reduced_session_flag | 1 when prior-week sessions ≥ 2 and this week ≤ 60% of that | Visits dropped | Often earlier than the game-count flag |
| high_withdrawal_to_deposit_ratio | 1 when 30-day withdrawals are at least 80% of 30-day deposits, or withdrawals are positive and deposits are zero | Cashing out relative to funding | Combined with high risk, this is the win-back / experience route |
| inactivity_gap_days | Longest gap, in days, between consecutive play dates inside the 30-day window, also considering the gap from the window start to the first game and from the last game to T | The longest hole in the month, not just the hole at the end | A player who disappears for 18 days and returns once is riskier than a player with the same recency who played evenly |

## Fields on the table that are not model inputs

| Field | Why it is excluded |
| --- | --- |
| churned, games_in_label_window | Outcome. Using them would be leakage |
| city, state, acquisition_campaign | High cardinality. Channel is enough for acquisition quality |
| age, gender | Not part of the gaming behavior brief. Gender is excluded so the scorer is not a demographic screen |
| registration_cohort, tenure_bucket | Analysis cuts. The model sees `player_tenure_days` |
| games_prev_7d and the other `*_prev_7d` components | The change ratios already encode them. Keeping both invites the linear model to split one fact across two coefficients |
| rolling_games_7d | Reconciliation column. It must match `games_7d`. It is not a second feature |
| last_game_date and other last-event dates | The day counts are the model inputs. Raw dates would be memorized |
| rake_rank_in_vip, deposit_dense_rank, rake_quartile | Snapshot-relative ranks. They move when the scored population changes, and they duplicate level information already in rake and deposits |
