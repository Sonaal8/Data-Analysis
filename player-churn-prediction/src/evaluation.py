"""Metrics, threshold selection, and lift / gain tables.

Accuracy is reported and is not the selection metric. With a 15–30% churn
base rate, a model that calls everyone retained can clear 70% accuracy while
finding nobody the retention team can call.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)


def classification_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict[str, Any]:
    """Score a probability vector at one operating threshold."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "accuracy": float((y_pred == y_true).mean()),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, y_prob)) if y_true.sum() else float("nan"),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "positives": int(y_true.sum()),
        "n": int(len(y_true)),
    }


def tune_threshold(y_true: np.ndarray, y_prob: np.ndarray, beta: float = 1.5) -> dict[str, float]:
    """Pick a validation threshold that maximizes F-beta.

    Beta above 1 weights recall more than precision, which matches a retention
    desk that would rather place an extra call than miss a player who leaves.
    The chosen threshold is a policy point for this cost ratio, not a universal
    optimum.
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    best: dict[str, float] | None = None
    for threshold in np.linspace(0.05, 0.90, 86):
        pred = (y_prob >= threshold).astype(int)
        score = float(fbeta_score(y_true, pred, beta=beta, zero_division=0))
        precision = float(precision_score(y_true, pred, zero_division=0))
        recall = float(recall_score(y_true, pred, zero_division=0))
        candidate = {
            "threshold": float(threshold),
            "fbeta": score,
            "precision": precision,
            "recall": recall,
            "beta": float(beta),
        }
        if best is None or candidate["fbeta"] > best["fbeta"]:
            best = candidate
    if best is None:
        raise RuntimeError("Threshold search received no candidates")
    return best


def decile_lift(y_true: np.ndarray, y_prob: np.ndarray, n_deciles: int = 10) -> pd.DataFrame:
    """Highest-risk decile is 1. Ties are broken by row order so groups stay equal."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    n = len(y_true)
    if n < n_deciles:
        raise ValueError("Need at least one row per decile")
    order = np.argsort(-y_prob, kind="mergesort")
    y_sorted = y_true[order]
    edges = np.linspace(0, n, n_deciles + 1, dtype=int)
    total_churn = float(y_true.sum())
    base_rate = total_churn / n
    rows: list[dict[str, float | int]] = []
    captured = 0.0
    for decile in range(n_deciles):
        segment = y_sorted[edges[decile] : edges[decile + 1]]
        users = int(len(segment))
        churners = int(segment.sum())
        captured += churners
        rate = churners / users if users else 0.0
        rows.append(
            {
                "decile": decile + 1,
                "users": users,
                "churners": churners,
                "churn_rate": rate,
                "cumulative_churn_capture": captured / total_churn if total_churn else 0.0,
                "lift": rate / base_rate if base_rate else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def capture_at_fractions(y_true: np.ndarray, y_prob: np.ndarray, fractions: list[float]) -> pd.DataFrame:
    """Churners reached if CRM contacts the top slice of predicted risk."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    n = len(y_true)
    order = np.argsort(-y_prob, kind="mergesort")
    y_sorted = y_true[order]
    total = float(y_true.sum())
    base = total / n if n else 0.0
    rows = []
    for fraction in fractions:
        k = max(1, int(round(n * fraction)))
        churners = int(y_sorted[:k].sum())
        rate = churners / k
        rows.append(
            {
                "contact_fraction": fraction,
                "users_contacted": k,
                "churners_captured": churners,
                "precision_at_k": rate,
                "recall_at_k": churners / total if total else 0.0,
                "lift": rate / base if base else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def curve_points(y_true: np.ndarray, y_prob: np.ndarray, max_points: int = 80) -> dict[str, list[float]]:
    """Downsample ROC and PR curves so dashboards do not need the raw scores."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    precision, recall, _ = precision_recall_curve(y_true, y_prob)

    def _take(a: np.ndarray, b: np.ndarray) -> tuple[list[float], list[float]]:
        if len(a) <= max_points:
            idx = np.arange(len(a))
        else:
            idx = np.linspace(0, len(a) - 1, max_points, dtype=int)
        return a[idx].astype(float).tolist(), b[idx].astype(float).tolist()

    fpr_s, tpr_s = _take(fpr, tpr)
    recall_s, precision_s = _take(recall, precision)
    return {
        "fpr": fpr_s,
        "tpr": tpr_s,
        "recall": recall_s,
        "precision": precision_s,
    }


def population_stability_index(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """PSI of ``actual`` against the ``expected`` (reference) distribution."""
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if len(expected) < bins or len(actual) == 0:
        return float("nan")
    breaks = np.quantile(expected, np.linspace(0, 1, bins + 1))
    breaks = np.unique(breaks)
    if len(breaks) < 3:
        return 0.0
    breaks[0] = -np.inf
    breaks[-1] = np.inf
    expected_pct = np.histogram(expected, bins=breaks)[0] / len(expected)
    actual_pct = np.histogram(actual, bins=breaks)[0] / len(actual)
    expected_pct = np.clip(expected_pct, 1e-4, None)
    actual_pct = np.clip(actual_pct, 1e-4, None)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))
