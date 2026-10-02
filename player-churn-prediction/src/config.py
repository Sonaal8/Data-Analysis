"""Load project configuration and resolve paths from the repository root."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


@dataclass(frozen=True)
class ProjectConfig:
    """Runtime configuration. Paths are resolved against the project root."""

    seed: int
    n_users: int
    chunk_size: int
    registration_start: date
    registration_end: date
    history_start: date
    detail_start: date
    data_end: date
    prediction_dates: dict[str, date]
    feature_days: int
    label_days: int
    risk_medium: float
    risk_high: float
    risk_critical: float
    decline_rules: dict[str, float]
    retention: dict[str, Any]
    model: dict[str, Any]
    paths: dict[str, str]
    project_root: Path = PROJECT_ROOT

    def path(self, key: str) -> Path:
        """Return an absolute path for a configured relative directory."""
        if key not in self.paths:
            raise KeyError(f"Unknown path key: {key}")
        return self.project_root / self.paths[key]

    def ensure_directories(self) -> None:
        for key in self.paths:
            directory = self.path(key)
            if directory.suffix:
                directory.parent.mkdir(parents=True, exist_ok=True)
            else:
                directory.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Path | None = None) -> ProjectConfig:
    """Load and validate ``config/config.yaml``."""
    path = config_path or CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping")

    prediction_dates = {name: _parse_date(value) for name, value in raw["prediction_dates"].items()}
    for required in ("train", "valid", "test"):
        if required not in prediction_dates:
            raise ValueError(f"prediction_dates.{required} is required")
    if not (prediction_dates["train"] < prediction_dates["valid"] < prediction_dates["test"]):
        raise ValueError("Prediction dates must be strictly increasing: train < valid < test")

    bands = raw["risk_bands"]
    medium, high, critical = float(bands["medium"]), float(bands["high"]), float(bands["critical"])
    if not (0 < medium < high < critical < 1):
        raise ValueError("Risk bands must satisfy 0 < medium < high < critical < 1")

    windows = raw["windows"]
    feature_days = int(windows["feature_days"])
    label_days = int(windows["label_days"])
    if feature_days <= 0 or label_days <= 0:
        raise ValueError("Feature and label windows must be positive")

    calendar = raw["calendar"]
    cfg = ProjectConfig(
        seed=int(raw["seed"]),
        n_users=int(raw["n_users"]),
        chunk_size=int(raw["chunk_size"]),
        registration_start=_parse_date(calendar["registration_start"]),
        registration_end=_parse_date(calendar["registration_end"]),
        history_start=_parse_date(calendar["history_start"]),
        detail_start=_parse_date(calendar["detail_start"]),
        data_end=_parse_date(calendar["data_end"]),
        prediction_dates=prediction_dates,
        feature_days=feature_days,
        label_days=label_days,
        risk_medium=medium,
        risk_high=high,
        risk_critical=critical,
        decline_rules={k: float(v) for k, v in raw["decline_rules"].items()},
        retention=dict(raw["retention"]),
        model=dict(raw["model"]),
        paths=dict(raw["paths"]),
    )
    if cfg.n_users < 1000:
        raise ValueError("n_users must be at least 1,000")
    if cfg.data_end < cfg.prediction_dates["test"]:
        raise ValueError("data_end must cover the test prediction date")
    return cfg


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for CLI entry points."""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
