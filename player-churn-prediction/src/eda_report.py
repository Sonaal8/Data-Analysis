"""Exploratory figures and rate tables for the June holdout, plus cohort trends.

Charts are saved under reports/figures. The notebook calls the same functions
so the narrative and the files cannot drift.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.config import ProjectConfig, configure_logging, load_config

logger = logging.getLogger(__name__)

HEATMAP_FEATURES = [
    "churned",
    "days_since_last_game",
    "games_30d",
    "active_days_30d",
    "sessions_30d",
    "games_change_7d_vs_previous_7d",
    "deposit_amount_30d",
    "deposit_change_7d_vs_previous_7d",
    "rake_30d",
    "rake_change_7d_vs_previous_7d",
    "lifetime_rake",
    "player_tenure_days",
    "inactivity_gap_days",
    "bonus_dependency_ratio",
    "activity_decline_flag",
]


def _rate_table(df: pd.DataFrame, column: str) -> pd.DataFrame:
    table = (
        df.groupby(column, dropna=False, observed=True)["churned"]
        .agg(players="size", churn_rate="mean")
        .reset_index()
        .sort_values("churn_rate", ascending=False)
    )
    return table


def _bar_rates(table: pd.DataFrame, column: str, title: str, xlabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    plot = table.sort_values("churn_rate", ascending=False)
    sns.barplot(data=plot, x=column, y="churn_rate", color="#1f4e79", ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Churn rate")
    ax.set_ylim(0, min(1.0, float(plot["churn_rate"].max()) * 1.25 + 0.05))
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _bucket(series: pd.Series, edges: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(series, bins=edges, labels=labels, include_lowest=True)


def build_eda(cfg: ProjectConfig | None = None) -> dict[str, Any]:
    """Create EDA tables, figures, and a short insight payload from real rates."""
    configure_logging()
    cfg = cfg or load_config()
    cfg.ensure_directories()
    frame = pd.read_csv(cfg.path("processed_dir") / "churn_dataset.csv")
    holdout = frame.loc[frame["dataset_split"] == "test"].copy()
    if holdout.empty:
        raise RuntimeError("June holdout is empty; EDA has nothing to describe")
    figures = cfg.path("figures_dir")
    aggregates = cfg.path("aggregates_dir")
    sns.set_theme(style="whitegrid", context="notebook")

    holdout["games_bucket"] = _bucket(
        holdout["games_30d"],
        [-0.1, 5, 15, 40, 80, holdout["games_30d"].max() + 1],
        ["1-5", "6-15", "16-40", "41-80", "81+"],
    )
    holdout["deposit_bucket"] = _bucket(
        holdout["deposit_amount_30d"],
        [-0.1, 0, 100, 500, 2000, holdout["deposit_amount_30d"].max() + 1],
        ["None", "1-100", "101-500", "501-2000", "2000+"],
    )
    holdout["withdrawal_bucket"] = _bucket(
        holdout["withdrawal_amount_30d"],
        [-0.1, 0, 100, 1000, holdout["withdrawal_amount_30d"].max() + 1],
        ["None", "1-100", "101-1000", "1000+"],
    )
    holdout["recency_bucket"] = _bucket(
        holdout["days_since_last_game"],
        [-0.1, 1, 3, 7, 14, 30],
        ["0-1", "2-3", "4-7", "8-14", "15-30"],
    )
    holdout["session_bucket"] = _bucket(
        holdout["sessions_30d"],
        [-0.1, 3, 6, 10, 14, holdout["sessions_30d"].max() + 1],
        ["1-3", "4-6", "7-10", "11-14", "15+"],
    )
    holdout["value_bucket"] = pd.qcut(
        holdout["lifetime_rake"].rank(method="first"), 4, labels=["Q1 low rake", "Q2", "Q3", "Q4 high rake"]
    )

    tables = {
        "by_vip": _rate_table(holdout, "vip_segment"),
        "by_channel": _rate_table(holdout, "acquisition_channel"),
        "by_device": _rate_table(holdout, "device_type"),
        "by_game_type": _rate_table(holdout, "preferred_game_type"),
        "by_tenure": _rate_table(holdout, "tenure_bucket"),
        "by_games": _rate_table(holdout, "games_bucket"),
        "by_deposit": _rate_table(holdout, "deposit_bucket"),
        "by_withdrawal": _rate_table(holdout, "withdrawal_bucket"),
        "by_recency": _rate_table(holdout, "recency_bucket"),
        "by_sessions": _rate_table(holdout, "session_bucket"),
        "by_activity_decline": _rate_table(holdout, "activity_decline_flag"),
        "by_value": _rate_table(holdout, "value_bucket"),
    }
    for name, table in tables.items():
        table.to_csv(aggregates / f"{name}.csv", index=False)

    _bar_rates(tables["by_vip"], "vip_segment", "June churn rate by VIP segment", "VIP segment", figures / "churn_by_vip.png")
    _bar_rates(tables["by_channel"], "acquisition_channel", "June churn rate by acquisition channel", "Channel", figures / "churn_by_channel.png")
    _bar_rates(tables["by_device"], "device_type", "June churn rate by device", "Device", figures / "churn_by_device.png")
    _bar_rates(tables["by_game_type"], "preferred_game_type", "June churn rate by preferred game type", "Game type", figures / "churn_by_game_type.png")
    _bar_rates(tables["by_tenure"], "tenure_bucket", "June churn rate by tenure", "Tenure (days)", figures / "churn_by_tenure.png")
    _bar_rates(tables["by_games"], "games_bucket", "June churn rate by games in the last 30 days", "Games played", figures / "churn_by_games.png")
    _bar_rates(tables["by_deposit"], "deposit_bucket", "June churn rate by 30-day deposit amount", "Deposit bucket", figures / "churn_by_deposit.png")
    _bar_rates(tables["by_withdrawal"], "withdrawal_bucket", "June churn rate by 30-day withdrawal amount", "Withdrawal bucket", figures / "churn_by_withdrawal.png")
    _bar_rates(tables["by_recency"], "recency_bucket", "June churn rate by days since last game", "Days since last game", figures / "churn_by_recency.png")
    _bar_rates(tables["by_sessions"], "session_bucket", "June churn rate by sessions in 30 days", "Sessions", figures / "churn_by_sessions.png")
    _bar_rates(
        tables["by_activity_decline"],
        "activity_decline_flag",
        "June churn rate by activity-decline flag",
        "Activity decline flag",
        figures / "churn_by_activity_decline.png",
    )
    _bar_rates(tables["by_value"], "value_bucket", "June churn rate by lifetime-rake quartile", "Player value", figures / "churn_by_value.png")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.boxplot(data=holdout, x="churned", y="days_since_last_game", ax=ax, color="#7aa2c4")
    ax.set_title("Days since last game by June outcome")
    ax.set_xlabel("Churned (1 = no games in the next 30 days)")
    ax.set_ylabel("Days since last game")
    fig.tight_layout()
    fig.savefig(figures / "recency_boxplot.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.histplot(data=holdout, x="games_30d", hue="churned", bins=30, element="step", stat="density", common_norm=False, ax=ax)
    ax.set_title("Distribution of 30-day games by outcome")
    ax.set_xlabel("Games in the 30 days before the prediction date")
    ax.set_ylabel("Density")
    fig.tight_layout()
    fig.savefig(figures / "games_distribution_by_churn.png", dpi=140)
    plt.close(fig)

    corr = holdout[HEATMAP_FEATURES].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(corr, cmap="RdBu_r", center=0, ax=ax)
    ax.set_title("Correlation of behavior features with June churn")
    fig.tight_layout()
    fig.savefig(figures / "correlation_heatmap.png", dpi=140)
    plt.close(fig)
    corr.to_csv(aggregates / "correlation_matrix.csv")

    cohort = (
        frame.groupby(["dataset_split", "registration_cohort"], observed=True)["churned"]
        .mean()
        .reset_index()
    )
    cohort_pivot = cohort.pivot(index="registration_cohort", columns="dataset_split", values="churned")
    cohort_pivot = cohort_pivot.reindex(columns=["train", "valid", "test"])
    cohort_pivot.to_csv(aggregates / "cohort_churn_by_snapshot.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(cohort_pivot, cmap="YlOrRd", ax=ax, vmin=0, vmax=max(0.45, float(np.nanmax(cohort_pivot.to_numpy()))))
    ax.set_title("Churn rate by registration cohort and scoring snapshot")
    ax.set_xlabel("Snapshot")
    ax.set_ylabel("Registration cohort")
    fig.tight_layout()
    fig.savefig(figures / "cohort_churn_heatmap.png", dpi=140)
    plt.close(fig)

    overall = float(holdout["churned"].mean())

    def _extreme(table: pd.DataFrame, column: str) -> dict[str, Any]:
        ordered = table.sort_values("churn_rate", ascending=False)
        top = ordered.iloc[0]
        bottom = ordered.iloc[-1]
        return {
            "highest": {column: str(top[column]), "churn_rate": float(top["churn_rate"]), "players": int(top["players"])},
            "lowest": {column: str(bottom[column]), "churn_rate": float(bottom["churn_rate"]), "players": int(bottom["players"])},
        }

    insights = {
        "holdout_players": int(len(holdout)),
        "holdout_churn_rate": overall,
        "vip": _extreme(tables["by_vip"], "vip_segment"),
        "channel": _extreme(tables["by_channel"], "acquisition_channel"),
        "device": _extreme(tables["by_device"], "device_type"),
        "game_type": _extreme(tables["by_game_type"], "preferred_game_type"),
        "tenure": _extreme(tables["by_tenure"], "tenure_bucket"),
        "games": _extreme(tables["by_games"], "games_bucket"),
        "deposit": _extreme(tables["by_deposit"], "deposit_bucket"),
        "withdrawal": _extreme(tables["by_withdrawal"], "withdrawal_bucket"),
        "recency": _extreme(tables["by_recency"], "recency_bucket"),
        "sessions": _extreme(tables["by_sessions"], "session_bucket"),
        "activity_decline": tables["by_activity_decline"].to_dict(orient="records"),
        "value": _extreme(tables["by_value"], "value_bucket"),
        "corr_days_since_last_game": float(corr.loc["days_since_last_game", "churned"]),
        "corr_games_30d": float(corr.loc["games_30d", "churned"]),
        "corr_games_change": float(corr.loc["games_change_7d_vs_previous_7d", "churned"]),
        "corr_active_days_30d": float(corr.loc["active_days_30d", "churned"]),
    }
    (aggregates / "eda_insights.json").write_text(json.dumps(insights, indent=2), encoding="utf-8")
    logger.info("EDA written. June churn rate %.3f on %s players", overall, f"{len(holdout):,}")
    return insights


def main() -> None:
    build_eda(load_config())


if __name__ == "__main__":
    main()
