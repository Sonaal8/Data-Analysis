"""Rule-based retention actions on top of model risk.

The model estimates the chance a player has no games in the next 30 days.
It does not estimate the effect of an offer. Actions are routing rules for
CRM, Product, and VIP operations. When several rules match, priority is:

1. High-value / VIP — protect revenue first
2. Recent withdrawal — the player may already be cashing out
3. Deposit decline — possible payment or trust friction
4. Activity decline — engagement journey
5. Low recent activity — low-friction re-engagement
6. Otherwise a standard high-risk engagement journey

LOW risk stays on the normal lifecycle. MEDIUM risk is a watchlist, not a
discount program. Thresholds come from config and from the scored population
(rake quantile, games quantile) so they can be changed without a retrain.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def assign_risk_band(probability: pd.Series, medium: float, high: float, critical: float) -> pd.Series:
    """Map probabilities to LOW / MEDIUM / HIGH / CRITICAL."""
    bands = np.full(len(probability), "LOW", dtype=object)
    values = probability.to_numpy(dtype=float)
    bands[values >= medium] = "MEDIUM"
    bands[values >= high] = "HIGH"
    bands[values >= critical] = "CRITICAL"
    return pd.Series(bands, index=probability.index)


def recommend_actions(
    scored: pd.DataFrame,
    retention_cfg: dict[str, Any],
) -> pd.Series:
    """Return one recommended action per scored player."""
    required = {
        "risk_band",
        "vip_segment",
        "lifetime_rake",
        "days_since_last_withdrawal",
        "never_withdrew",
        "deposit_decline_flag",
        "activity_decline_flag",
        "active_days_30d",
        "games_30d",
    }
    missing = required - set(scored.columns)
    if missing:
        raise KeyError(f"Retention rules need columns {sorted(missing)}")

    high_vips = set(retention_cfg["high_value_vip"])
    rake_q = float(retention_cfg["high_value_rake_quantile"])
    recent_days = float(retention_cfg["recent_withdrawal_days"])
    low_days = float(retention_cfg["low_activity_active_days_max"])
    games_q = float(retention_cfg["low_activity_games_quantile"])
    rake_cut = float(scored["lifetime_rake"].quantile(rake_q))
    games_cut = float(scored["games_30d"].quantile(games_q))

    actions: list[str] = []
    for row in scored.itertuples(index=False):
        band = row.risk_band
        if band == "LOW":
            actions.append("Normal lifecycle engagement")
            continue
        if band == "MEDIUM":
            actions.append("Watchlist: light lifecycle nudge, no heavy incentive")
            continue
        prefix = "Urgent — " if band == "CRITICAL" else ""
        high_value = row.vip_segment in high_vips or float(row.lifetime_rake) >= rake_cut
        recent_withdrawal = int(row.never_withdrew) == 0 and float(row.days_since_last_withdrawal) <= recent_days
        if high_value:
            actions.append(prefix + "Priority VIP retention")
        elif recent_withdrawal:
            actions.append(prefix + "Win-back and product-experience review after a recent withdrawal")
        elif int(row.deposit_decline_flag) == 1:
            actions.append(prefix + "Payment and deposit-friction investigation plus reactivation comms")
        elif int(row.activity_decline_flag) == 1:
            actions.append(prefix + "Engagement journey")
        elif int(row.active_days_30d) <= low_days or float(row.games_30d) <= games_cut:
            actions.append(prefix + "Low-friction re-engagement")
        else:
            actions.append(prefix + "Engagement journey")
    return pd.Series(actions, index=scored.index, name="recommended_action")
