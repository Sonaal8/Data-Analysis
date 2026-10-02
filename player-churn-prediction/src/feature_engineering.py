"""Build the player-level modeling table by executing the warehouse SQL.

Feature logic lives in ``sql/`` so the Python path and the documented SQL stay
the same queries. All feature predicates require ``event_date < prediction_date``.
The churn label is attached afterwards from the outcome window only.

This project uses synthetic data inspired by common online gaming analytics
use cases. It does not contain confidential or proprietary Junglee Games data.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import duckdb
import pandas as pd

from src.config import ProjectConfig, configure_logging, load_config

logger = logging.getLogger(__name__)

SQL_FILES: tuple[str, ...] = (
    "01_user_base.sql",
    "02_daily_activity.sql",
    "03_game_metrics.sql",
    "04_transaction_metrics.sql",
    "05_player_features.sql",
    "06_churn_label.sql",
    "07_model_dataset.sql",
)

LABEL_COLUMNS = ("churned", "games_in_label_window")


def _sql_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def connect(cfg: ProjectConfig) -> duckdb.DuckDBPyConnection:
    """Open a file-backed DuckDB database so intermediates can spill to disk."""
    db_path = cfg.path("processed_dir") / "churn.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute("SET threads=2")
    con.execute("SET memory_limit='3GB'")
    con.execute("SET preserve_insertion_order=false")
    return con


def load_raw_tables(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> None:
    """Load raw CSVs into typed tables. Dates are parsed; blank strings become NULL."""
    required = ("users.csv", "games.csv", "transactions.csv", "sessions.csv", "bonuses.csv")
    for name in required:
        if not (raw_dir / name).exists():
            raise FileNotFoundError(
                f"Missing {raw_dir / name}. Generate it with `python -m src.data_generation`."
            )
    raw = _sql_literal(raw_dir)
    con.execute(
        f"""
        CREATE TABLE users AS
        SELECT
            user_id::BIGINT AS user_id,
            registration_date::DATE AS registration_date,
            age::INTEGER AS age,
            NULLIF(gender, '') AS gender,
            city,
            state,
            device_type,
            acquisition_channel,
            acquisition_campaign,
            registration_platform,
            vip_segment
        FROM read_csv('{raw}/users.csv', header=true, dateformat='%Y-%m-%d', nullstr='')
        """
    )
    con.execute(
        f"""
        CREATE TABLE games AS
        SELECT
            game_id::BIGINT AS game_id,
            user_id::BIGINT AS user_id,
            game_date::DATE AS game_date,
            game_type,
            game_variant,
            entry_fee::DOUBLE AS entry_fee,
            game_result,
            games_played::BIGINT AS games_played,
            duration_minutes::DOUBLE AS duration_minutes,
            rake::DOUBLE AS rake,
            tournament_flag::INTEGER AS tournament_flag
        FROM read_csv('{raw}/games.csv', header=true, dateformat='%Y-%m-%d')
        """
    )
    con.execute(
        f"""
        CREATE TABLE transactions AS
        SELECT
            transaction_id::BIGINT AS transaction_id,
            user_id::BIGINT AS user_id,
            transaction_date::DATE AS transaction_date,
            transaction_type,
            amount::DOUBLE AS amount
        FROM read_csv('{raw}/transactions.csv', header=true, dateformat='%Y-%m-%d')
        """
    )
    con.execute(
        f"""
        CREATE TABLE sessions AS
        SELECT
            session_id::BIGINT AS session_id,
            user_id::BIGINT AS user_id,
            session_date::DATE AS session_date,
            session_duration::DOUBLE AS session_duration,
            login_count::INTEGER AS login_count,
            NULLIF(app_version, '') AS app_version,
            device_type
        FROM read_csv('{raw}/sessions.csv', header=true, dateformat='%Y-%m-%d', nullstr='')
        """
    )
    con.execute(
        f"""
        CREATE TABLE bonuses AS
        SELECT
            bonus_id::BIGINT AS bonus_id,
            user_id::BIGINT AS user_id,
            bonus_date::DATE AS bonus_date,
            bonus_type,
            bonus_amount::DOUBLE AS bonus_amount,
            bonus_used_flag::INTEGER AS bonus_used_flag
        FROM read_csv('{raw}/bonuses.csv', header=true, dateformat='%Y-%m-%d')
        """
    )


def create_scoring_dates(con: duckdb.DuckDBPyConnection, cfg: ProjectConfig) -> None:
    """Build the scoring calendar from config so SQL windows cannot drift."""
    rows = []
    for split, prediction_date in cfg.prediction_dates.items():
        rows.append(f"(DATE '{prediction_date.isoformat()}', '{split}')")
    values = ",\n".join(rows)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE scoring_dates AS
        SELECT
            CAST(prediction_date AS DATE) AS prediction_date,
            CAST(dataset_split AS VARCHAR) AS dataset_split,
            CAST(prediction_date AS DATE) - 7 AS window_7_start,
            CAST(prediction_date AS DATE) - 14 AS window_14_start,
            CAST(prediction_date AS DATE) - 28 AS window_28_start,
            CAST(prediction_date AS DATE) - 30 AS window_30_start,
            CAST(prediction_date AS DATE) + {int(cfg.label_days)} AS label_end
        FROM (
            SELECT * FROM (VALUES {values}) AS seeds(prediction_date, dataset_split)
        )
        """
    )
    if cfg.feature_days != 30:
        raise ValueError("SQL feature windows are defined as 30 days; config feature_days must be 30")


def execute_sql_files(con: duckdb.DuckDBPyConnection, sql_dir: Path, files: tuple[str, ...] = SQL_FILES) -> None:
    """Run the feature SQL in order. Each file may contain multiple statements."""
    for name in files:
        path = sql_dir / name
        if not path.exists():
            raise FileNotFoundError(path)
        logger.info("Running %s", name)
        con.execute(path.read_text(encoding="utf-8"))


def validate_dataset(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Fail closed if labels leak into features or window definitions disagree."""
    rolling_gap = con.execute(
        """
        SELECT MAX(ABS(games_7d - rolling_games_7d))
        FROM player_features
        WHERE rolling_games_7d IS NOT NULL
        """
    ).fetchone()[0]
    if rolling_gap is None or float(rolling_gap) > 1e-6:
        raise RuntimeError(f"games_7d does not match the rolling 7-day sum (max gap={rolling_gap})")

    lifetime_mismatch = con.execute(
        """
        WITH recomputed AS (
            SELECT
                b.user_id,
                b.prediction_date,
                COALESCE(SUM(g.games_played), 0) AS lifetime_games
            FROM user_base AS b
            LEFT JOIN games AS g
                ON g.user_id = b.user_id
               AND g.game_date < b.prediction_date
            GROUP BY b.user_id, b.prediction_date
        )
        SELECT COUNT(*)
        FROM model_dataset AS m
        INNER JOIN recomputed AS r
            ON r.user_id = m.user_id
           AND r.prediction_date = m.prediction_date
        WHERE m.lifetime_games <> r.lifetime_games
        """
    ).fetchone()[0]
    if int(lifetime_mismatch) != 0:
        raise RuntimeError(f"Lifetime games include or drop rows incorrectly ({lifetime_mismatch} mismatches)")

    label_mismatch = con.execute(
        """
        WITH recomputed AS (
            SELECT
                b.user_id,
                b.prediction_date,
                COALESCE(SUM(g.games_played), 0) AS games_in_label_window
            FROM user_base AS b
            LEFT JOIN games AS g
                ON g.user_id = b.user_id
               AND g.game_date >= b.prediction_date
               AND g.game_date < b.label_end
            GROUP BY b.user_id, b.prediction_date
        )
        SELECT COUNT(*)
        FROM model_dataset AS m
        INNER JOIN recomputed AS r
            ON r.user_id = m.user_id
           AND r.prediction_date = m.prediction_date
        WHERE m.games_in_label_window <> r.games_in_label_window
        """
    ).fetchone()[0]
    if int(label_mismatch) != 0:
        raise RuntimeError(f"Churn label window does not match raw games ({label_mismatch} mismatches)")

    future_in_features = con.execute(
        """
        SELECT COUNT(*)
        FROM model_dataset
        WHERE last_game_date >= prediction_date
           OR (last_deposit_date IS NOT NULL AND last_deposit_date >= prediction_date)
           OR (last_login_date IS NOT NULL AND last_login_date >= prediction_date)
        """
    ).fetchone()[0]
    if int(future_in_features) != 0:
        raise RuntimeError("Feature recency columns include outcome-window dates")

    summary = con.execute(
        """
        SELECT
            dataset_split,
            COUNT(*) AS players,
            AVG(churned) AS churn_rate,
            corr(days_since_last_game, churned) AS corr_recency,
            corr(games_30d, churned) AS corr_games_30d,
            corr(games_change_7d_vs_previous_7d, churned) AS corr_games_change,
            corr(active_days_30d, churned) AS corr_active_days,
            AVG(days_since_last_game) AS avg_recency,
            AVG(games_30d) AS avg_games_30d
        FROM model_dataset
        GROUP BY dataset_split
        ORDER BY MIN(prediction_date)
        """
    ).fetchdf()
    logger.info("Snapshot summary:\n%s", summary.to_string(index=False))
    return summary


def export_datasets(con: duckdb.DuckDBPyConnection, cfg: ProjectConfig) -> None:
    """Write the full modeling extracts (gitignored) and small committed samples."""
    processed = cfg.path("processed_dir")
    samples = cfg.path("sample_dir")
    aggregates = cfg.path("aggregates_dir")
    dataset_path = processed / "churn_dataset.csv"
    features_path = processed / "player_features.csv"
    con.execute(
        f"COPY model_dataset TO '{_sql_literal(dataset_path)}' (HEADER, DELIMITER ',')"
    )
    con.execute(
        f"""
        COPY (
            SELECT * EXCLUDE (churned, games_in_label_window)
            FROM model_dataset
        ) TO '{_sql_literal(features_path)}' (HEADER, DELIMITER ',')
        """
    )
    con.execute(
        f"""
        COPY (
            SELECT * FROM model_dataset
            WHERE dataset_split = 'test' AND user_id % 47 = 0
            ORDER BY user_id
            LIMIT 5000
        ) TO '{_sql_literal(samples / 'churn_dataset_sample.csv')}' (HEADER, DELIMITER ',')
        """
    )
    con.execute(
        f"""
        COPY (
            SELECT * EXCLUDE (churned, games_in_label_window)
            FROM model_dataset
            WHERE dataset_split = 'test' AND user_id % 47 = 0
            ORDER BY user_id
            LIMIT 5000
        ) TO '{_sql_literal(samples / 'player_features_sample.csv')}' (HEADER, DELIMITER ',')
        """
    )
    con.execute(
        f"COPY cohort_summary TO '{_sql_literal(aggregates / 'cohort_summary.csv')}' (HEADER, DELIMITER ',')"
    )
    raw = cfg.path("raw_dir")
    for name in ("users", "games", "transactions", "sessions", "bonuses"):
        con.execute(
            f"""
            COPY (
                SELECT * FROM {name}
                USING SAMPLE 1500
            ) TO '{_sql_literal(samples / f'{name}_sample.csv')}' (HEADER, DELIMITER ',')
            """
        )
    logger.info("Wrote %s and %s", dataset_path.name, features_path.name)


def build_features(cfg: ProjectConfig | None = None) -> pd.DataFrame:
    """Run the full feature build and return the snapshot summary."""
    configure_logging()
    cfg = cfg or load_config()
    cfg.ensure_directories()
    logger.info("Building features from %s", cfg.path("raw_dir"))
    con = connect(cfg)
    try:
        load_raw_tables(con, cfg.path("raw_dir"))
        create_scoring_dates(con, cfg)
        execute_sql_files(con, cfg.path("sql_dir"))
        summary = validate_dataset(con)
        export_datasets(con, cfg)
        summary_path = cfg.path("aggregates_dir") / "snapshot_summary.csv"
        summary.to_csv(summary_path, index=False)
        meta = {
            "rows": int(con.execute("SELECT COUNT(*) FROM model_dataset").fetchone()[0]),
            "columns": [row[0] for row in con.execute("DESCRIBE model_dataset").fetchall()],
            "disclaimer": (
                "This project uses synthetic data inspired by common online gaming analytics "
                "use cases. It does not contain confidential or proprietary Junglee Games data."
            ),
        }
        (cfg.path("processed_dir") / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        test_rate = summary.loc[summary["dataset_split"] == "test", "churn_rate"]
        if test_rate.empty:
            raise RuntimeError("Test snapshot is empty")
        rate = float(test_rate.iloc[0])
        if not 0.15 <= rate <= 0.30:
            logger.warning("Test churn rate %.3f is outside the 15-30%% design range", rate)
        else:
            logger.info("Test churn rate %.3f is inside the design range", rate)
        return summary
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build player features and churn labels")
    parser.parse_args()
    build_features(load_config())


if __name__ == "__main__":
    main()
