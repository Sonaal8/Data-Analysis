"""Feature lists and matrix preparation.

Logistic regression uses scaled numerics and one-hot categories.
Tree boosters use the original fields, with categories kept as pandas
categorical dtype so splits stay on the business feature rather than on
dummy columns.

Gender, age, city, and campaign are available for EDA and are not model
inputs. Gender is excluded so the scorer is not a demographic screen.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES: list[str] = [
    "games_7d",
    "games_14d",
    "games_30d",
    "active_days_7d",
    "active_days_30d",
    "sessions_7d",
    "sessions_30d",
    "avg_session_duration",
    "total_play_time",
    "avg_games_per_active_day",
    "days_since_last_game",
    "days_since_last_login",
    "days_since_last_deposit",
    "days_since_last_withdrawal",
    "never_deposited",
    "never_withdrew",
    "games_per_day",
    "sessions_per_active_day",
    "deposit_amount_7d",
    "deposit_amount_30d",
    "withdrawal_amount_30d",
    "net_deposit_30d",
    "rake_7d",
    "rake_30d",
    "avg_entry_fee",
    "total_entry_fee",
    "games_change_7d_vs_previous_7d",
    "games_change_14d_vs_previous_14d",
    "deposit_change_7d_vs_previous_7d",
    "rake_change_7d_vs_previous_7d",
    "session_change_7d_vs_previous_7d",
    "game_frequency_std",
    "deposit_frequency_std",
    "session_duration_std",
    "lifetime_games",
    "lifetime_deposit",
    "lifetime_rake",
    "player_tenure_days",
    "tournament_affinity",
    "pool_affinity",
    "points_affinity",
    "deals_affinity",
    "bonus_received_30d",
    "bonus_used_30d",
    "cashback_received_30d",
    "bonus_dependency_ratio",
    "activity_decline_flag",
    "deposit_decline_flag",
    "reduced_session_flag",
    "high_withdrawal_to_deposit_ratio",
    "inactivity_gap_days",
]

CATEGORICAL_FEATURES: list[str] = [
    "vip_segment",
    "device_type",
    "acquisition_channel",
    "registration_platform",
    "preferred_game_type",
    "preferred_game_variant",
]

# Present on the analytical table and intentionally absent from the estimator.
EXCLUDED_FROM_MODEL: list[str] = [
    "user_id",
    "prediction_date",
    "dataset_split",
    "registration_date",
    "registration_cohort",
    "tenure_bucket",
    "age",
    "gender",
    "city",
    "state",
    "acquisition_campaign",
    "churned",
    "games_in_label_window",
    "games_per_active_day",  # identical to avg_games_per_active_day
    "games_prev_7d",
    "games_prev_14d",
    "deposit_prev_7d",
    "rake_prev_7d",
    "sessions_prev_7d",
    "rolling_games_7d",
    "last_game_date",
    "last_login_date",
    "last_deposit_date",
    "last_withdrawal_date",
    "rake_rank_in_vip",
    "deposit_dense_rank",
    "rake_quartile",
]

LABEL_COLUMN = "churned"
LEAKAGE_COLUMNS = ("churned", "games_in_label_window")


def model_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return the raw modeling columns in a stable order."""
    missing = [col for col in NUMERIC_FEATURES + CATEGORICAL_FEATURES if col not in df.columns]
    if missing:
        raise KeyError(f"Modeling frame is missing columns: {missing}")
    leaked = [col for col in LEAKAGE_COLUMNS if col in NUMERIC_FEATURES or col in CATEGORICAL_FEATURES]
    if leaked:
        raise RuntimeError(f"Label columns are listed as features: {leaked}")
    return df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()


@dataclass
class TreePrep:
    """Train-fitted imputers and category levels for native tree boosters."""

    numeric_features: list[str]
    categorical_features: list[str]
    medians: dict[str, float]
    modes: dict[str, str]
    categories: dict[str, list[str]]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)
        for col in self.numeric_features:
            values = pd.to_numeric(df[col], errors="coerce")
            out[col] = values.fillna(self.medians[col]).astype(float)
        for col in self.categorical_features:
            raw = df[col].astype("object")
            filled = raw.where(raw.notna(), self.modes[col]).fillna(self.modes[col]).astype(str)
            out[col] = pd.Categorical(filled, categories=self.categories[col])
        return out[self.numeric_features + self.categorical_features]


def fit_tree_prep(df: pd.DataFrame) -> TreePrep:
    """Fit imputation statistics on the training fold only."""
    numeric = df[NUMERIC_FEATURES].apply(pd.to_numeric, errors="coerce")
    medians = {col: float(numeric[col].median()) if numeric[col].notna().any() else 0.0 for col in NUMERIC_FEATURES}
    modes: dict[str, str] = {}
    categories: dict[str, list[str]] = {}
    for col in CATEGORICAL_FEATURES:
        series = df[col].dropna().astype(str)
        modes[col] = str(series.mode().iloc[0]) if not series.empty else "Unknown"
        levels = sorted(series.unique().tolist())
        if modes[col] not in levels:
            levels.append(modes[col])
        categories[col] = levels
    return TreePrep(list(NUMERIC_FEATURES), list(CATEGORICAL_FEATURES), medians, modes, categories)


def make_one_hot_preprocessor(scale_numeric: bool) -> ColumnTransformer:
    """Impute and encode. Scaling is for linear models only."""
    numeric_steps: list[tuple[str, SimpleImputer | StandardScaler]] = [
        ("imputer", SimpleImputer(strategy="median"))
    ]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))
    return ColumnTransformer(
        transformers=[
            ("numeric", Pipeline(numeric_steps), NUMERIC_FEATURES),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("one_hot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )
