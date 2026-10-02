"""Global and player-level explanations for the champion model.

Tree SHAP is computed with the booster contribution API for XGBoost and
LightGBM, and with ``shap.TreeExplainer`` for a scikit-learn forest or
gradient-boosting pipeline. One-hot columns are summed back to the original
categorical feature before a player-level driver is named. If that path
fails, explanations fall back to permutation importance plus a one-at-a-time
replacement against the training median or mode. The fallback is labeled as
such and is not described as SHAP.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from src.boosters import NativeBooster
from src.config import ProjectConfig, configure_logging, load_config
from src.preprocessing import CATEGORICAL_FEATURES, NUMERIC_FEATURES, model_feature_frame

logger = logging.getLogger(__name__)

DRIVER_LABELS: dict[str, str] = {
    "games_7d": "Games in the last 7 days",
    "games_14d": "Games in the last 14 days",
    "games_30d": "Games in the last 30 days",
    "active_days_7d": "Active days in the last 7 days",
    "active_days_30d": "Active days in the last 30 days",
    "sessions_7d": "Sessions in the last 7 days",
    "sessions_30d": "Sessions in the last 30 days",
    "avg_session_duration": "Average session duration",
    "total_play_time": "Total play time in the last 30 days",
    "avg_games_per_active_day": "Games per active day",
    "days_since_last_game": "Days since last game",
    "days_since_last_login": "Days since last login",
    "days_since_last_deposit": "Days since last deposit",
    "days_since_last_withdrawal": "Days since last withdrawal",
    "never_deposited": "No deposit on record",
    "never_withdrew": "No withdrawal on record",
    "games_per_day": "Games per day over 30 days",
    "sessions_per_active_day": "Sessions per active day",
    "deposit_amount_7d": "Deposits in the last 7 days",
    "deposit_amount_30d": "Deposits in the last 30 days",
    "withdrawal_amount_30d": "Withdrawals in the last 30 days",
    "net_deposit_30d": "Net deposits in the last 30 days",
    "rake_7d": "Rake in the last 7 days",
    "rake_30d": "Rake in the last 30 days",
    "avg_entry_fee": "Average entry fee",
    "total_entry_fee": "Total entry fees in the last 30 days",
    "games_change_7d_vs_previous_7d": "Change in games versus the prior week",
    "games_change_14d_vs_previous_14d": "Change in games versus the prior two weeks",
    "deposit_change_7d_vs_previous_7d": "Change in deposits versus the prior week",
    "rake_change_7d_vs_previous_7d": "Change in rake versus the prior week",
    "session_change_7d_vs_previous_7d": "Change in sessions versus the prior week",
    "game_frequency_std": "Volatility of daily game counts",
    "deposit_frequency_std": "Volatility of daily deposits",
    "session_duration_std": "Volatility of session duration",
    "lifetime_games": "Lifetime games",
    "lifetime_deposit": "Lifetime deposits",
    "lifetime_rake": "Lifetime rake",
    "player_tenure_days": "Tenure",
    "tournament_affinity": "Tournament affinity",
    "pool_affinity": "Pool-rummy affinity",
    "points_affinity": "Points-rummy affinity",
    "deals_affinity": "Deals-rummy affinity",
    "bonus_received_30d": "Bonus value received in 30 days",
    "bonus_used_30d": "Bonus value used in 30 days",
    "cashback_received_30d": "Cashback in 30 days",
    "bonus_dependency_ratio": "Bonus dependency",
    "activity_decline_flag": "Activity-decline flag",
    "deposit_decline_flag": "Deposit-decline flag",
    "reduced_session_flag": "Reduced-session flag",
    "high_withdrawal_to_deposit_ratio": "High withdrawal-to-deposit ratio",
    "inactivity_gap_days": "Longest inactivity gap in 30 days",
    "vip_segment": "VIP segment",
    "device_type": "Device type",
    "acquisition_channel": "Acquisition channel",
    "registration_platform": "Registration platform",
    "preferred_game_type": "Preferred game type",
    "preferred_game_variant": "Preferred game variant",
}


def label_for(feature: str) -> str:
    return DRIVER_LABELS.get(feature, feature.replace("_", " "))


def _tree_contributions(booster: NativeBooster, frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    transformed = booster.prep.transform(frame) if booster.prep is not None else frame
    if booster.kind == "xgboost":
        import xgboost as xgb

        matrix = xgb.DMatrix(transformed, enable_categorical=True)
        values = booster.model.get_booster().predict(matrix, pred_contribs=True)
        method = "TreeSHAP contributions from XGBoost pred_contribs (bias column dropped)"
    else:
        values = booster.model.predict(transformed, pred_contrib=True)
        method = "TreeSHAP contributions from LightGBM pred_contrib (bias column dropped)"
    features = list(transformed.columns)
    if values.shape[1] != len(features) + 1:
        raise RuntimeError(
            f"Contribution width {values.shape[1]} does not match {len(features)} features plus bias"
        )
    contributions = pd.DataFrame(values[:, :-1], columns=features, index=frame.index)
    return contributions, method


def _original_feature_name(transformed: str) -> str:
    """Map a ColumnTransformer column back to a modeling feature."""
    if transformed.startswith("numeric__"):
        return transformed[len("numeric__") :]
    if transformed.startswith("categorical__"):
        rest = transformed[len("categorical__") :]
        for feature in sorted(CATEGORICAL_FEATURES, key=len, reverse=True):
            if rest == feature or rest.startswith(feature + "_"):
                return feature
        return rest
    return transformed


def _group_transformed_shap(values: np.ndarray, transformed_names: list[str]) -> pd.DataFrame:
    """Sum one-hot SHAP columns so each original feature has one contribution."""
    grouped: dict[str, np.ndarray] = {}
    for index, name in enumerate(transformed_names):
        feature = _original_feature_name(str(name))
        column = values[:, index]
        if feature in grouped:
            grouped[feature] = grouped[feature] + column
        else:
            grouped[feature] = column.copy()
    ordered = [feature for feature in NUMERIC_FEATURES + CATEGORICAL_FEATURES if feature in grouped]
    extra = [feature for feature in grouped if feature not in ordered]
    return pd.DataFrame({feature: grouped[feature] for feature in ordered + extra})


def _positive_class_shap(raw: Any, n_rows: int) -> np.ndarray:
    """Return class-1 SHAP values with shape (n_rows, n_transformed)."""
    if isinstance(raw, list):
        if len(raw) < 2:
            raise RuntimeError(f"SHAP returned {len(raw)} class arrays; expected 2")
        values = np.asarray(raw[1])
    else:
        values = np.asarray(raw)
        if values.ndim == 3:
            if values.shape[0] == n_rows:
                values = values[:, :, -1]
            elif values.shape[2] == n_rows:
                values = values[-1].T
            else:
                raise RuntimeError(f"Unexpected SHAP shape {values.shape} for {n_rows} rows")
    if values.shape[0] != n_rows:
        raise RuntimeError(f"SHAP row count {values.shape[0]} != {n_rows}")
    return values


def _sklearn_tree_shap(estimator: Any, frame: pd.DataFrame, chunk_size: int = 2500) -> tuple[pd.DataFrame, str]:
    """Tree SHAP for a fitted sklearn Pipeline(pre, clf)."""
    import shap

    if "pre" not in getattr(estimator, "named_steps", {}) or "clf" not in estimator.named_steps:
        raise TypeError("Expected a Pipeline with steps 'pre' and 'clf'")
    preprocessor = estimator.named_steps["pre"]
    classifier = estimator.named_steps["clf"]
    classes = list(getattr(classifier, "classes_", []))
    if classes and classes[-1] != 1:
        raise RuntimeError(f"Positive class is not 1: {classes}")
    transformed_names = [str(name) for name in preprocessor.get_feature_names_out()]
    explainer = shap.TreeExplainer(classifier)
    parts: list[pd.DataFrame] = []
    for start in range(0, len(frame), chunk_size):
        chunk = frame.iloc[start : start + chunk_size]
        transformed = preprocessor.transform(chunk)
        raw = explainer.shap_values(transformed, check_additivity=False)
        class_values = _positive_class_shap(raw, n_rows=len(chunk))
        if class_values.shape[1] != len(transformed_names):
            raise RuntimeError(
                f"SHAP width {class_values.shape[1]} != {len(transformed_names)} transformed columns"
            )
        grouped = _group_transformed_shap(class_values, transformed_names)
        grouped.index = chunk.index
        parts.append(grouped)
        logger.info("TreeSHAP rows %s–%s of %s", start + 1, start + len(chunk), len(frame))
    contributions = pd.concat(parts, axis=0).loc[frame.index]
    method = (
        f"SHAP TreeExplainer on {classifier.__class__.__name__} "
        f"({getattr(classifier, 'n_estimators', 'n/a')} trees). "
        "Class-1 contributions; one-hot columns summed back to the original feature. "
        f"Computed on all {len(frame):,} June holdout rows."
    )
    return contributions, method


def _permutation_importance(
    predict_fn: Any,
    frame: pd.DataFrame,
    y: np.ndarray,
    seed: int,
    repeats: int = 3,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    baseline = float(average_precision_score(y, predict_fn(frame)[:, 1]))
    rows = []
    for column in frame.columns:
        drops = []
        for _ in range(repeats):
            shuffled = frame.copy()
            shuffled[column] = rng.permutation(shuffled[column].to_numpy())
            score = float(average_precision_score(y, predict_fn(shuffled)[:, 1]))
            drops.append(baseline - score)
        rows.append(
            {
                "feature": column,
                "label": label_for(column),
                "mean_importance": float(np.mean(drops)),
                "std_importance": float(np.std(drops)),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_importance", ascending=False)


def _replacement_contributions(
    predict_fn: Any,
    frame: pd.DataFrame,
    features: list[str],
    medians: dict[str, float],
    modes: dict[str, str],
) -> pd.DataFrame:
    """Increase in risk versus replacing the feature with a typical training value."""
    base = predict_fn(frame)[:, 1]
    columns = {}
    for feature in features:
        altered = frame.copy()
        if feature in medians:
            altered[feature] = medians[feature]
        else:
            altered[feature] = modes[feature]
        columns[feature] = base - predict_fn(altered)[:, 1]
    return pd.DataFrame(columns, index=frame.index)


def _top_driver_frame(contributions: pd.DataFrame, user_ids: pd.Series) -> pd.DataFrame:
    values = contributions.to_numpy(dtype=float)
    names = np.array(contributions.columns)
    order = np.argsort(-values, axis=1)
    records = []
    for row_i, user_id in enumerate(user_ids.to_numpy()):
        picked: list[tuple[str, float]] = []
        for rank in order[row_i]:
            shap_value = float(values[row_i, rank])
            if shap_value <= 0:
                break
            picked.append((str(names[rank]), shap_value))
            if len(picked) == 3:
                break
        while len(picked) < 3:
            picked.append(("", float("nan")))
        records.append(
            {
                "user_id": int(user_id),
                "top_risk_driver_1": label_for(picked[0][0]) if picked[0][0] else "",
                "top_risk_driver_2": label_for(picked[1][0]) if picked[1][0] else "",
                "top_risk_driver_3": label_for(picked[2][0]) if picked[2][0] else "",
                "driver_1_feature": picked[0][0],
                "driver_2_feature": picked[1][0],
                "driver_3_feature": picked[2][0],
                "driver_1_shap": picked[0][1],
                "driver_2_shap": picked[1][1],
                "driver_3_shap": picked[2][1],
            }
        )
    return pd.DataFrame(records)


def _plot_importance(importance: pd.DataFrame, value_col: str, title: str, path: Path) -> None:
    top = importance.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(top["label"], top[value_col], color="#1f4e79")
    ax.set_title(title)
    ax.set_xlabel(value_col.replace("_", " "))
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def explain_model(cfg: ProjectConfig | None = None) -> dict[str, Any]:
    """Write global importance, local drivers, and a few player narratives."""
    configure_logging()
    cfg = cfg or load_config()
    cfg.ensure_directories()
    bundle_path = cfg.path("models_dir") / "champion.joblib"
    if not bundle_path.exists():
        raise FileNotFoundError(f"Missing {bundle_path}. Train the champion first.")
    bundle = joblib.load(bundle_path)
    estimator = bundle["estimator"]
    dataset = pd.read_csv(cfg.path("processed_dir") / "churn_dataset.csv")
    test = dataset.loc[dataset["dataset_split"] == "test"].reset_index(drop=True)
    features = model_feature_frame(test)
    y = test["churned"].to_numpy().astype(int)
    metrics_dir = cfg.path("metrics_dir")
    figure_dir = cfg.path("figures_dir")

    method = ""
    contributions: pd.DataFrame | None = None
    shap_error = ""
    if isinstance(estimator, NativeBooster):
        contributions, method = _tree_contributions(estimator, features)
        logger.info("Computed contributions with %s", method)
    else:
        try:
            contributions, method = _sklearn_tree_shap(estimator, features)
            logger.info("Computed contributions with %s", method)
        except Exception as exc:  # documented fallback; the failure is persisted
            shap_error = f"{type(exc).__name__}: {exc}"
            method = (
                "One-at-a-time replacement versus the training median or mode. "
                f"TreeSHAP failed ({shap_error}). These are local sensitivities, not SHAP values."
            )
            logger.warning(method)

    sample_n = min(4000, len(features))
    sample = features.sample(sample_n, random_state=cfg.seed)
    y_sample = y[sample.index.to_numpy()]
    logger.info("Permutation importance on %s holdout rows", f"{sample_n:,}")
    permutation = _permutation_importance(
        estimator.predict_proba,
        sample.reset_index(drop=True),
        y_sample,
        seed=cfg.seed,
    )
    permutation.to_csv(metrics_dir / "permutation_importance.csv", index=False)
    _plot_importance(
        permutation,
        "mean_importance",
        "Permutation importance (drop in PR-AUC)",
        figure_dir / "permutation_importance.png",
    )

    if contributions is None:
        top_features = permutation["feature"].head(8).tolist()
        prep = getattr(estimator, "prep", None)
        medians = prep.medians if prep is not None else {col: float(features[col].median()) for col in NUMERIC_FEATURES}
        modes = prep.modes if prep is not None else {
            col: str(features[col].mode(dropna=True).iloc[0]) for col in CATEGORICAL_FEATURES
        }
        contributions = _replacement_contributions(
            estimator.predict_proba, features, top_features, medians, modes
        )

    mean_abs = contributions.abs().mean().sort_values(ascending=False)
    global_shap = pd.DataFrame(
        {
            "feature": mean_abs.index,
            "label": [label_for(name) for name in mean_abs.index],
            "mean_abs_shap": mean_abs.to_numpy(),
            "mean_shap": contributions[mean_abs.index].mean().to_numpy(),
        }
    )
    global_shap.to_csv(metrics_dir / "shap_importance.csv", index=False)
    _plot_importance(
        global_shap,
        "mean_abs_shap",
        "Global importance — mean absolute contribution",
        figure_dir / "shap_importance.png",
    )

    # Dependence view for the strongest numeric driver, on a sample.
    top_feature = str(global_shap["feature"].iloc[0])
    sample_idx = contributions.sample(min(2500, len(contributions)), random_state=cfg.seed).index
    fig, ax = plt.subplots(figsize=(7, 4.5))
    if top_feature in features.columns and pd.api.types.is_numeric_dtype(features[top_feature]):
        ax.scatter(
            features.loc[sample_idx, top_feature],
            contributions.loc[sample_idx, top_feature],
            s=8,
            alpha=0.35,
            color="#1f4e79",
        )
        ax.set_xlabel(label_for(top_feature))
        ax.set_ylabel("Contribution to churn score")
        ax.set_title(f"Player-level contribution of {label_for(top_feature)}")
    else:
        grouped = pd.DataFrame(
            {
                "level": features.loc[sample_idx, top_feature].astype(str),
                "contrib": contributions.loc[sample_idx, top_feature],
            }
        )
        order = grouped.groupby("level")["contrib"].mean().sort_values().index
        ax.barh(order, grouped.groupby("level")["contrib"].mean().loc[order], color="#1f4e79")
        ax.set_xlabel("Mean contribution to churn score")
        ax.set_title(f"Mean contribution by {label_for(top_feature)}")
    fig.tight_layout()
    fig.savefig(figure_dir / "shap_dependence_top_feature.png", dpi=140)
    plt.close(fig)

    drivers = _top_driver_frame(contributions, test["user_id"])
    drivers.to_csv(metrics_dir / "local_drivers.csv", index=False)

    shap_sample_cols = list(global_shap["feature"].head(12))
    sample_out = contributions.loc[sample_idx, shap_sample_cols].copy()
    sample_out.insert(0, "user_id", test.loc[sample_idx, "user_id"].to_numpy())
    sample_out.to_csv(metrics_dir / "shap_sample.csv", index=False)

    summary = {
        "method": method,
        "shap_error": shap_error,
        "is_shap": shap_error == "" and contributions is not None and "not SHAP" not in method,
        "champion": bundle["model_name"],
        "rows_explained": int(len(contributions)),
        "top_features": global_shap.head(15).to_dict(orient="records"),
        "permutation_top_features": permutation.head(15).to_dict(orient="records"),
    }
    (metrics_dir / "explain_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Top feature: %s", summary["top_features"][0]["feature"])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Explain the champion churn model")
    parser.parse_args()
    explain_model(load_config())


if __name__ == "__main__":
    main()
