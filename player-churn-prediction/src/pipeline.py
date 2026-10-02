"""Run the churn and retention pipeline from raw generation through monitoring."""

from __future__ import annotations

import argparse
import logging

from src.config import configure_logging, load_config
from src.data_generation import generate_raw_data
from src.eda_report import build_eda
from src.explain import explain_model
from src.feature_engineering import build_features
from src.monitoring import run_monitoring
from src.predict import score_players
from src.segmentation import build_segments
from src.train import train_models

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Player churn and retention pipeline")
    parser.add_argument("--n-users", type=int, default=None, help="Override config n_users")
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--skip-features", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()
    cfg = load_config()
    if not args.skip_generate:
        generate_raw_data(cfg, n_users=args.n_users)
    if not args.skip_features:
        build_features(cfg)
    build_eda(cfg)
    if not args.skip_train:
        train_models(cfg)
        explain_model(cfg)
        build_segments(cfg)
        score_players(cfg)
        run_monitoring(cfg)
    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
