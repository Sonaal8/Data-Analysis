"""Feature PSI, score shift, and a simple drift simulation.

Population stability compares the April training snapshot (reference) with
the June scoring snapshot (actual). The simulation then worsens June
engagement features and shows that the score distribution moves before any
new labels exist. That is a monitoring alert, not a measured retention effect.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import ProjectConfig, configure_logging, load_config
from src.evaluation import population_stability_index
from src.preprocessing import model_feature_frame

logger = logging.getLogger(__name__)

WATCHED_FEATURES = [
    "days_since_last_game",
    "games_30d",
    "games_7d",
    "active_days_30d",
    "sessions_30d",
    "games_change_7d_vs_previous_7d",
    "deposit_amount_30d",
    "deposit_change_7d_vs_previous_7d",
    "rake_30d",
    "lifetime_rake",
    "bonus_dependency_ratio",
    "inactivity_gap_days",
]


def run_monitoring(cfg: ProjectConfig | None = None) -> dict[str, Any]:
    """Compare April vs June and simulate an engagement drop."""
    configure_logging()
    cfg = cfg or load_config()
    cfg.ensure_directories()
    frame = pd.read_csv(cfg.path("processed_dir") / "churn_dataset.csv")
    train = frame.loc[frame["dataset_split"] == "train"]
    test = frame.loc[frame["dataset_split"] == "test"].reset_index(drop=True)
    rows = []
    for feature in WATCHED_FEATURES:
        psi = population_stability_index(train[feature].to_numpy(), test[feature].to_numpy())
        rows.append(
            {
                "feature": feature,
                "psi_april_vs_june": psi,
                "april_mean": float(train[feature].mean()),
                "june_mean": float(test[feature].mean()),
            }
        )
    psi_table = pd.DataFrame(rows).sort_values("psi_april_vs_june", ascending=False)
    psi_table.to_csv(cfg.path("metrics_dir") / "feature_psi.csv", index=False)

    bundle = joblib.load(cfg.path("models_dir") / "champion.joblib")
    estimator = bundle["estimator"]
    base_features = model_feature_frame(test)
    base_scores = estimator.predict_proba(base_features)[:, 1]
    shifted = test.copy()
    for column in ("games_7d", "games_14d", "games_30d", "active_days_7d", "active_days_30d", "sessions_7d", "sessions_30d", "rake_7d", "rake_30d"):
        if column in shifted.columns:
            shifted[column] = shifted[column] * 0.7
    shifted["days_since_last_game"] = shifted["days_since_last_game"] + 4
    shifted["inactivity_gap_days"] = shifted["inactivity_gap_days"] + 3
    shifted_scores = estimator.predict_proba(model_feature_frame(shifted))[:, 1]
    score_psi = population_stability_index(base_scores, shifted_scores)

    valid_path = cfg.path("metrics_dir") / "valid_predictions.csv"
    temporal_score_psi = None
    if valid_path.exists():
        valid_scores = pd.read_csv(valid_path)["p_champion"].to_numpy()
        temporal_score_psi = population_stability_index(valid_scores, base_scores)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(base_scores, bins=30, alpha=0.7, label="June scores", color="#1f4e79", density=True)
    ax.hist(shifted_scores, bins=30, alpha=0.55, label="Simulated engagement drop", color="#c47b2b", density=True)
    ax.set_title("Score distribution before and after a simulated behavior shift")
    ax.set_xlabel("Predicted churn probability")
    ax.set_ylabel("Density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(cfg.path("figures_dir") / "monitoring_score_shift.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    top = psi_table.head(10).iloc[::-1]
    ax.barh(top["feature"], top["psi_april_vs_june"], color="#1f4e79")
    ax.axvline(0.1, color="grey", linestyle="--", label="Watch (0.10)")
    ax.axvline(0.25, color="#a33b20", linestyle="--", label="Act (0.25)")
    ax.set_title("Feature PSI, April reference vs June actual")
    ax.set_xlabel("PSI")
    ax.legend()
    fig.tight_layout()
    fig.savefig(cfg.path("figures_dir") / "feature_psi.png", dpi=140)
    plt.close(fig)

    report = {
        "reference": "April train snapshot",
        "actual": "June test snapshot",
        "feature_psi": psi_table.to_dict(orient="records"),
        "max_feature_psi": float(psi_table["psi_april_vs_june"].max()),
        "score_psi_may_vs_june": None if temporal_score_psi is None else float(temporal_score_psi),
        "simulation": {
            "description": (
                "June engagement and rake features multiplied by 0.7; recency and "
                "inactivity gap increased. Labels are not changed. The alert is the "
                "movement in scores."
            ),
            "score_psi": float(score_psi),
            "mean_score_before": float(np.mean(base_scores)),
            "mean_score_after": float(np.mean(shifted_scores)),
        },
        "thresholds": {
            "psi_watch": 0.10,
            "psi_act": 0.25,
            "note": "These are operating guidelines, not statistical laws.",
        },
    }
    (cfg.path("metrics_dir") / "monitoring.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info(
        "Monitoring PSI max %.3f; simulated score mean %.3f -> %.3f",
        report["max_feature_psi"],
        report["simulation"]["mean_score_before"],
        report["simulation"]["mean_score_after"],
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run churn-model monitoring checks")
    parser.parse_args()
    run_monitoring(load_config())


if __name__ == "__main__":
    main()
