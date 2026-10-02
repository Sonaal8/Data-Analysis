"""Estimators that fit preprocessing inside ``fit`` so CV folds stay clean."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.preprocessing import CATEGORICAL_FEATURES, TreePrep, fit_tree_prep


def balanced_sample_weight(y: np.ndarray) -> np.ndarray:
    """Weight the minority class to the majority count. Neutral for the majority."""
    y = np.asarray(y).astype(int)
    n_pos = max(int((y == 1).sum()), 1)
    n_neg = max(int((y == 0).sum()), 1)
    return np.where(y == 1, n_neg / n_pos, 1.0).astype(float)


class NativeBooster:
    """XGBoost or LightGBM on the original feature fields."""

    def __init__(self, kind: str, params: dict[str, Any]) -> None:
        if kind not in {"xgboost", "lightgbm"}:
            raise ValueError(f"Unsupported booster kind: {kind}")
        self.kind = kind
        self.params = dict(params)
        self.prep: TreePrep | None = None
        self.model: Any = None

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "NativeBooster":
        y = np.asarray(y).astype(int)
        self.prep = fit_tree_prep(X)
        transformed = self.prep.transform(X)
        if self.kind == "xgboost":
            from xgboost import XGBClassifier

            positives = max(int((y == 1).sum()), 1)
            scale = float((y == 0).sum() / positives)
            params = {**self.params, "scale_pos_weight": scale}
            self.model = XGBClassifier(**params)
            self.model.fit(transformed, y)
        else:
            from lightgbm import LGBMClassifier

            params = {**self.params, "class_weight": "balanced"}
            self.model = LGBMClassifier(**params)
            self.model.fit(transformed, y, categorical_feature=CATEGORICAL_FEATURES)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None or self.prep is None:
            raise RuntimeError("NativeBooster is not fitted")
        return self.model.predict_proba(self.prep.transform(X))


class WeightedPipelineModel:
    """Sklearn pipeline whose final step receives balanced sample weights."""

    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "WeightedPipelineModel":
        y = np.asarray(y).astype(int)
        self.pipeline.fit(X, y, clf__sample_weight=balanced_sample_weight(y))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(X)
