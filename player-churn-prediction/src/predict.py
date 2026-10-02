"""Score the latest snapshot and attach risk bands, drivers, and actions.

Scoring reads the saved champion. It does not retrain. Drivers and segments
are joined when those artifacts exist; actions still run without them.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import joblib
import pandas as pd

from src.config import ProjectConfig, configure_logging, load_config
from src.preprocessing import model_feature_frame
from src.retention_engine import assign_risk_band, recommend_actions

logger = logging.getLogger(__name__)

SCORE_COLUMNS = [
    "user_id",
    "prediction_date",
    "churn_probability",
    "churned_holdout",
    "risk_band",
    "segment",
    "top_risk_driver_1",
    "top_risk_driver_2",
    "top_risk_driver_3",
    "recommended_action",
    "vip_segment",
    "acquisition_channel",
    "device_type",
    "preferred_game_type",
    "tenure_bucket",
    "games_30d",
    "active_days_30d",
    "sessions_30d",
    "deposit_amount_30d",
    "withdrawal_amount_30d",
    "rake_30d",
    "lifetime_rake",
    "lifetime_deposit",
    "days_since_last_game",
    "days_since_last_withdrawal",
    "never_withdrew",
    "player_tenure_days",
    "activity_decline_flag",
    "deposit_decline_flag",
    "reduced_session_flag",
    "high_withdrawal_to_deposit_ratio",
    "bonus_dependency_ratio",
    "games_change_7d_vs_previous_7d",
]


def score_players(cfg: ProjectConfig | None = None) -> pd.DataFrame:
    """Write the production-style score file for the test snapshot."""
    configure_logging()
    cfg = cfg or load_config()
    cfg.ensure_directories()
    bundle_path = cfg.path("models_dir") / "champion.joblib"
    if not bundle_path.exists():
        raise FileNotFoundError(bundle_path)
    bundle = joblib.load(bundle_path)
    dataset = pd.read_csv(cfg.path("processed_dir") / "churn_dataset.csv")
    scored = dataset.loc[dataset["dataset_split"] == "test"].copy()
    if scored.empty:
        raise RuntimeError("Test snapshot is empty")
    probabilities = bundle["estimator"].predict_proba(model_feature_frame(scored))[:, 1]
    scored["churn_probability"] = probabilities
    scored["churned_holdout"] = scored["churned"].astype(int)
    scored["risk_band"] = assign_risk_band(
        scored["churn_probability"], cfg.risk_medium, cfg.risk_high, cfg.risk_critical
    )
    scored["prediction_date"] = scored["prediction_date"].astype(str)

    drivers_path = cfg.path("metrics_dir") / "local_drivers.csv"
    if drivers_path.exists():
        drivers = pd.read_csv(drivers_path)
        scored = scored.merge(drivers, on="user_id", how="left")
    else:
        logger.warning("No local drivers found; driver columns will be blank")
        for col in ("top_risk_driver_1", "top_risk_driver_2", "top_risk_driver_3"):
            scored[col] = ""

    segments_path = cfg.path("scores_dir") / "segments.csv"
    if segments_path.exists():
        segments = pd.read_csv(segments_path)
        segments = segments.loc[segments["dataset_split"] == "test", ["user_id", "segment"]]
        scored = scored.merge(segments, on="user_id", how="left")
    else:
        scored["segment"] = "Unsegmented"
    scored["segment"] = scored["segment"].fillna("Unsegmented")
    for col in ("top_risk_driver_1", "top_risk_driver_2", "top_risk_driver_3"):
        scored[col] = scored[col].fillna("")

    scored["recommended_action"] = recommend_actions(scored, cfg.retention)
    output = scored[SCORE_COLUMNS].sort_values("churn_probability", ascending=False)
    out_path = cfg.path("scores_dir") / "player_risk_scores.csv"
    output.to_csv(out_path, index=False)
    logger.info("Wrote %s scores to %s", f"{len(output):,}", out_path)

    examples = output.head(8)[
        [
            "user_id",
            "churn_probability",
            "risk_band",
            "segment",
            "top_risk_driver_1",
            "top_risk_driver_2",
            "top_risk_driver_3",
            "recommended_action",
            "vip_segment",
            "games_30d",
            "days_since_last_game",
            "lifetime_rake",
            "activity_decline_flag",
            "deposit_decline_flag",
        ]
    ]
    examples.to_json(cfg.path("metrics_dir") / "example_high_risk_players.json", orient="records", indent=2)
    band_counts = output["risk_band"].value_counts().to_dict()
    summary = {
        "prediction_date": str(output["prediction_date"].iloc[0]),
        "players": int(len(output)),
        "average_churn_probability": float(output["churn_probability"].mean()),
        "holdout_churn_rate": float(output["churned_holdout"].mean()),
        "risk_band_counts": {str(k): int(v) for k, v in band_counts.items()},
        "risk_band_thresholds": {
            "medium": cfg.risk_medium,
            "high": cfg.risk_high,
            "critical": cfg.risk_critical,
        },
        "model": bundle["model_name"],
        "note": (
            "churned_holdout is known only because this file is a backtest. "
            "A live scoring run would not contain it."
        ),
    }
    (cfg.path("scores_dir") / "score_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Score players and recommend actions")
    parser.parse_args()
    score_players(load_config())


if __name__ == "__main__":
    main()
