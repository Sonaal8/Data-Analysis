-- Final analytical table. Rank and NTILE columns describe the snapshot;
-- they are not model inputs because they move when the scored population changes.

DROP TABLE IF EXISTS model_dataset;
CREATE TABLE model_dataset AS
SELECT
    f.*,
    c.churned,
    c.games_in_label_window,
    RANK() OVER (
        PARTITION BY f.prediction_date, f.vip_segment
        ORDER BY f.lifetime_rake DESC, f.user_id
    ) AS rake_rank_in_vip,
    DENSE_RANK() OVER (
        PARTITION BY f.prediction_date
        ORDER BY f.lifetime_deposit DESC
    ) AS deposit_dense_rank,
    NTILE(4) OVER (
        PARTITION BY f.prediction_date
        ORDER BY f.lifetime_rake
    ) AS rake_quartile
FROM player_features AS f
INNER JOIN churn_labels AS c
    ON c.user_id = f.user_id
   AND c.prediction_date = f.prediction_date;

DROP TABLE IF EXISTS cohort_summary;
CREATE TABLE cohort_summary AS
SELECT
    registration_cohort,
    dataset_split,
    prediction_date,
    COUNT(*) AS players,
    AVG(churned) AS churn_rate,
    AVG(games_30d) AS avg_games_30d,
    AVG(deposit_amount_30d) AS avg_deposit_30d,
    AVG(days_since_last_game) AS avg_days_since_last_game
FROM model_dataset
GROUP BY registration_cohort, dataset_split, prediction_date;
