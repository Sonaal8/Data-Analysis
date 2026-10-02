-- Wallet metrics. Bonus grants are measured from bonuses.csv so a ledger
-- mirror row is not double-counted. Cashback stays on the transaction ledger.

DROP TABLE IF EXISTS transaction_metrics;
CREATE TABLE transaction_metrics AS
SELECT
    b.user_id,
    b.prediction_date,
    COALESCE(SUM(t.amount) FILTER (
        WHERE t.transaction_type = 'deposit'
          AND t.transaction_date >= b.window_7_start
          AND t.transaction_date < b.prediction_date
    ), 0) AS deposit_amount_7d,
    COALESCE(SUM(t.amount) FILTER (
        WHERE t.transaction_type = 'deposit'
          AND t.transaction_date >= b.window_14_start
          AND t.transaction_date < b.window_7_start
    ), 0) AS deposit_prev_7d,
    COALESCE(SUM(t.amount) FILTER (
        WHERE t.transaction_type = 'deposit'
          AND t.transaction_date >= b.window_30_start
          AND t.transaction_date < b.prediction_date
    ), 0) AS deposit_amount_30d,
    COALESCE(SUM(t.amount) FILTER (
        WHERE t.transaction_type = 'withdrawal'
          AND t.transaction_date >= b.window_30_start
          AND t.transaction_date < b.prediction_date
    ), 0) AS withdrawal_amount_30d,
    COALESCE(SUM(t.amount) FILTER (
        WHERE t.transaction_type = 'cashback'
          AND t.transaction_date >= b.window_30_start
          AND t.transaction_date < b.prediction_date
    ), 0) AS cashback_received_30d,
    COALESCE(SUM(t.amount) FILTER (
        WHERE t.transaction_type = 'deposit'
          AND t.transaction_date < b.prediction_date
    ), 0) AS lifetime_deposit,
    MAX(t.transaction_date) FILTER (
        WHERE t.transaction_type = 'deposit'
          AND t.transaction_date < b.prediction_date
    ) AS last_deposit_date,
    MAX(t.transaction_date) FILTER (
        WHERE t.transaction_type = 'withdrawal'
          AND t.transaction_date < b.prediction_date
    ) AS last_withdrawal_date
FROM user_base AS b
LEFT JOIN transactions AS t
    ON t.user_id = b.user_id
   AND t.transaction_date < b.prediction_date
GROUP BY b.user_id, b.prediction_date;

DROP TABLE IF EXISTS session_metrics;
CREATE TABLE session_metrics AS
SELECT
    b.user_id,
    b.prediction_date,
    COUNT(s.session_id) FILTER (
        WHERE s.session_date >= b.window_7_start
          AND s.session_date < b.prediction_date
    ) AS sessions_7d,
    COUNT(s.session_id) FILTER (
        WHERE s.session_date >= b.window_14_start
          AND s.session_date < b.window_7_start
    ) AS sessions_prev_7d,
    COUNT(s.session_id) FILTER (
        WHERE s.session_date >= b.window_30_start
          AND s.session_date < b.prediction_date
    ) AS sessions_30d,
    COUNT(DISTINCT s.session_date) FILTER (
        WHERE s.session_date >= b.window_30_start
          AND s.session_date < b.prediction_date
    ) AS active_session_days_30d,
    AVG(s.session_duration) FILTER (
        WHERE s.session_date >= b.window_30_start
          AND s.session_date < b.prediction_date
    ) AS avg_session_duration,
    STDDEV_SAMP(s.session_duration) FILTER (
        WHERE s.session_date >= b.window_30_start
          AND s.session_date < b.prediction_date
    ) AS session_duration_std,
    MAX(s.session_date) FILTER (
        WHERE s.session_date < b.prediction_date
    ) AS last_login_date
FROM user_base AS b
LEFT JOIN sessions AS s
    ON s.user_id = b.user_id
   AND s.session_date < b.prediction_date
GROUP BY b.user_id, b.prediction_date;

DROP TABLE IF EXISTS bonus_metrics;
CREATE TABLE bonus_metrics AS
SELECT
    b.user_id,
    b.prediction_date,
    COALESCE(SUM(bn.bonus_amount) FILTER (
        WHERE bn.bonus_date >= b.window_30_start
          AND bn.bonus_date < b.prediction_date
    ), 0) AS bonus_received_30d,
    COALESCE(SUM(bn.bonus_amount) FILTER (
        WHERE bn.bonus_date >= b.window_30_start
          AND bn.bonus_date < b.prediction_date
          AND bn.bonus_used_flag = 1
    ), 0) AS bonus_used_30d
FROM user_base AS b
LEFT JOIN bonuses AS bn
    ON bn.user_id = b.user_id
   AND bn.bonus_date < b.prediction_date
GROUP BY b.user_id, b.prediction_date;
