-- Game aggregates. Every predicate is game_date < prediction_date.
-- Outcome-window games are intentionally invisible to this query.

DROP TABLE IF EXISTS game_window;
CREATE TABLE game_window AS
SELECT
    b.user_id,
    b.prediction_date,
    b.window_7_start,
    b.window_14_start,
    b.window_28_start,
    b.window_30_start,
    g.game_date,
    g.game_type,
    g.game_variant,
    g.games_played,
    g.duration_minutes,
    g.rake,
    g.entry_fee,
    g.tournament_flag
FROM user_base AS b
INNER JOIN games AS g
    ON g.user_id = b.user_id
   AND g.game_date < b.prediction_date;

DROP TABLE IF EXISTS game_metrics;
CREATE TABLE game_metrics AS
SELECT
    user_id,
    prediction_date,
    SUM(games_played) FILTER (WHERE game_date >= window_7_start) AS games_7d,
    SUM(games_played) FILTER (
        WHERE game_date >= window_14_start AND game_date < window_7_start
    ) AS games_prev_7d,
    SUM(games_played) FILTER (WHERE game_date >= window_14_start) AS games_14d,
    SUM(games_played) FILTER (
        WHERE game_date >= window_28_start AND game_date < window_14_start
    ) AS games_prev_14d,
    SUM(games_played) FILTER (WHERE game_date >= window_30_start) AS games_30d,
    COUNT(DISTINCT game_date) FILTER (WHERE game_date >= window_7_start) AS active_days_7d,
    COUNT(DISTINCT game_date) FILTER (WHERE game_date >= window_30_start) AS active_days_30d,
    SUM(duration_minutes) FILTER (WHERE game_date >= window_30_start) AS total_play_time,
    SUM(rake) FILTER (WHERE game_date >= window_7_start) AS rake_7d,
    SUM(rake) FILTER (
        WHERE game_date >= window_14_start AND game_date < window_7_start
    ) AS rake_prev_7d,
    SUM(rake) FILTER (WHERE game_date >= window_30_start) AS rake_30d,
    SUM(entry_fee * games_played) FILTER (WHERE game_date >= window_30_start) AS total_entry_fee,
    SUM(games_played) AS lifetime_games,
    SUM(rake) AS lifetime_rake,
    MAX(game_date) AS last_game_date,
    SUM(games_played) FILTER (
        WHERE game_date >= window_30_start AND game_type = 'Pool Rummy'
    ) AS pool_games_30d,
    SUM(games_played) FILTER (
        WHERE game_date >= window_30_start AND game_type = 'Points Rummy'
    ) AS points_games_30d,
    SUM(games_played) FILTER (
        WHERE game_date >= window_30_start AND game_type = 'Deals Rummy'
    ) AS deals_games_30d,
    SUM(games_played) FILTER (
        WHERE game_date >= window_30_start AND tournament_flag = 1
    ) AS tournament_games_30d
FROM game_window
GROUP BY user_id, prediction_date;

DROP TABLE IF EXISTS preferred_game_type;
CREATE TABLE preferred_game_type AS
WITH counts AS (
    SELECT
        user_id,
        prediction_date,
        game_type,
        SUM(games_played) AS games_played
    FROM game_window
    WHERE game_date >= window_30_start
    GROUP BY user_id, prediction_date, game_type
),
ranked AS (
    SELECT
        user_id,
        prediction_date,
        game_type,
        games_played,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, prediction_date
            ORDER BY games_played DESC, game_type
        ) AS type_row_number,
        RANK() OVER (
            PARTITION BY user_id, prediction_date
            ORDER BY games_played DESC
        ) AS type_rank,
        DENSE_RANK() OVER (
            PARTITION BY user_id, prediction_date
            ORDER BY games_played DESC
        ) AS type_dense_rank
    FROM counts
)
SELECT
    user_id,
    prediction_date,
    game_type AS preferred_game_type,
    type_rank,
    type_dense_rank
FROM ranked
WHERE type_row_number = 1;

DROP TABLE IF EXISTS preferred_game_variant;
CREATE TABLE preferred_game_variant AS
WITH counts AS (
    SELECT
        user_id,
        prediction_date,
        game_variant,
        SUM(games_played) AS games_played
    FROM game_window
    WHERE game_date >= window_30_start
    GROUP BY user_id, prediction_date, game_variant
),
ranked AS (
    SELECT
        user_id,
        prediction_date,
        game_variant,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, prediction_date
            ORDER BY games_played DESC, game_variant
        ) AS variant_row_number
    FROM counts
)
SELECT
    user_id,
    prediction_date,
    game_variant AS preferred_game_variant
FROM ranked
WHERE variant_row_number = 1;
