-- Eligible scoring population.
-- A player is scored on a snapshot only when they registered before the
-- prediction date AND played at least one game in the prior 30 days.
-- Already-silent players are a reactivation list, not this model's book.

DROP TABLE IF EXISTS user_base;
CREATE TABLE user_base AS
WITH dated AS (
    SELECT
        u.user_id,
        u.registration_date,
        u.age,
        u.gender,
        u.city,
        u.state,
        u.device_type,
        u.acquisition_channel,
        u.acquisition_campaign,
        u.registration_platform,
        u.vip_segment,
        s.prediction_date,
        s.dataset_split,
        s.window_7_start,
        s.window_14_start,
        s.window_28_start,
        s.window_30_start,
        s.label_end,
        s.prediction_date - u.registration_date AS player_tenure_days,
        CAST(date_trunc('month', u.registration_date) AS DATE) AS registration_cohort
    FROM users AS u
    CROSS JOIN scoring_dates AS s
    WHERE u.registration_date < s.prediction_date
),
eligible AS (
    SELECT
        d.user_id,
        d.prediction_date
    FROM dated AS d
    WHERE EXISTS (
        SELECT 1
        FROM games AS g
        WHERE g.user_id = d.user_id
          AND g.game_date >= d.window_30_start
          AND g.game_date < d.prediction_date
    )
)
SELECT
    d.*,
    CASE
        WHEN d.player_tenure_days <= 30 THEN '0-30'
        WHEN d.player_tenure_days <= 90 THEN '31-90'
        WHEN d.player_tenure_days <= 180 THEN '91-180'
        WHEN d.player_tenure_days <= 365 THEN '181-365'
        ELSE '365+'
    END AS tenure_bucket
FROM dated AS d
INNER JOIN eligible AS e
    ON e.user_id = d.user_id
   AND e.prediction_date = d.prediction_date;
