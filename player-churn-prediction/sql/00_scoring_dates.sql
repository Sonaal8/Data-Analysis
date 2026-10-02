-- Scoring calendar for manual DuckDB / PostgreSQL runs.
-- The Python pipeline rebuilds this table from config/config.yaml so the
-- dates stay aligned with training. Window bounds use date +/- integer day
-- arithmetic, which both DuckDB and PostgreSQL support.
--
-- prediction_date is the first day of the OUTCOME window.
-- Features may use only dates strictly before prediction_date.

DROP TABLE IF EXISTS scoring_dates;
CREATE TABLE scoring_dates AS
SELECT
    CAST(prediction_date AS DATE) AS prediction_date,
    CAST(dataset_split AS VARCHAR) AS dataset_split,
    CAST(prediction_date AS DATE) - 7 AS window_7_start,
    CAST(prediction_date AS DATE) - 14 AS window_14_start,
    CAST(prediction_date AS DATE) - 28 AS window_28_start,
    CAST(prediction_date AS DATE) - 30 AS window_30_start,
    CAST(prediction_date AS DATE) + 30 AS label_end
FROM (
    SELECT DATE '2025-04-15' AS prediction_date, 'train' AS dataset_split
    UNION ALL
    SELECT DATE '2025-05-15', 'valid'
    UNION ALL
    SELECT DATE '2025-06-15', 'test'
) AS seeds;
