"""Behavioral segments for the active base.

K-means is fit on the April snapshot only, using scaled activity, value,
recency, and bonus-dependence features. K is chosen by silhouette on a
sample. Names are assigned from the centroid profile, not from the churn
label. June players are scored with the April centroids.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.config import ProjectConfig, configure_logging, load_config

logger = logging.getLogger(__name__)

CLUSTER_FEATURES: list[str] = [
    "games_30d",
    "active_days_30d",
    "sessions_30d",
    "days_since_last_game",
    "games_change_7d_vs_previous_7d",
    "deposit_amount_30d",
    "lifetime_rake",
    "player_tenure_days",
    "bonus_dependency_ratio",
    "rake_30d",
    "inactivity_gap_days",
]


def _choose_k(scaled: np.ndarray, seed: int) -> tuple[int, list[dict[str, float]]]:
    sample_n = min(12000, len(scaled))
    rng = np.random.default_rng(seed)
    sample_idx = rng.choice(len(scaled), size=sample_n, replace=False)
    sample = scaled[sample_idx]
    rows = []
    best_k = 4
    best_score = -1.0
    for k in range(4, 9):
        model = KMeans(n_clusters=k, n_init=10, random_state=seed)
        labels = model.fit_predict(sample)
        score = float(silhouette_score(sample, labels))
        rows.append({"k": k, "silhouette": score})
        logger.info("K=%s silhouette %.4f", k, score)
        if score > best_score:
            best_score = score
            best_k = k
    return best_k, rows


def _name_clusters(centroids: pd.DataFrame) -> dict[int, str]:
    """Name centroids from their raw profile. Names are not reused.

    A cluster with bonus dependency near 1 and almost no deposits is
    Promotion Sensitive even when tenure is also short. Calling that group
    "new" overclaims: the June players who match the centroid are often
    older accounts that still play only on bonus.
    """
    raw = centroids.copy()
    assigned: dict[int, str] = {}
    used: set[int] = set()

    def _take(cluster_id: int, name: str) -> None:
        assigned[int(cluster_id)] = name
        used.add(int(cluster_id))

    promo_id = int(raw["bonus_dependency_ratio"].idxmax())
    if float(raw.loc[promo_id, "bonus_dependency_ratio"]) >= 0.5 and float(raw.loc[promo_id, "deposit_amount_30d"]) < 50:
        _take(promo_id, "Promotion Sensitive")

    value_id = int(raw["lifetime_rake"].idxmax())
    if value_id not in used:
        high_recency = float(raw.loc[value_id, "days_since_last_game"]) >= float(raw["days_since_last_game"].median())
        declining = float(raw.loc[value_id, "games_change_7d_vs_previous_7d"]) < 0 and high_recency
        _take(value_id, "High Value–Declining" if declining else "High Value–High Engagement")

    remaining = [int(idx) for idx in raw.index if int(idx) not in used]
    if remaining:
        dormant_id = max(
            remaining,
            key=lambda idx: float(raw.loc[idx, "days_since_last_game"]) + float(raw.loc[idx, "inactivity_gap_days"]) - float(raw.loc[idx, "games_30d"]),
        )
        if float(raw.loc[dormant_id, "games_30d"]) <= float(raw.loc[remaining, "games_30d"].median()):
            _take(dormant_id, "Dormant/Reactivation")

    remaining = [int(idx) for idx in raw.index if int(idx) not in used]
    if remaining:
        engaged_id = max(remaining, key=lambda idx: float(raw.loc[idx, "games_30d"]))
        _take(engaged_id, "Low Value–High Engagement")

    remaining = [int(idx) for idx in raw.index if int(idx) not in used]
    fallback = ["New & Unstable", "Casual", "High Value–Declining", "Promotion Sensitive"]
    for cluster_id, name in zip(remaining, fallback):
        if name not in assigned.values():
            _take(cluster_id, name)
    for cluster_id in raw.index:
        if int(cluster_id) not in assigned:
            assigned[int(cluster_id)] = f"Segment {int(cluster_id)}"
    return assigned


def build_segments(cfg: ProjectConfig | None = None) -> pd.DataFrame:
    """Fit K-means on April and assign June players."""
    configure_logging()
    cfg = cfg or load_config()
    cfg.ensure_directories()
    frame = pd.read_csv(cfg.path("processed_dir") / "churn_dataset.csv")
    missing = [col for col in CLUSTER_FEATURES if col not in frame.columns]
    if missing:
        raise KeyError(f"Segmentation features missing: {missing}")
    train = frame.loc[frame["dataset_split"] == "train"].reset_index(drop=True)
    test = frame.loc[frame["dataset_split"] == "test"].reset_index(drop=True)
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train[CLUSTER_FEATURES])
    k, silhouette_rows = _choose_k(scaled_train, seed=cfg.seed)
    model = KMeans(n_clusters=k, n_init=10, random_state=cfg.seed)
    train_labels = model.fit_predict(scaled_train)
    test_labels = model.predict(scaler.transform(test[CLUSTER_FEATURES]))
    centroids = pd.DataFrame(scaler.inverse_transform(model.cluster_centers_), columns=CLUSTER_FEATURES)
    names = _name_clusters(centroids)
    logger.info("Selected K=%s with names %s", k, names)

    def _pack(part: pd.DataFrame, labels: np.ndarray, split: str) -> pd.DataFrame:
        out = pd.DataFrame(
            {
                "user_id": part["user_id"].to_numpy(),
                "dataset_split": split,
                "cluster_id": labels,
                "segment": [names[int(label)] for label in labels],
                "churned": part["churned"].to_numpy(),
            }
        )
        return out

    assignments = pd.concat(
        [_pack(train, train_labels, "train"), _pack(test, test_labels, "test")],
        ignore_index=True,
    )
    profile_source = test.copy()
    profile_source["segment"] = [names[int(label)] for label in test_labels]
    profile = (
        profile_source.groupby("segment")
        .agg(
            players=("user_id", "size"),
            churn_rate=("churned", "mean"),
            avg_games_30d=("games_30d", "mean"),
            avg_active_days_30d=("active_days_30d", "mean"),
            avg_days_since_last_game=("days_since_last_game", "mean"),
            avg_deposit_30d=("deposit_amount_30d", "mean"),
            avg_lifetime_rake=("lifetime_rake", "mean"),
            avg_tenure_days=("player_tenure_days", "mean"),
            avg_bonus_dependency=("bonus_dependency_ratio", "mean"),
            avg_games_change_7d=("games_change_7d_vs_previous_7d", "mean"),
        )
        .reset_index()
        .sort_values("players", ascending=False)
    )
    scores_dir = cfg.path("scores_dir")
    metrics_dir = cfg.path("metrics_dir")
    assignments.to_csv(scores_dir / "segments.csv", index=False)
    profile.to_csv(metrics_dir / "segment_profile.csv", index=False)
    centroids.assign(segment=[names[i] for i in centroids.index]).to_csv(
        metrics_dir / "segment_centroids.csv", index=False
    )

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ordered = profile.sort_values("churn_rate", ascending=False)
    ax.barh(ordered["segment"], ordered["churn_rate"], color="#1f4e79")
    ax.set_xlabel("June holdout churn rate")
    ax.set_title("Churn rate by behavioral segment")
    fig.tight_layout()
    fig.savefig(cfg.path("figures_dir") / "churn_by_segment.png", dpi=140)
    plt.close(fig)

    summary = {
        "k": k,
        "silhouette": silhouette_rows,
        "names": {str(k_): v for k_, v in names.items()},
        "features": CLUSTER_FEATURES,
        "fit_on": "train snapshot only; June is assigned with those centroids",
        "why_kmeans": (
            "Segments are a compression of continuous behavior for CRM routing. "
            "K-means is appropriate once features are scaled, because the inputs "
            "are numeric and the goal is a small set of operational groups rather "
            "than a generative mixture. Silhouette on a sample chooses K in 4–8."
        ),
    }
    (metrics_dir / "segmentation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Build behavioral player segments")
    parser.parse_args()
    build_segments(load_config())


if __name__ == "__main__":
    main()
