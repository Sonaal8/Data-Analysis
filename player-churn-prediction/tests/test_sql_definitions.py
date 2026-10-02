"""Lock the feature and label definitions on a hand-computed fixture.

The fixture includes games after the prediction date. Those rows may change
only the label, never a feature.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.feature_engineering import SQL_FILES, execute_sql_files  # noqa: E402


def _load_fixture(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE users (
            user_id BIGINT, registration_date DATE, age INTEGER, gender VARCHAR,
            city VARCHAR, state VARCHAR, device_type VARCHAR, acquisition_channel VARCHAR,
            acquisition_campaign VARCHAR, registration_platform VARCHAR, vip_segment VARCHAR
        );
        INSERT INTO users VALUES
            (1, DATE '2025-01-01', 29, 'Female', 'Pune', 'Maharashtra', 'Android', 'Referral', 'REFERRAL_FRIEND50', 'Android', 'Gold'),
            (2, DATE '2025-01-01', 29, 'Female', 'Pune', 'Maharashtra', 'Android', 'Referral', 'REFERRAL_FRIEND50', 'Android', 'Gold'),
            (3, DATE '2025-01-01', 41, 'Male', 'Delhi', 'Delhi', 'iOS', 'Organic', 'ORGANIC_DIRECT', 'iOS', 'Regular');

        CREATE TABLE games (
            game_id BIGINT, user_id BIGINT, game_date DATE, game_type VARCHAR, game_variant VARCHAR,
            entry_fee DOUBLE, game_result VARCHAR, games_played BIGINT, duration_minutes DOUBLE,
            rake DOUBLE, tournament_flag INTEGER
        );
        INSERT INTO games VALUES
            (1, 1, DATE '2025-05-20', 'Pool Rummy', '101 Pool', 50, 'loss', 4, 20, 10, 0),
            (2, 1, DATE '2025-06-01', 'Points Rummy', '0.10 per point', 25, 'win', 2, 10, 5, 0),
            (3, 1, DATE '2025-06-10', 'Points Rummy', '1 per point', 100, 'loss', 6, 30, 12, 0),
            (4, 1, DATE '2025-06-20', 'Deals Rummy', 'Best of 3', 80, 'win', 8, 40, 20, 0),
            (5, 2, DATE '2025-05-20', 'Pool Rummy', '101 Pool', 50, 'loss', 4, 20, 10, 0),
            (6, 2, DATE '2025-06-01', 'Points Rummy', '0.10 per point', 25, 'win', 2, 10, 5, 0),
            (7, 2, DATE '2025-06-10', 'Points Rummy', '1 per point', 100, 'loss', 6, 30, 12, 0),
            (8, 3, DATE '2025-04-01', 'Points Rummy', '0.10 per point', 10, 'loss', 3, 12, 2, 0);

        CREATE TABLE transactions (
            transaction_id BIGINT, user_id BIGINT, transaction_date DATE,
            transaction_type VARCHAR, amount DOUBLE
        );
        INSERT INTO transactions VALUES
            (1, 1, DATE '2025-05-25', 'deposit', 100),
            (2, 1, DATE '2025-06-12', 'deposit', 200),
            (3, 1, DATE '2025-06-11', 'withdrawal', 80),
            (4, 1, DATE '2025-06-09', 'cashback', 10),
            (5, 1, DATE '2025-06-25', 'deposit', 999),
            (6, 2, DATE '2025-05-25', 'deposit', 100),
            (7, 2, DATE '2025-06-12', 'deposit', 200),
            (8, 2, DATE '2025-06-11', 'withdrawal', 80),
            (9, 2, DATE '2025-06-09', 'cashback', 10);

        CREATE TABLE sessions (
            session_id BIGINT, user_id BIGINT, session_date DATE, session_duration DOUBLE,
            login_count INTEGER, app_version VARCHAR, device_type VARCHAR
        );
        INSERT INTO sessions VALUES
            (1, 1, DATE '2025-05-20', 25, 1, '5.6.1', 'Android'),
            (2, 1, DATE '2025-06-01', 15, 1, '6.0.0', 'Android'),
            (3, 1, DATE '2025-06-10', 40, 2, '6.0.0', 'Android'),
            (4, 1, DATE '2025-06-21', 50, 1, '6.0.0', 'Android'),
            (5, 2, DATE '2025-05-20', 25, 1, '5.6.1', 'Android'),
            (6, 2, DATE '2025-06-01', 15, 1, '6.0.0', 'Android'),
            (7, 2, DATE '2025-06-10', 40, 2, '6.0.0', 'Android');

        CREATE TABLE bonuses (
            bonus_id BIGINT, user_id BIGINT, bonus_date DATE, bonus_type VARCHAR,
            bonus_amount DOUBLE, bonus_used_flag INTEGER
        );
        INSERT INTO bonuses VALUES
            (1, 1, DATE '2025-06-05', 'Reload', 50, 1),
            (2, 2, DATE '2025-06-05', 'Reload', 50, 1),
            (3, 1, DATE '2025-06-22', 'Reload', 500, 1);

        CREATE TABLE scoring_dates AS
        SELECT
            DATE '2025-06-15' AS prediction_date,
            'test' AS dataset_split,
            DATE '2025-06-15' - 7 AS window_7_start,
            DATE '2025-06-15' - 14 AS window_14_start,
            DATE '2025-06-15' - 28 AS window_28_start,
            DATE '2025-06-15' - 30 AS window_30_start,
            DATE '2025-06-15' + 30 AS label_end;
        """
    )


def test_feature_windows_ignore_future_activity() -> None:
    con = duckdb.connect()
    _load_fixture(con)
    execute_sql_files(con, ROOT / "sql", SQL_FILES)
    frame = con.execute(
        """
        SELECT * FROM model_dataset ORDER BY user_id
        """
    ).fetchdf()
    assert set(frame["user_id"]) == {1, 2}
    user1 = frame.loc[frame["user_id"] == 1].iloc[0]
    user2 = frame.loc[frame["user_id"] == 2].iloc[0]

    assert pd.Timestamp(user1["prediction_date"]).date() == date(2025, 6, 15)
    assert int(user1["games_7d"]) == 6
    assert int(user1["games_prev_7d"]) == 2
    assert int(user1["games_14d"]) == 8
    assert int(user1["games_prev_14d"]) == 4
    assert int(user1["games_30d"]) == 12
    assert int(user1["active_days_7d"]) == 1
    assert int(user1["active_days_30d"]) == 3
    assert int(user1["days_since_last_game"]) == 5
    assert int(user1["lifetime_games"]) == 12
    assert user1["lifetime_rake"] == pytest.approx(27)
    assert user1["total_entry_fee"] == pytest.approx(850)
    assert user1["avg_entry_fee"] == pytest.approx(850 / 12)
    assert int(user1["sessions_7d"]) == 1
    assert int(user1["sessions_30d"]) == 3
    assert user1["avg_session_duration"] == pytest.approx((25 + 15 + 40) / 3)
    assert user1["deposit_amount_7d"] == pytest.approx(200)
    assert user1["deposit_amount_30d"] == pytest.approx(300)
    assert user1["withdrawal_amount_30d"] == pytest.approx(80)
    assert user1["net_deposit_30d"] == pytest.approx(220)
    assert user1["lifetime_deposit"] == pytest.approx(300)
    assert user1["cashback_received_30d"] == pytest.approx(10)
    assert int(user1["days_since_last_deposit"]) == 3
    assert int(user1["days_since_last_withdrawal"]) == 4
    assert user1["bonus_received_30d"] == pytest.approx(50)
    assert user1["bonus_used_30d"] == pytest.approx(50)
    assert user1["bonus_dependency_ratio"] == pytest.approx(50 / 350)
    assert user1["games_change_7d_vs_previous_7d"] == pytest.approx(4 / 3)
    assert int(user1["activity_decline_flag"]) == 0
    assert user1["preferred_game_type"] == "Points Rummy"
    assert user1["points_affinity"] == pytest.approx(8 / 12)
    assert user1["pool_affinity"] == pytest.approx(4 / 12)
    assert int(user1["inactivity_gap_days"]) == 12
    assert int(user1["player_tenure_days"]) == 165
    assert int(user1["churned"]) == 0
    assert int(user1["games_in_label_window"]) == 8
    assert user1["rolling_games_7d"] == pytest.approx(6)
    assert pd.Timestamp(user1["last_game_date"]).date() == date(2025, 6, 10)

    # Same history, no outcome-window play: features match, label flips.
    feature_cols = [
        "games_7d",
        "games_30d",
        "lifetime_games",
        "days_since_last_game",
        "deposit_amount_30d",
        "sessions_30d",
        "rake_30d",
        "bonus_received_30d",
    ]
    for col in feature_cols:
        assert user1[col] == pytest.approx(user2[col])
    assert int(user2["churned"]) == 1
    assert int(user2["games_in_label_window"]) == 0
    assert int(user2["lifetime_games"]) == 12
