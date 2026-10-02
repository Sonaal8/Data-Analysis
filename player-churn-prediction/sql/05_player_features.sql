-- Player-level behavioral features. Thresholds match config/config.yaml
-- decline_rules (games 0.6 / min 3, deposits 0.6 / min 100, sessions 0.6 / min 2,
-- withdrawal-to-deposit 0.8).

DROP TABLE IF EXISTS volatility_metrics;
CREATE TABLE volatility_metrics AS
SELECT
    user_id,
    prediction_date,
    STDDEV_SAMP(games_played) AS game_frequency_std,
    STDDEV_SAMP(deposit_amount) AS deposit_frequency_std
FROM daily_activity
GROUP BY user_id, prediction_date;

DROP TABLE IF EXISTS inactivity_gaps;
CREATE TABLE inactivity_gaps AS
WITH game_days AS (
    SELECT
        b.user_id,
        b.prediction_date,
        b.window_30_start,
        g.game_date
    FROM user_base AS b
    INNER JOIN games AS g
        ON g.user_id = b.user_id
       AND g.game_date >= b.window_30_start
       AND g.game_date < b.prediction_date
    GROUP BY b.user_id, b.prediction_date, b.window_30_start, g.game_date
),
ordered_days AS (
    SELECT
        user_id,
        prediction_date,
        window_30_start,
        game_date,
        LAG(game_date) OVER (
            PARTITION BY user_id, prediction_date
            ORDER BY game_date
        ) AS prev_game_date,
        LEAD(game_date) OVER (
            PARTITION BY user_id, prediction_date
            ORDER BY game_date
        ) AS next_game_date
    FROM game_days
),
gap_rows AS (
    SELECT
        user_id,
        prediction_date,
        CASE
            WHEN prev_game_date IS NULL THEN game_date - window_30_start
            ELSE game_date - prev_game_date
        END AS lag_gap_days,
        CASE
            WHEN next_game_date IS NULL THEN NULL
            ELSE next_game_date - game_date
        END AS lead_gap_days,
        CASE
            WHEN next_game_date IS NULL THEN prediction_date - game_date
            ELSE NULL
        END AS gap_to_prediction
    FROM ordered_days
)
SELECT
    user_id,
    prediction_date,
    GREATEST(
        MAX(lag_gap_days),
        COALESCE(MAX(lead_gap_days), 0),
        COALESCE(MAX(gap_to_prediction), 0)
    ) AS inactivity_gap_days
FROM gap_rows
GROUP BY user_id, prediction_date;

DROP TABLE IF EXISTS rolling_asof;
CREATE TABLE rolling_asof AS
SELECT
    user_id,
    prediction_date,
    rolling_games_7d
FROM daily_activity
WHERE activity_date = prediction_date - 1;

DROP TABLE IF EXISTS player_features;
CREATE TABLE player_features AS
SELECT
    b.user_id,
    b.prediction_date,
    b.dataset_split,
    b.registration_date,
    b.registration_cohort,
    b.player_tenure_days,
    b.tenure_bucket,
    b.age,
    b.gender,
    b.city,
    b.state,
    b.device_type,
    b.acquisition_channel,
    b.acquisition_campaign,
    b.registration_platform,
    b.vip_segment,
    COALESCE(g.games_7d, 0) AS games_7d,
    COALESCE(g.games_prev_7d, 0) AS games_prev_7d,
    COALESCE(g.games_14d, 0) AS games_14d,
    COALESCE(g.games_prev_14d, 0) AS games_prev_14d,
    COALESCE(g.games_30d, 0) AS games_30d,
    COALESCE(g.active_days_7d, 0) AS active_days_7d,
    COALESCE(g.active_days_30d, 0) AS active_days_30d,
    COALESCE(sm.sessions_7d, 0) AS sessions_7d,
    COALESCE(sm.sessions_prev_7d, 0) AS sessions_prev_7d,
    COALESCE(sm.sessions_30d, 0) AS sessions_30d,
    COALESCE(sm.avg_session_duration, 0) AS avg_session_duration,
    COALESCE(g.total_play_time, 0) AS total_play_time,
    CASE
        WHEN COALESCE(g.active_days_30d, 0) = 0 THEN 0
        ELSE g.games_30d * 1.0 / g.active_days_30d
    END AS avg_games_per_active_day,
    b.prediction_date - g.last_game_date AS days_since_last_game,
    CASE
        WHEN sm.last_login_date IS NULL THEN b.player_tenure_days
        ELSE b.prediction_date - sm.last_login_date
    END AS days_since_last_login,
    CASE
        WHEN tm.last_deposit_date IS NULL THEN b.player_tenure_days
        ELSE b.prediction_date - tm.last_deposit_date
    END AS days_since_last_deposit,
    CASE
        WHEN tm.last_withdrawal_date IS NULL THEN b.player_tenure_days
        ELSE b.prediction_date - tm.last_withdrawal_date
    END AS days_since_last_withdrawal,
    CASE WHEN tm.last_deposit_date IS NULL THEN 1 ELSE 0 END AS never_deposited,
    CASE WHEN tm.last_withdrawal_date IS NULL THEN 1 ELSE 0 END AS never_withdrew,
    COALESCE(g.games_30d, 0) * 1.0 / 30.0 AS games_per_day,
    CASE
        WHEN COALESCE(g.active_days_30d, 0) = 0 THEN 0
        ELSE g.games_30d * 1.0 / g.active_days_30d
    END AS games_per_active_day,
    CASE
        WHEN COALESCE(sm.active_session_days_30d, 0) = 0 THEN 0
        ELSE sm.sessions_30d * 1.0 / sm.active_session_days_30d
    END AS sessions_per_active_day,
    COALESCE(tm.deposit_amount_7d, 0) AS deposit_amount_7d,
    COALESCE(tm.deposit_prev_7d, 0) AS deposit_prev_7d,
    COALESCE(tm.deposit_amount_30d, 0) AS deposit_amount_30d,
    COALESCE(tm.withdrawal_amount_30d, 0) AS withdrawal_amount_30d,
    COALESCE(tm.deposit_amount_30d, 0) - COALESCE(tm.withdrawal_amount_30d, 0) AS net_deposit_30d,
    COALESCE(g.rake_7d, 0) AS rake_7d,
    COALESCE(g.rake_prev_7d, 0) AS rake_prev_7d,
    COALESCE(g.rake_30d, 0) AS rake_30d,
    CASE
        WHEN COALESCE(g.games_30d, 0) = 0 THEN 0
        ELSE g.total_entry_fee * 1.0 / g.games_30d
    END AS avg_entry_fee,
    COALESCE(g.total_entry_fee, 0) AS total_entry_fee,
    (COALESCE(g.games_7d, 0) - COALESCE(g.games_prev_7d, 0)) * 1.0
        / (COALESCE(g.games_prev_7d, 0) + 1.0) AS games_change_7d_vs_previous_7d,
    (COALESCE(g.games_14d, 0) - COALESCE(g.games_prev_14d, 0)) * 1.0
        / (COALESCE(g.games_prev_14d, 0) + 1.0) AS games_change_14d_vs_previous_14d,
    (COALESCE(tm.deposit_amount_7d, 0) - COALESCE(tm.deposit_prev_7d, 0)) * 1.0
        / (COALESCE(tm.deposit_prev_7d, 0) + 1.0) AS deposit_change_7d_vs_previous_7d,
    (COALESCE(g.rake_7d, 0) - COALESCE(g.rake_prev_7d, 0)) * 1.0
        / (COALESCE(g.rake_prev_7d, 0) + 1.0) AS rake_change_7d_vs_previous_7d,
    (COALESCE(sm.sessions_7d, 0) - COALESCE(sm.sessions_prev_7d, 0)) * 1.0
        / (COALESCE(sm.sessions_prev_7d, 0) + 1.0) AS session_change_7d_vs_previous_7d,
    COALESCE(v.game_frequency_std, 0) AS game_frequency_std,
    COALESCE(v.deposit_frequency_std, 0) AS deposit_frequency_std,
    COALESCE(sm.session_duration_std, 0) AS session_duration_std,
    COALESCE(g.lifetime_games, 0) AS lifetime_games,
    COALESCE(tm.lifetime_deposit, 0) AS lifetime_deposit,
    COALESCE(g.lifetime_rake, 0) AS lifetime_rake,
    COALESCE(pt.preferred_game_type, 'Unknown') AS preferred_game_type,
    COALESCE(pv.preferred_game_variant, 'Unknown') AS preferred_game_variant,
    CASE
        WHEN COALESCE(g.games_30d, 0) = 0 THEN 0
        ELSE g.tournament_games_30d * 1.0 / g.games_30d
    END AS tournament_affinity,
    CASE
        WHEN COALESCE(g.games_30d, 0) = 0 THEN 0
        ELSE g.pool_games_30d * 1.0 / g.games_30d
    END AS pool_affinity,
    CASE
        WHEN COALESCE(g.games_30d, 0) = 0 THEN 0
        ELSE g.points_games_30d * 1.0 / g.games_30d
    END AS points_affinity,
    CASE
        WHEN COALESCE(g.games_30d, 0) = 0 THEN 0
        ELSE g.deals_games_30d * 1.0 / g.games_30d
    END AS deals_affinity,
    COALESCE(bn.bonus_received_30d, 0) AS bonus_received_30d,
    COALESCE(bn.bonus_used_30d, 0) AS bonus_used_30d,
    COALESCE(tm.cashback_received_30d, 0) AS cashback_received_30d,
    CASE
        WHEN COALESCE(tm.deposit_amount_30d, 0) + COALESCE(bn.bonus_received_30d, 0) = 0 THEN 0
        ELSE bn.bonus_received_30d * 1.0
            / (tm.deposit_amount_30d + bn.bonus_received_30d)
    END AS bonus_dependency_ratio,
    CASE
        WHEN COALESCE(g.games_prev_7d, 0) >= 3
         AND COALESCE(g.games_7d, 0) <= 0.6 * g.games_prev_7d THEN 1
        ELSE 0
    END AS activity_decline_flag,
    CASE
        WHEN COALESCE(tm.deposit_prev_7d, 0) >= 100
         AND COALESCE(tm.deposit_amount_7d, 0) <= 0.6 * tm.deposit_prev_7d THEN 1
        ELSE 0
    END AS deposit_decline_flag,
    CASE
        WHEN COALESCE(sm.sessions_prev_7d, 0) >= 2
         AND COALESCE(sm.sessions_7d, 0) <= 0.6 * sm.sessions_prev_7d THEN 1
        ELSE 0
    END AS reduced_session_flag,
    CASE
        WHEN COALESCE(tm.withdrawal_amount_30d, 0) > 0
         AND COALESCE(tm.deposit_amount_30d, 0) = 0 THEN 1
        WHEN COALESCE(tm.deposit_amount_30d, 0) > 0
         AND tm.withdrawal_amount_30d >= 0.8 * tm.deposit_amount_30d THEN 1
        ELSE 0
    END AS high_withdrawal_to_deposit_ratio,
    COALESCE(ig.inactivity_gap_days, b.prediction_date - g.last_game_date) AS inactivity_gap_days,
    g.last_game_date,
    sm.last_login_date,
    tm.last_deposit_date,
    tm.last_withdrawal_date,
    r.rolling_games_7d
FROM user_base AS b
LEFT JOIN game_metrics AS g
    ON g.user_id = b.user_id
   AND g.prediction_date = b.prediction_date
LEFT JOIN preferred_game_type AS pt
    ON pt.user_id = b.user_id
   AND pt.prediction_date = b.prediction_date
LEFT JOIN preferred_game_variant AS pv
    ON pv.user_id = b.user_id
   AND pv.prediction_date = b.prediction_date
LEFT JOIN transaction_metrics AS tm
    ON tm.user_id = b.user_id
   AND tm.prediction_date = b.prediction_date
LEFT JOIN session_metrics AS sm
    ON sm.user_id = b.user_id
   AND sm.prediction_date = b.prediction_date
LEFT JOIN bonus_metrics AS bn
    ON bn.user_id = b.user_id
   AND bn.prediction_date = b.prediction_date
LEFT JOIN volatility_metrics AS v
    ON v.user_id = b.user_id
   AND v.prediction_date = b.prediction_date
LEFT JOIN inactivity_gaps AS ig
    ON ig.user_id = b.user_id
   AND ig.prediction_date = b.prediction_date
LEFT JOIN rolling_asof AS r
    ON r.user_id = b.user_id
   AND r.prediction_date = b.prediction_date;
