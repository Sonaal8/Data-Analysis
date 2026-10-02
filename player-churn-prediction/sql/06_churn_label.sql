-- Outcome label. A player is churned when they have no gaming activity on the
-- 30 days starting at prediction_date. This query is the only place that reads
-- games on or after prediction_date, and it does not feed feature columns.

DROP TABLE IF EXISTS churn_labels;
CREATE TABLE churn_labels AS
SELECT
    b.user_id,
    b.prediction_date,
    COALESCE(SUM(g.games_played), 0) AS games_in_label_window,
    CASE
        WHEN COALESCE(SUM(g.games_played), 0) = 0 THEN 1
        ELSE 0
    END AS churned
FROM user_base AS b
LEFT JOIN games AS g
    ON g.user_id = b.user_id
   AND g.game_date >= b.prediction_date
   AND g.game_date < b.label_end
GROUP BY b.user_id, b.prediction_date;
