-- Daily grain inside each 30-day feature window, including zero-activity days.
-- Rolling sums, LAG, and LEAD are computed here. The rolling 7-day sum on the
-- day before prediction_date must match games_7d from the game aggregate.
--
-- DuckDB generate_series is used for the date spine. PostgreSQL equivalent:
--   SELECT d::date AS activity_date
--   FROM generate_series(DATE '2024-06-01', DATE '2025-07-14', INTERVAL '1 day') AS g(d);

DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date AS
SELECT CAST(d AS DATE) AS activity_date
FROM generate_series(DATE '2024-06-01', DATE '2025-07-14', INTERVAL 1 DAY) AS t(d);

DROP TABLE IF EXISTS game_day;
CREATE TABLE game_day AS
SELECT
    user_id,
    game_date,
    SUM(games_played) AS games_played,
    SUM(rake) AS rake,
    SUM(duration_minutes) AS duration_minutes,
    SUM(entry_fee * games_played) AS entry_fee_total
FROM games
GROUP BY user_id, game_date;

DROP TABLE IF EXISTS session_day;
CREATE TABLE session_day AS
SELECT
    user_id,
    session_date,
    COUNT(*) AS sessions,
    SUM(session_duration) AS session_duration,
    AVG(session_duration) AS avg_session_duration
FROM sessions
GROUP BY user_id, session_date;

DROP TABLE IF EXISTS txn_day;
CREATE TABLE txn_day AS
SELECT
    user_id,
    transaction_date,
    SUM(CASE WHEN transaction_type = 'deposit' THEN amount ELSE 0 END) AS deposit_amount,
    SUM(CASE WHEN transaction_type = 'withdrawal' THEN amount ELSE 0 END) AS withdrawal_amount,
    SUM(CASE WHEN transaction_type = 'cashback' THEN amount ELSE 0 END) AS cashback_amount
FROM transactions
GROUP BY user_id, transaction_date;

DROP TABLE IF EXISTS daily_activity;
CREATE TABLE daily_activity AS
WITH spine AS (
    SELECT
        b.user_id,
        b.prediction_date,
        b.window_30_start,
        d.activity_date
    FROM user_base AS b
    INNER JOIN dim_date AS d
        ON d.activity_date >= b.window_30_start
       AND d.activity_date < b.prediction_date
),
joined AS (
    SELECT
        s.user_id,
        s.prediction_date,
        s.window_30_start,
        s.activity_date,
        COALESCE(g.games_played, 0) AS games_played,
        COALESCE(g.rake, 0) AS rake,
        COALESCE(sd.sessions, 0) AS sessions,
        COALESCE(sd.session_duration, 0) AS session_duration,
        COALESCE(t.deposit_amount, 0) AS deposit_amount,
        COALESCE(t.withdrawal_amount, 0) AS withdrawal_amount
    FROM spine AS s
    LEFT JOIN game_day AS g
        ON g.user_id = s.user_id
       AND g.game_date = s.activity_date
    LEFT JOIN session_day AS sd
        ON sd.user_id = s.user_id
       AND sd.session_date = s.activity_date
    LEFT JOIN txn_day AS t
        ON t.user_id = s.user_id
       AND t.transaction_date = s.activity_date
)
SELECT
    user_id,
    prediction_date,
    window_30_start,
    activity_date,
    games_played,
    rake,
    sessions,
    session_duration,
    deposit_amount,
    withdrawal_amount,
    SUM(games_played) OVER (
        PARTITION BY user_id, prediction_date
        ORDER BY activity_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_games_7d,
    LAG(games_played) OVER (
        PARTITION BY user_id, prediction_date
        ORDER BY activity_date
    ) AS prev_day_games,
    LEAD(games_played) OVER (
        PARTITION BY user_id, prediction_date
        ORDER BY activity_date
    ) AS next_day_games,
    ROW_NUMBER() OVER (
        PARTITION BY user_id, prediction_date
        ORDER BY activity_date
    ) AS day_number
FROM joined;
