"""Train, compare, and select the churn model on a temporal split.

Training rows are the April snapshot. Hyperparameters are chosen by stratified
cross-validation on a subsample of that snapshot, using average precision.
The May snapshot tunes only the decision threshold. The June snapshot is
touched once, for the published test metrics.

A separate in-time random split of June is reported so the optimism of a
random split is visible. It is not used to pick the champion.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Any, Callable

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import (
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline

from src.boosters import NativeBooster, WeightedPipelineModel
from src.config import ProjectConfig, configure_logging, load_config
from src.evaluation import (
    capture_at_fractions,
    classification_metrics,
    curve_points,
    decile_lift,
    tune_threshold,
)
from src.preprocessing import make_one_hot_preprocessor, model_feature_frame

logger = logging.getLogger(__name__)

EstimatorFactory = Callable[[dict[str, Any]], Any]


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2), encoding="utf-8")


def _load_snapshots(cfg: ProjectConfig) -> dict[str, tuple[pd.DataFrame, np.ndarray, pd.DataFrame]]:
    path = cfg.path("processed_dir") / "churn_dataset.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run feature engineering first.")
    frame = pd.read_csv(path)
    if "churned" not in frame.columns:
        raise RuntimeError("churn_dataset.csv has no churned column")
    splits: dict[str, tuple[pd.DataFrame, np.ndarray, pd.DataFrame]] = {}
    for name in ("train", "valid", "test"):
        part = frame.loc[frame["dataset_split"] == name].reset_index(drop=True)
        if part.empty:
            raise RuntimeError(f"Snapshot '{name}' has no rows")
        if part["churned"].nunique() < 2:
            raise RuntimeError(f"Snapshot '{name}' has a single class")
        splits[name] = (model_feature_frame(part), part["churned"].to_numpy().astype(int), part)
        logger.info(
            "%s snapshot: %s players, churn rate %.3f",
            name,
            f"{len(part):,}",
            float(part["churned"].mean()),
        )
    return splits


def _factories(seed: int) -> dict[str, EstimatorFactory]:
    def logreg(params: dict[str, Any]) -> Pipeline:
        return Pipeline(
            [
                ("pre", make_one_hot_preprocessor(scale_numeric=True)),
                (
                    "clf",
                    LogisticRegression(
                        C=float(params["C"]),
                        class_weight="balanced",
                        max_iter=500,
                        solver="lbfgs",
                        random_state=seed,
                    ),
                ),
            ]
        )

    def random_forest(params: dict[str, Any]) -> Pipeline:
        return Pipeline(
            [
                ("pre", make_one_hot_preprocessor(scale_numeric=False)),
                (
                    "clf",
                    RandomForestClassifier(
                        n_estimators=int(params["n_estimators"]),
                        max_depth=int(params["max_depth"]),
                        min_samples_leaf=int(params["min_samples_leaf"]),
                        max_features="sqrt",
                        class_weight="balanced_subsample",
                        n_jobs=2,
                        random_state=seed,
                    ),
                ),
            ]
        )

    def hist_gb(params: dict[str, Any]) -> Pipeline:
        return Pipeline(
            [
                ("pre", make_one_hot_preprocessor(scale_numeric=False)),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        max_depth=int(params["max_depth"]),
                        learning_rate=float(params["learning_rate"]),
                        max_iter=int(params["max_iter"]),
                        l2_regularization=0.1,
                        class_weight="balanced",
                        random_state=seed,
                    ),
                ),
            ]
        )

    def gradient_boosting(params: dict[str, Any]) -> WeightedPipelineModel:
        pipeline = Pipeline(
            [
                ("pre", make_one_hot_preprocessor(scale_numeric=False)),
                (
                    "clf",
                    GradientBoostingClassifier(
                        n_estimators=int(params["n_estimators"]),
                        max_depth=int(params["max_depth"]),
                        learning_rate=float(params["learning_rate"]),
                        subsample=0.85,
                        random_state=seed,
                    ),
                ),
            ]
        )
        return WeightedPipelineModel(pipeline)

    def xgboost(params: dict[str, Any]) -> NativeBooster:
        return NativeBooster(
            "xgboost",
            {
                "n_estimators": int(params["n_estimators"]),
                "max_depth": int(params["max_depth"]),
                "learning_rate": float(params["learning_rate"]),
                "subsample": 0.85,
                "colsample_bytree": 0.85,
                "min_child_weight": 5,
                "reg_lambda": 1.0,
                "objective": "binary:logistic",
                "tree_method": "hist",
                "enable_categorical": True,
                "eval_metric": "aucpr",
                "random_state": seed,
                "n_jobs": 2,
                "verbosity": 0,
            },
        )

    def lightgbm(params: dict[str, Any]) -> NativeBooster:
        return NativeBooster(
            "lightgbm",
            {
                "n_estimators": int(params["n_estimators"]),
                "max_depth": int(params["max_depth"]),
                "learning_rate": float(params["learning_rate"]),
                "subsample": 0.85,
                "colsample_bytree": 0.85,
                "min_child_samples": 40,
                "reg_lambda": 1.0,
                "objective": "binary",
                "random_state": seed,
                "n_jobs": 2,
                "verbose": -1,
            },
        )

    return {
        "logistic_regression": logreg,
        "random_forest": random_forest,
        "hist_gradient_boosting": hist_gb,
        "gradient_boosting": gradient_boosting,
        "xgboost": xgboost,
        "lightgbm": lightgbm,
    }


def _grids() -> dict[str, list[dict[str, Any]]]:
    """Tight grids. Search cost stays bounded; the winner is refit on all April rows."""
    return {
        "logistic_regression": [{"C": 0.3}, {"C": 1.0}, {"C": 3.0}],
        "random_forest": [
            {"n_estimators": 80, "max_depth": 10, "min_samples_leaf": 20},
            {"n_estimators": 80, "max_depth": 16, "min_samples_leaf": 8},
        ],
        "hist_gradient_boosting": [
            {"max_depth": 4, "learning_rate": 0.08, "max_iter": 180},
            {"max_depth": 8, "learning_rate": 0.06, "max_iter": 220},
        ],
        "gradient_boosting": [
            {"n_estimators": 80, "max_depth": 2, "learning_rate": 0.08},
            {"n_estimators": 120, "max_depth": 3, "learning_rate": 0.05},
        ],
        "xgboost": [
            {"n_estimators": 220, "max_depth": 3, "learning_rate": 0.08},
            {"n_estimators": 180, "max_depth": 5, "learning_rate": 0.06},
        ],
        "lightgbm": [
            {"n_estimators": 220, "max_depth": 4, "learning_rate": 0.08},
            {"n_estimators": 180, "max_depth": 6, "learning_rate": 0.06},
        ],
    }


def _folds_for(name: str) -> int:
    return 2 if name in {"random_forest", "gradient_boosting"} else 3


def _cross_validate(
    factory: EstimatorFactory,
    params: dict[str, Any],
    X: pd.DataFrame,
    y: np.ndarray,
    folds: int,
    seed: int,
) -> float:
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    scores: list[float] = []
    for train_idx, test_idx in splitter.split(X, y):
        model = factory(params)
        model.fit(X.iloc[train_idx], y[train_idx])
        probabilities = model.predict_proba(X.iloc[test_idx])[:, 1]
        scores.append(float(average_precision_score(y[test_idx], probabilities)))
    return float(np.mean(scores))


def _search(
    name: str,
    factory: EstimatorFactory,
    grid: list[dict[str, Any]],
    X: pd.DataFrame,
    y: np.ndarray,
    sample_size: int,
    seed: int,
) -> dict[str, Any]:
    if len(y) > sample_size:
        X_search, _, y_search, _ = train_test_split(
            X, y, train_size=sample_size, stratify=y, random_state=seed
        )
        X_search = X_search.reset_index(drop=True)
    else:
        X_search, y_search = X, y
    folds = _folds_for(name)
    best_score = -1.0
    best_params = grid[0]
    for params in grid:
        score = _cross_validate(factory, params, X_search, y_search, folds, seed)
        logger.info("%s params %s -> CV average precision %.4f", name, params, score)
        if score > best_score:
            best_score = score
            best_params = params
    return {"params": best_params, "cv_average_precision": best_score, "cv_folds": folds, "search_rows": int(len(y_search))}


def _save_figures(
    comparison: pd.DataFrame,
    curves: dict[str, dict[str, list[float]]],
    champion: str,
    y_test: np.ndarray,
    p_test: np.ndarray,
    lift: pd.DataFrame,
    matrix: dict[str, int],
    figure_dir: Path,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="talk")

    ranked = comparison.sort_values("pr_auc", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    plot_df = ranked.melt(
        id_vars="model",
        value_vars=["pr_auc", "roc_auc", "recall"],
        var_name="metric",
        value_name="score",
    )
    sns.barplot(data=plot_df, x="model", y="score", hue="metric", ax=ax)
    ax.set_title("Holdout ranking quality versus recall at the tuned threshold")
    ax.set_xlabel("")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(figure_dir / "model_comparison.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    for name, curve in curves.items():
        width = 2.4 if name == champion else 1.2
        ax.plot(curve["fpr"], curve["tpr"], label=name, linewidth=width)
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1)
    ax.set_title("ROC curves on the June holdout")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figure_dir / "roc_curves.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    base = float(np.mean(y_test))
    ax.hlines(base, 0, 1, colors="grey", linestyles="--", label=f"Base rate {base:.2f}")
    for name, curve in curves.items():
        width = 2.4 if name == champion else 1.2
        ax.plot(curve["recall"], curve["precision"], label=name, linewidth=width)
    ax.set_title("Precision-recall curves on the June holdout")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figure_dir / "pr_curves.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4))
    cm = np.array([[matrix["tn"], matrix["fp"]], [matrix["fn"], matrix["tp"]]])
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["Pred retained", "Pred churn"],
        yticklabels=["Retained", "Churned"],
        ax=ax,
    )
    ax.set_title(f"June confusion matrix — {champion}")
    fig.tight_layout()
    fig.savefig(figure_dir / "confusion_matrix.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(lift["decile"].astype(str), lift["lift"], color="#1f4e79")
    ax.axhline(1.0, color="grey", linestyle="--")
    ax.set_title("Lift by predicted-risk decile (1 = highest risk)")
    ax.set_xlabel("Decile")
    ax.set_ylabel("Lift vs base churn rate")
    fig.tight_layout()
    fig.savefig(figure_dir / "lift_by_decile.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    share = np.arange(1, 11) / 10
    ax.plot(share, lift["cumulative_churn_capture"], marker="o", label="Model")
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="Random contact")
    ax.set_title("Cumulative gains — share of churners captured")
    ax.set_xlabel("Share of active players contacted")
    ax.set_ylabel("Share of churners captured")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "cumulative_gains.png", dpi=140)
    plt.close(fig)


def train_models(cfg: ProjectConfig | None = None) -> dict[str, Any]:
    """Fit the comparison set and persist metrics, curves, and the champion."""
    configure_logging()
    cfg = cfg or load_config()
    cfg.ensure_directories()
    seed = int(cfg.model.get("random_state", cfg.seed))
    sample_size = int(cfg.model.get("search_sample_size", 25000))
    beta = float(cfg.model.get("threshold_beta", 1.5))
    contact_rates = [float(v) for v in cfg.model.get("contact_rates", [0.05, 0.10, 0.20])]

    snapshots = _load_snapshots(cfg)
    X_train, y_train, _ = snapshots["train"]
    X_valid, y_valid, valid_frame = snapshots["valid"]
    X_test, y_test, test_frame = snapshots["test"]
    factories = _factories(seed)
    grids = _grids()

    fitted: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    for name, factory in factories.items():
        try:
            logger.info("Selecting hyperparameters for %s", name)
            search = _search(name, factory, grids[name], X_train, y_train, sample_size, seed)
            model = factory(search["params"])
            logger.info("Refitting %s on the full April snapshot", name)
            model.fit(X_train, y_train)
            p_valid = model.predict_proba(X_valid)[:, 1]
            p_test = model.predict_proba(X_test)[:, 1]
            threshold = tune_threshold(y_valid, p_valid, beta=beta)
            fitted[name] = {
                "model": model,
                "search": search,
                "threshold": threshold,
                "p_valid": p_valid,
                "p_test": p_test,
                "valid_at_threshold": classification_metrics(y_valid, p_valid, threshold["threshold"]),
                "test_at_threshold": classification_metrics(y_test, p_test, threshold["threshold"]),
                "test_at_0_5": classification_metrics(y_test, p_test, 0.5),
                "curves": curve_points(y_test, p_test),
            }
            logger.info(
                "%s test PR-AUC %.4f | recall %.3f at threshold %.2f",
                name,
                fitted[name]["test_at_threshold"]["pr_auc"],
                fitted[name]["test_at_threshold"]["recall"],
                threshold["threshold"],
            )
        except Exception as exc:  # noqa: BLE001 — one failed learner must not drop the rest
            logger.exception("Model %s failed", name)
            failures[name] = f"{type(exc).__name__}: {exc}"

    if not fitted:
        raise RuntimeError(f"Every model failed: {failures}")

    champion = max(
        fitted,
        key=lambda name: (
            fitted[name]["valid_at_threshold"]["pr_auc"],
            fitted[name]["valid_at_threshold"]["roc_auc"],
        ),
    )
    logger.info("Champion by May validation PR-AUC: %s", champion)
    champ = fitted[champion]
    lift = decile_lift(y_test, champ["p_test"])
    capture = capture_at_fractions(y_test, champ["p_test"], contact_rates)

    # In-time random split on June only, using the champion hyperparameters.
    X_rand_train, X_rand_test, y_rand_train, y_rand_test = train_test_split(
        X_test, y_test, test_size=0.30, stratify=y_test, random_state=seed
    )
    random_model = factories[champion](champ["search"]["params"])
    random_model.fit(X_rand_train.reset_index(drop=True), y_rand_train)
    p_random = random_model.predict_proba(X_rand_test.reset_index(drop=True))[:, 1]
    random_metrics = classification_metrics(y_rand_test, p_random, champ["threshold"]["threshold"])

    metrics_dir = cfg.path("metrics_dir")
    figure_dir = cfg.path("figures_dir")
    comparison_rows = []
    for name, payload in fitted.items():
        row = {"model": name, **payload["test_at_threshold"]}
        row["cv_average_precision"] = payload["search"]["cv_average_precision"]
        row["validation_pr_auc"] = payload["valid_at_threshold"]["pr_auc"]
        comparison_rows.append(row)
    comparison = pd.DataFrame(comparison_rows).sort_values("pr_auc", ascending=False)
    flat_cols = [
        "model",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "pr_auc",
        "threshold",
        "validation_pr_auc",
        "cv_average_precision",
    ]
    comparison[flat_cols].to_csv(metrics_dir / "model_comparison.csv", index=False)
    at_half = pd.DataFrame(
        [{"model": name, **payload["test_at_0_5"]} for name, payload in fitted.items()]
    )
    at_half.to_csv(metrics_dir / "model_comparison_threshold_0_5.csv", index=False)
    lift.to_csv(metrics_dir / "lift_deciles.csv", index=False)
    capture.to_csv(metrics_dir / "capture_at_contact_rate.csv", index=False)

    predictions = pd.DataFrame({"user_id": test_frame["user_id"].to_numpy(), "y_true": y_test})
    for name, payload in fitted.items():
        predictions[f"p_{name}"] = payload["p_test"]
    predictions["p_champion"] = champ["p_test"]
    predictions.to_csv(metrics_dir / "test_predictions.csv", index=False)
    pd.DataFrame(
        {
            "user_id": valid_frame["user_id"].to_numpy(),
            "y_true": y_valid,
            "p_champion": champ["p_valid"],
        }
    ).to_csv(metrics_dir / "valid_predictions.csv", index=False)

    _save_figures(
        comparison[flat_cols],
        {name: payload["curves"] for name, payload in fitted.items()},
        champion,
        y_test,
        champ["p_test"],
        lift,
        champ["test_at_threshold"]["confusion_matrix"],
        figure_dir,
    )

    bundle = {
        "model_name": champion,
        "estimator": champ["model"],
        "threshold": champ["threshold"],
        "params": champ["search"]["params"],
        "numeric_features": list(X_train.columns),
    }
    model_path = cfg.path("models_dir") / "champion.joblib"
    joblib.dump(bundle, model_path)
    logger.info("Saved champion to %s", model_path)

    summary = {
        "champion": champion,
        "selection_rule": "Highest PR-AUC on the May validation snapshot. Threshold maximizes F-beta on May and is frozen before June is scored.",
        "threshold_beta": beta,
        "failures": failures,
        "comparison": comparison[flat_cols].to_dict(orient="records"),
        "comparison_at_0_5": at_half.to_dict(orient="records"),
        "champion_test": champ["test_at_threshold"],
        "champion_test_at_0_5": champ["test_at_0_5"],
        "champion_validation": champ["valid_at_threshold"],
        "search": {name: payload["search"] for name, payload in fitted.items()},
        "lift_deciles": lift.to_dict(orient="records"),
        "capture": capture.to_dict(orient="records"),
        "random_split": {
            "description": (
                "Champion hyperparameters refit on a stratified 70% of the June snapshot "
                "and scored on the other 30%. Same threshold as the temporal model. "
                "This is an in-time estimate and is expected to look better than the June "
                "holdout of a model trained in April."
            ),
            "metrics": random_metrics,
            "temporal_test_metrics": champ["test_at_threshold"],
        },
        "curves": {champion: champ["curves"]},
        "disclaimer": (
            "This project uses synthetic data inspired by common online gaming analytics "
            "use cases. It does not contain confidential or proprietary Junglee Games data."
        ),
    }
    _write_json(metrics_dir / "metrics.json", summary)
    logger.info("Wrote metrics to %s", metrics_dir / "metrics.json")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and compare churn models")
    parser.parse_args()
    train_models(load_config())


if __name__ == "__main__":
    main()
