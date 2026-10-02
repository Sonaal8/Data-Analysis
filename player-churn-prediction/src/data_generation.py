"""Synthetic online-gaming event generator.

The simulator creates player, game, wallet, session, and bonus events with
overlapping behavioral archetypes. Churn is not a formula of any single
feature: a latent exit date censors future play, while observed history is a
noisy function of archetype, trend, and day-level randomness.

Labels are NOT written here. They are derived later from games on or after
each prediction date. Nothing in this module reads the future to build a
feature; feature queries live in ``sql/`` and ``feature_engineering.py``.

This project uses synthetic data inspired by common online gaming analytics
use cases. It does not contain confidential or proprietary Junglee Games data.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ProjectConfig, configure_logging, load_config

logger = logging.getLogger(__name__)

ARCHETYPES: tuple[str, ...] = (
    "loyal_regular",
    "casual",
    "declining",
    "low_value_engaged",
    "promo_sensitive",
    "new_unstable",
    "vip_stable",
    "vip_at_risk",
    "high_activity_churner",
)
# Cohort order: loyal, april_exit, may_exit, june_exit, intermittent
COHORTS: tuple[str, ...] = (
    "loyal",
    "april_exit",
    "may_exit",
    "june_exit",
    "intermittent",
)
ARCHETYPE_PROBS: np.ndarray = np.array(
    [0.22, 0.18, 0.14, 0.10, 0.08, 0.08, 0.07, 0.07, 0.06], dtype=float
)
# Rows follow ARCHETYPES; columns follow COHORTS.
ARCHETYPE_COHORT_PROBS: np.ndarray = np.array(
    [
        [0.74, 0.08, 0.06, 0.05, 0.07],  # loyal_regular
        [0.36, 0.19, 0.15, 0.13, 0.17],  # casual
        [0.16, 0.30, 0.24, 0.22, 0.08],  # declining
        [0.66, 0.09, 0.08, 0.07, 0.10],  # low_value_engaged
        [0.38, 0.16, 0.14, 0.12, 0.20],  # promo_sensitive
        [0.22, 0.17, 0.20, 0.21, 0.20],  # new_unstable
        [0.78, 0.06, 0.05, 0.04, 0.07],  # vip_stable
        [0.20, 0.24, 0.22, 0.24, 0.10],  # vip_at_risk
        [0.12, 0.22, 0.26, 0.30, 0.10],  # high_activity_churner
    ],
    dtype=float,
)
DAILY_P: dict[str, float] = {
    "loyal_regular": 0.24,
    "casual": 0.07,
    "declining": 0.18,
    "low_value_engaged": 0.28,
    "promo_sensitive": 0.09,
    "new_unstable": 0.11,
    "vip_stable": 0.20,
    "vip_at_risk": 0.16,
    "high_activity_churner": 0.30,
}
GAMES_LAMBDA: dict[str, float] = {
    "loyal_regular": 5.0,
    "casual": 2.0,
    "declining": 4.0,
    "low_value_engaged": 8.0,
    "promo_sensitive": 2.4,
    "new_unstable": 3.0,
    "vip_stable": 4.0,
    "vip_at_risk": 3.2,
    "high_activity_churner": 7.0,
}
CHANNEL_P_MULT: dict[str, float] = {
    "Organic": 1.00,
    "Referral": 1.06,
    "Google Ads": 0.96,
    "Facebook": 0.94,
    "Affiliate": 0.90,
    "Influencer": 0.95,
}
GAME_TYPES: tuple[str, ...] = (
    "Points Rummy",
    "Pool Rummy",
    "Deals Rummy",
    "Tournaments",
)
VARIANTS: dict[str, tuple[str, ...]] = {
    "Points Rummy": ("0.10 per point", "0.25 per point", "1 per point"),
    "Pool Rummy": ("101 Pool", "201 Pool"),
    "Deals Rummy": ("Best of 2", "Best of 3", "Best of 6"),
    "Tournaments": ("Sit and Go", "Free Roll", "Grand Slam"),
}
FEE_LADDER: dict[str, tuple[float, ...]] = {
    "Regular": (5, 10, 25, 50),
    "Bronze": (10, 25, 50),
    "Silver": (25, 50, 100, 250),
    "Gold": (50, 100, 250, 500),
    "Platinum": (100, 250, 500, 1000),
    "Diamond": (250, 500, 1000, 2500),
}
DEPOSIT_MU: dict[str, float] = {
    "Regular": 5.4,
    "Bronze": 5.9,
    "Silver": 6.5,
    "Gold": 7.1,
    "Platinum": 7.7,
    "Diamond": 8.3,
}
CITY_STATE: tuple[tuple[str, str, float], ...] = (
    ("Mumbai", "Maharashtra", 0.14),
    ("Pune", "Maharashtra", 0.06),
    ("Nagpur", "Maharashtra", 0.03),
    ("Delhi", "Delhi", 0.12),
    ("Bengaluru", "Karnataka", 0.10),
    ("Hyderabad", "Telangana", 0.08),
    ("Chennai", "Tamil Nadu", 0.07),
    ("Kolkata", "West Bengal", 0.06),
    ("Ahmedabad", "Gujarat", 0.05),
    ("Surat", "Gujarat", 0.03),
    ("Jaipur", "Rajasthan", 0.04),
    ("Lucknow", "Uttar Pradesh", 0.04),
    ("Indore", "Madhya Pradesh", 0.03),
    ("Chandigarh", "Chandigarh", 0.02),
    ("Kochi", "Kerala", 0.03),
    ("Coimbatore", "Tamil Nadu", 0.02),
    ("Bhubaneswar", "Odisha", 0.02),
    ("Patna", "Bihar", 0.02),
    ("Guwahati", "Assam", 0.02),
    ("Visakhapatnam", "Andhra Pradesh", 0.02),
)
CHANNELS: tuple[str, ...] = (
    "Organic",
    "Google Ads",
    "Facebook",
    "Referral",
    "Affiliate",
    "Influencer",
)
CHANNEL_PROBS: np.ndarray = np.array([0.30, 0.22, 0.16, 0.14, 0.10, 0.08])
CAMPAIGNS: dict[str, tuple[str, ...]] = {
    "Organic": ("ORGANIC_DIRECT", "ORGANIC_SEO"),
    "Google Ads": ("GOOG_INSTALL_APR", "GOOG_BRAND_EXACT", "GOOG_UAC_SCALE"),
    "Facebook": ("META_LOOKALIKE", "META_RETARGET", "META_CRICKET_SEASON"),
    "Referral": ("REFERRAL_FRIEND50", "REFERRAL_VIP"),
    "Affiliate": ("AFF_CASHBACK_NET", "AFF_CONTENT_BLOG"),
    "Influencer": ("INF_CREATOR_A", "INF_CREATOR_B", "INF_YOUTUBE_SHORTS"),
}
VIP_LEVELS: tuple[str, ...] = ("Regular", "Bronze", "Silver", "Gold", "Platinum", "Diamond")
BONUS_TYPES: tuple[str, ...] = (
    "Welcome",
    "Reload",
    "Cashback Ticket",
    "Free Game",
    "Leaderboard",
)


def _epoch(day: date | np.datetime64 | str) -> int:
    return int(np.datetime64(str(day), "D").astype(np.int64))


def _datestr(ordinals: np.ndarray) -> np.ndarray:
    return pd.to_datetime(ordinals, unit="D").strftime("%Y-%m-%d").to_numpy()


def _choice_index(rng: np.random.Generator, probs: np.ndarray, n: int) -> np.ndarray:
    cdf = np.cumsum(probs)
    cdf[-1] = 1.0
    draws = rng.random(n)
    return np.searchsorted(cdf, draws, side="right")


def _sample_between(
    rng: np.random.Generator,
    n: int,
    start: int,
    end: int,
    lower: np.ndarray,
    upper: np.ndarray,
) -> np.ndarray:
    """Sample an inclusive ordinal in ``[start, end]`` clipped to ``[lower, upper]``.

    Returns -1 when a row has no valid day inside the requested window.
    """
    if end < start:
        raise ValueError("force window end is before start")
    draw = start + rng.integers(0, end - start + 1, size=n)
    lo = np.maximum(lower, start)
    hi = np.minimum(upper, end)
    valid = lo <= hi
    out = np.full(n, -1, dtype=np.int64)
    out[valid] = np.clip(draw[valid], lo[valid], hi[valid])
    return out


def _assign_vip(rng: np.random.Generator, archetype: np.ndarray) -> np.ndarray:
    n = len(archetype)
    vip = np.empty(n, dtype=object)
    default_p = np.array([0.58, 0.18, 0.12, 0.07, 0.04, 0.01])
    specs: dict[str, tuple[tuple[str, ...], np.ndarray]] = {
        "vip_stable": (("Gold", "Platinum", "Diamond"), np.array([0.45, 0.35, 0.20])),
        "vip_at_risk": (
            ("Silver", "Gold", "Platinum", "Diamond"),
            np.array([0.22, 0.38, 0.25, 0.15]),
        ),
        "low_value_engaged": (("Regular", "Bronze"), np.array([0.82, 0.18])),
    }
    assigned = np.zeros(n, dtype=bool)
    for name, (levels, probs) in specs.items():
        mask = archetype == name
        assigned |= mask
        if mask.any():
            idx = _choice_index(rng, probs, int(mask.sum()))
            vip[mask] = np.array(levels, dtype=object)[idx]
    rest = ~assigned
    if rest.any():
        idx = _choice_index(rng, default_p, int(rest.sum()))
        vip[rest] = np.array(VIP_LEVELS, dtype=object)[idx]
    return vip


def _assign_modes(
    rng: np.random.Generator, archetype: np.ndarray, cohort: np.ndarray
) -> np.ndarray:
    """Behavior mode: stable, gradual_exit, shock_exit, temporary_dip."""
    n = len(archetype)
    mode = np.full(n, "stable", dtype=object)
    exit_mask = np.isin(cohort, ("april_exit", "may_exit", "june_exit"))
    shock_draw = rng.random(n)
    gradual = exit_mask & (
        np.isin(archetype, ("declining", "new_unstable", "casual", "promo_sensitive"))
        | (shock_draw >= 0.35)
    )
    # High-activity and a slice of otherwise stable players stop without a fade.
    shock = exit_mask & ~gradual
    shock |= exit_mask & (archetype == "high_activity_churner") & (shock_draw < 0.85)
    gradual = exit_mask & ~shock
    mode[gradual] = "gradual_exit"
    mode[shock] = "shock_exit"
    dip = (cohort == "loyal") & (rng.random(n) < 0.18)
    mode[dip] = "temporary_dip"
    return mode


def _play_end_ordinal(cohort: np.ndarray, data_end: int) -> np.ndarray:
    ends = {
        "loyal": data_end,
        "intermittent": data_end,
        "april_exit": _epoch(date(2025, 4, 14)),
        "may_exit": _epoch(date(2025, 5, 14)),
        "june_exit": _epoch(date(2025, 6, 14)),
    }
    out = np.empty(len(cohort), dtype=np.int64)
    for name, value in ends.items():
        out[cohort == name] = value
    return out


def _build_forces(
    rng: np.random.Generator,
    cohort: np.ndarray,
    mode: np.ndarray,
    reg: np.ndarray,
    play_end: np.ndarray,
) -> np.ndarray:
    """Return an (n, 8) matrix of forced play dates, -1 if unused.

    Forced dates keep cohort labels identifiable without making any one
    pre-period feature a deterministic function of churn. Shock exits are
    anchored near the censor date; gradual exits are anchored earlier so a
    fade is visible. Loyal players are anchored near each snapshot so the
    active base is actually active, plus once inside each label window.
    """
    n = len(cohort)
    slots: list[np.ndarray] = []

    def add(mask: np.ndarray, start: date, end: date) -> None:
        draw = _sample_between(rng, n, _epoch(start), _epoch(end), reg, play_end)
        draw = np.where(mask, draw, -1)
        slots.append(draw.astype(np.int64))

    loyal = cohort == "loyal"
    april = cohort == "april_exit"
    may = cohort == "may_exit"
    june = cohort == "june_exit"
    shock = mode == "shock_exit"
    gradual = mode == "gradual_exit"
    dip = mode == "temporary_dip"
    active_after_april = np.isin(cohort, ("loyal", "may_exit", "june_exit", "intermittent"))
    # Intermittent players are left unforced so 30-day gaps arise naturally.

    # April snapshot anchors (prediction date 2025-04-15).
    add(loyal | may | june | (april & shock), date(2025, 4, 9), date(2025, 4, 14))
    add(april & gradual, date(2025, 3, 22), date(2025, 4, 2))
    add((april & gradual) & (rng.random(n) < 0.45), date(2025, 4, 5), date(2025, 4, 8))
    # Retained through the April label window.
    add(loyal | may | june, date(2025, 4, 16), date(2025, 5, 8))

    # May snapshot anchors (prediction date 2025-05-15).
    add((loyal & ~dip) | (june & shock) | (may & shock), date(2025, 5, 9), date(2025, 5, 14))
    add(may & gradual, date(2025, 4, 20), date(2025, 5, 2))
    add(june & gradual, date(2025, 5, 8), date(2025, 5, 14))
    add(loyal | june, date(2025, 5, 16), date(2025, 6, 6))

    # June snapshot anchors (prediction date 2025-06-15).
    add((loyal & ~dip) | (june & shock), date(2025, 6, 8), date(2025, 6, 14))
    add(june & gradual, date(2025, 5, 18), date(2025, 5, 30))
    add(loyal, date(2025, 6, 18), date(2025, 7, 8))

    # Dips still need an earlier anchor so they remain inside the active base.
    add(dip, date(2025, 5, 20), date(2025, 6, 2))
    # A minority of dips show a small recovery game; the rest stay quiet and return later.
    add(dip & (rng.random(n) < 0.35), date(2025, 6, 11), date(2025, 6, 14))

    # Keep the matrix rectangular.
    while len(slots) < 8:
        slots.append(np.full(n, -1, dtype=np.int64))
    forces = np.column_stack(slots[:8])
    # Drop anchors that fall outside the player's allowed calendar.
    invalid = (forces >= 0) & ((forces < reg[:, None]) | (forces > play_end[:, None]))
    forces = forces.copy()
    forces[invalid] = -1
    return forces


def build_users(cfg: ProjectConfig, n_users: int, rng: np.random.Generator) -> pd.DataFrame:
    """Create the player dimension and latent simulator attributes."""
    n = n_users
    arch_idx = _choice_index(rng, ARCHETYPE_PROBS, n)
    archetype = np.array(ARCHETYPES, dtype=object)[arch_idx]
    cohort_draw = rng.random(n)
    cohort_cdf = np.cumsum(ARCHETYPE_COHORT_PROBS, axis=1)
    cohort_cdf[:, -1] = 1.0
    cohort_idx = np.clip(np.sum(cohort_draw[:, None] > cohort_cdf[arch_idx], axis=1), 0, len(COHORTS) - 1)
    cohort = np.array(COHORTS, dtype=object)[cohort_idx]

    reg_start = _epoch(cfg.registration_start)
    reg_end_general = _epoch(date(2025, 4, 30))
    new_start = _epoch(date(2025, 2, 1))
    new_end = _epoch(cfg.registration_end)
    reg = rng.integers(reg_start, reg_end_general + 1, size=n)
    new_mask = archetype == "new_unstable"
    reg[new_mask] = rng.integers(new_start, new_end + 1, size=int(new_mask.sum()))
    # A slice of non-new players are recent acquisitions too.
    recent = (~new_mask) & (rng.random(n) < 0.12)
    reg[recent] = rng.integers(_epoch(date(2025, 1, 1)), _epoch(date(2025, 5, 20)) + 1, size=int(recent.sum()))

    data_end = _epoch(cfg.data_end)
    play_end = _play_end_ordinal(cohort, data_end)
    # Exit cohorts that registered after they would have stopped are reassigned.
    too_late = reg > play_end
    cohort = cohort.copy()
    play_end = play_end.copy()
    cohort[too_late] = "loyal"
    play_end[too_late] = data_end

    mode = _assign_modes(rng, archetype, cohort)
    vip = _assign_vip(rng, archetype)

    channel_idx = _choice_index(rng, CHANNEL_PROBS, n)
    channel = np.array(CHANNELS, dtype=object)[channel_idx]
    # Modest acquisition-quality shift, not a hard rule.
    affiliate = channel == "Affiliate"
    flip_to_exit = affiliate & (cohort == "loyal") & (rng.random(n) < 0.08)
    cohort = cohort.copy()
    play_end = play_end.copy()
    cohort[flip_to_exit] = "june_exit"
    play_end[flip_to_exit] = _epoch(date(2025, 6, 14))
    referral_save = (channel == "Referral") & np.isin(cohort, ("may_exit", "june_exit")) & (rng.random(n) < 0.10)
    cohort[referral_save] = "loyal"
    play_end[referral_save] = data_end
    mode = _assign_modes(rng, archetype, cohort)

    daily_p = np.array([DAILY_P[a] for a in archetype])
    daily_p *= np.array([CHANNEL_P_MULT[c] for c in channel])
    device_roll = rng.random(n)
    device = np.where(device_roll < 0.68, "Android", np.where(device_roll < 0.90, "iOS", "Web"))
    daily_p *= np.where(device == "Web", 0.90, np.where(device == "iOS", 0.97, 1.0))
    daily_p = np.clip(daily_p, 0.02, 0.55)
    games_lambda = np.array([GAMES_LAMBDA[a] for a in archetype])

    forces = _build_forces(rng, cohort, mode, reg, play_end)

    city_p = np.array([row[2] for row in CITY_STATE])
    city_p = city_p / city_p.sum()
    city_idx = _choice_index(rng, city_p, n)
    city = np.array([CITY_STATE[i][0] for i in city_idx], dtype=object)
    state = np.array([CITY_STATE[i][1] for i in city_idx], dtype=object)

    gender_roll = rng.random(n)
    gender = np.where(
        gender_roll < 0.58,
        "Male",
        np.where(gender_roll < 0.93, "Female", np.where(gender_roll < 0.97, "Non-binary", "Prefer not to say")),
    )
    age = rng.triangular(18, 26, 58, size=n).astype(np.int64)
    age = np.clip(age, 18, 65)
    age[new_mask] = rng.integers(18, 32, size=int(new_mask.sum()))

    platform_roll = rng.random(n)
    platform = np.where(
        platform_roll < 0.62,
        "Android",
        np.where(platform_roll < 0.84, "iOS", np.where(platform_roll < 0.95, "Web", "Desktop")),
    )
    campaigns = np.empty(n, dtype=object)
    for name, options in CAMPAIGNS.items():
        mask = channel == name
        if mask.any():
            pick = rng.integers(0, len(options), size=int(mask.sum()))
            campaigns[mask] = np.array(options, dtype=object)[pick]

    type_prefs = rng.dirichlet((2.2, 2.0, 1.8, 1.1), size=n)
    # Low-value grinders prefer points/pool; VIPs a bit more tournament-curious.
    type_prefs[archetype == "low_value_engaged", 0] += 0.8
    type_prefs[archetype == "low_value_engaged"] /= type_prefs[archetype == "low_value_engaged"].sum(axis=1, keepdims=True)
    vip_heavy = np.isin(vip, ("Platinum", "Diamond"))
    type_prefs[vip_heavy, 3] += 0.5
    type_prefs[vip_heavy] /= type_prefs[vip_heavy].sum(axis=1, keepdims=True)

    favorite_variant = np.empty((n, 4), dtype=object)
    for t_i, gtype in enumerate(GAME_TYPES):
        options = VARIANTS[gtype]
        favorite_variant[:, t_i] = np.array(options, dtype=object)[rng.integers(0, len(options), size=n)]

    users = pd.DataFrame(
        {
            "user_id": np.arange(10_000_001, 10_000_001 + n, dtype=np.int64),
            "registration_date": _datestr(reg),
            "age": age,
            "gender": gender,
            "city": city,
            "state": state,
            "device_type": device,
            "acquisition_channel": channel,
            "acquisition_campaign": campaigns,
            "registration_platform": platform,
            "vip_segment": vip,
            "reg_ord": reg,
            "play_end_ord": play_end,
            "daily_p": daily_p,
            "games_lambda": games_lambda,
            "archetype": archetype,
            "cohort": cohort,
            "mode": mode,
        }
    )
    for i in range(forces.shape[1]):
        users[f"force_{i}"] = forces[:, i]
    for t_i in range(4):
        users[f"pref_{t_i}"] = type_prefs[:, t_i]
        users[f"fav_{t_i}"] = favorite_variant[:, t_i]

    _assert_calendar(users)
    return users


def _assert_calendar(users: pd.DataFrame) -> None:
    june_end = _epoch(date(2025, 6, 14))
    may_end = _epoch(date(2025, 5, 14))
    april_end = _epoch(date(2025, 4, 14))
    if not (users.loc[users["cohort"] == "june_exit", "play_end_ord"] <= june_end).all():
        raise RuntimeError("June exit cohort can play on or after the June prediction date")
    if not (users.loc[users["cohort"] == "may_exit", "play_end_ord"] <= may_end).all():
        raise RuntimeError("May exit cohort calendar is invalid")
    if not (users.loc[users["cohort"] == "april_exit", "play_end_ord"] <= april_end).all():
        raise RuntimeError("April exit cohort calendar is invalid")
    force_cols = [c for c in users.columns if c.startswith("force_")]
    forces = users[force_cols].to_numpy()
    reg = users["reg_ord"].to_numpy()
    end = users["play_end_ord"].to_numpy()
    bad = (forces >= 0) & ((forces < reg[:, None]) | (forces > end[:, None]))
    if bad.any():
        raise RuntimeError("Forced play dates fall outside a player's calendar")


def _apply_forces(played: np.ndarray, forces: np.ndarray, recent_start: int, n_days: int) -> None:
    n = played.shape[0]
    for slot in range(forces.shape[1]):
        force = forces[:, slot]
        valid = force >= 0
        if not valid.any():
            continue
        idx = force[valid] - recent_start
        in_grid = (idx >= 0) & (idx < n_days)
        rows = np.flatnonzero(valid)[in_grid]
        cols = idx[in_grid]
        played[rows, cols] = True


def _simulate_chunk(
    users: pd.DataFrame,
    rng: np.random.Generator,
    cfg: ProjectConfig,
    id_state: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Simulate events for a user chunk and return the four event frames."""
    n = len(users)
    recent_start = _epoch(cfg.detail_start)
    recent_end = _epoch(cfg.data_end)
    recent_days = np.arange(recent_start, recent_end + 1, dtype=np.int64)
    n_days = len(recent_days)
    reg = users["reg_ord"].to_numpy()
    play_end = users["play_end_ord"].to_numpy()
    daily_p = users["daily_p"].to_numpy()
    mode = users["mode"].to_numpy()
    force_cols = [c for c in users.columns if c.startswith("force_")]
    forces = users[force_cols].to_numpy(dtype=np.int64)

    days = recent_days[None, :]
    eligible = (days >= reg[:, None]) & (days <= play_end[:, None])
    days_before_stop = play_end[:, None] - days
    decay = np.ones((n, n_days), dtype=np.float32)
    gradual = (mode == "gradual_exit")[:, None]
    decay_zone = gradual & (days_before_stop >= 0) & (days_before_stop <= 21)
    decay = np.where(decay_zone, np.clip(days_before_stop / 21.0, 0.18, 1.0), decay).astype(np.float32)

    dip = mode == "temporary_dip"
    if dip.any():
        dip_start = play_end[dip] - 16
        # Quiet stretch near the June feature window, then a possible return after prediction.
        in_dip = dip[:, None] & (days >= (play_end - 16)[:, None]) & (days <= (play_end - 4)[:, None])
        # For loyal dips play_end is data_end (July). A July-relative dip misses June.
        # Place the dip explicitly against the June prediction date.
        june_pred = _epoch(cfg.prediction_dates["test"])
        in_dip = dip[:, None] & (days >= (june_pred - 18)) & (days <= (june_pred - 3))
        decay = np.where(in_dip, decay * 0.22, decay)
        del dip_start

    weekday = (recent_days + 3) % 7  # Monday = 0, epoch day 0 was Thursday
    weekend = np.where(weekday >= 5, 1.15, 1.0).astype(np.float32)
    prob = daily_p[:, None] * decay * weekend[None, :]
    prob = np.clip(prob, 0.0, 0.85)
    prob = np.where(eligible, prob, 0.0)
    played = rng.random((n, n_days)) < prob
    _apply_forces(played, forces, recent_start, n_days)
    played &= eligible

    user_idx, day_idx = np.nonzero(played)
    if len(user_idx) == 0:
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    uid = users["user_id"].to_numpy()[user_idx]
    date_ord = recent_days[day_idx]
    row_mode = mode[user_idx]
    row_vip = users["vip_segment"].to_numpy()[user_idx]
    row_arch = users["archetype"].to_numpy()[user_idx]
    row_device = users["device_type"].to_numpy()[user_idx]
    row_lambda = users["games_lambda"].to_numpy()[user_idx]
    row_play_end = play_end[user_idx]
    prefs = users[[f"pref_{i}" for i in range(4)]].to_numpy(dtype=float)[user_idx]
    favs = users[[f"fav_{i}" for i in range(4)]].to_numpy()[user_idx]

    u = rng.random(len(user_idx))
    cdf = np.cumsum(prefs, axis=1)
    cdf[:, -1] = 1.0
    type_idx = np.argmax(u[:, None] <= cdf, axis=1)
    game_type = np.array(GAME_TYPES, dtype=object)[type_idx]
    # Mostly the favorite variant, occasionally a neighbour in the same family.
    variant = favs[np.arange(len(user_idx)), type_idx]
    switch = rng.random(len(user_idx)) < 0.18
    if switch.any():
        switched = game_type[switch]
        alt = np.empty(int(switch.sum()), dtype=object)
        for i, gtype in enumerate(switched):
            options = VARIANTS[gtype]
            alt[i] = options[int(rng.integers(0, len(options)))]
        variant = variant.copy()
        variant[switch] = alt

    base_fee = np.empty(len(user_idx), dtype=float)
    for level, ladder in FEE_LADDER.items():
        mask = row_vip == level
        if mask.any():
            pick = rng.integers(0, len(ladder), size=int(mask.sum()))
            base_fee[mask] = np.array(ladder)[pick]
    if np.isin(row_arch, ("low_value_engaged",)).any():
        low = row_arch == "low_value_engaged"
        base_fee[low] = np.minimum(base_fee[low], 25)
    entry_fee = np.round(base_fee * rng.uniform(0.9, 1.1, size=len(user_idx)), 2)
    entry_fee = np.clip(entry_fee, 1, None)

    games_played = rng.poisson(row_lambda) + 1
    games_played = np.clip(games_played, 1, 36).astype(np.int64)
    duration = np.round(games_played * rng.uniform(1.8, 4.2, size=len(user_idx)), 1)
    rake_rate = rng.uniform(0.08, 0.15, size=len(user_idx))
    rake = np.round(entry_fee * games_played * rake_rate, 2)
    result_roll = rng.random(len(user_idx))
    game_result = np.where(result_roll < 0.27, "win", np.where(result_roll < 0.84, "loss", "drop"))
    tournament_flag = (game_type == "Tournaments").astype(np.int64)

    n_games = len(user_idx)
    game_ids = np.arange(id_state["game_id"], id_state["game_id"] + n_games, dtype=np.int64)
    id_state["game_id"] += n_games
    games = pd.DataFrame(
        {
            "game_id": game_ids,
            "user_id": uid,
            "game_date": _datestr(date_ord),
            "game_type": game_type,
            "game_variant": variant,
            "entry_fee": entry_fee,
            "game_result": game_result,
            "games_played": games_played,
            "duration_minutes": duration,
            "rake": rake,
            "tournament_flag": tournament_flag,
        }
    )

    # Sessions: one primary session per game day, sometimes a second sitting.
    session_duration = np.round(duration + rng.uniform(2.0, 10.0, size=n_games), 1)
    login_count = 1 + rng.poisson(0.35, size=n_games)
    versions = _app_versions(date_ord, rng)
    sessions = pd.DataFrame(
        {
            "user_id": uid,
            "session_date": games["game_date"].to_numpy(),
            "session_duration": session_duration,
            "login_count": login_count.astype(np.int64),
            "app_version": versions,
            "device_type": row_device,
            "_ord": date_ord,
        }
    )
    second = rng.random(n_games) < np.where(np.isin(row_arch, ("loyal_regular", "low_value_engaged", "high_activity_churner")), 0.22, 0.08)
    if second.any():
        extra = pd.DataFrame(
            {
                "user_id": uid[second],
                "session_date": games.loc[second, "game_date"].to_numpy(),
                "session_duration": np.round(rng.uniform(4, 18, size=int(second.sum())), 1),
                "login_count": 1 + rng.poisson(0.2, size=int(second.sum())),
                "app_version": _app_versions(date_ord[second], rng),
                "device_type": row_device[second],
                "_ord": date_ord[second],
            }
        )
        sessions = pd.concat([sessions, extra], ignore_index=True)

    # Login-only sessions on quiet days inside the allowed calendar.
    login_only_p = 0.012
    login_only = (rng.random((n, n_days)) < login_only_p) & eligible & ~played
    lo_user, lo_day = np.nonzero(login_only)
    if len(lo_user):
        lo_ord = recent_days[lo_day]
        extra_login = pd.DataFrame(
            {
                "user_id": users["user_id"].to_numpy()[lo_user],
                "session_date": _datestr(lo_ord),
                "session_duration": np.round(rng.uniform(1.0, 6.0, size=len(lo_user)), 1),
                "login_count": np.ones(len(lo_user), dtype=np.int64),
                "app_version": _app_versions(lo_ord, rng),
                "device_type": users["device_type"].to_numpy()[lo_user],
                "_ord": lo_ord,
            }
        )
        sessions = pd.concat([sessions, extra_login], ignore_index=True)
    sessions = sessions.reset_index(drop=True)
    sessions.insert(0, "session_id", np.arange(id_state["session_id"], id_state["session_id"] + len(sessions)))
    id_state["session_id"] += len(sessions)
    sessions = sessions.drop(columns=["_ord"])

    transactions, bonuses = _wallet_events(
        rng,
        users,
        user_idx,
        date_ord,
        row_vip,
        row_arch,
        row_mode,
        row_play_end,
        entry_fee,
        id_state,
    )

    hist_games, hist_tx, hist_bonus, hist_sessions = _historical_events(users, rng, cfg, id_state)
    if not hist_games.empty:
        games = pd.concat([hist_games, games], ignore_index=True)
    if not hist_sessions.empty:
        sessions = pd.concat([hist_sessions, sessions], ignore_index=True)
    if not hist_tx.empty:
        transactions = pd.concat([hist_tx, transactions], ignore_index=True)
    if not hist_bonus.empty:
        bonuses = pd.concat([hist_bonus, bonuses], ignore_index=True)
    return games, sessions, transactions, bonuses


def _app_versions(ordinals: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    v1, v2, v3 = _epoch(date(2025, 1, 15)), _epoch(date(2025, 3, 20)), _epoch(date(2025, 5, 18))
    versions = np.where(
        ordinals < v1,
        "5.4.2",
        np.where(ordinals < v2, "5.5.0", np.where(ordinals < v3, "5.6.1", "6.0.0")),
    ).astype(object)
    missing = rng.random(len(ordinals)) < 0.02
    versions[missing] = None
    return versions


def _wallet_events(
    rng: np.random.Generator,
    users: pd.DataFrame,
    user_idx: np.ndarray,
    date_ord: np.ndarray,
    vip: np.ndarray,
    archetype: np.ndarray,
    mode: np.ndarray,
    play_end: np.ndarray,
    entry_fee: np.ndarray,
    id_state: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(user_idx)
    deposit_p = np.array([{"Regular": 0.16, "Bronze": 0.18, "Silver": 0.20, "Gold": 0.24, "Platinum": 0.27, "Diamond": 0.30}[v] for v in vip])
    deposit_p = np.where(archetype == "promo_sensitive", deposit_p * 0.75, deposit_p)
    days_before = play_end - date_ord
    deposit_p = np.where((mode == "gradual_exit") & (days_before <= 14), deposit_p * 0.45, deposit_p)
    is_deposit = rng.random(n) < deposit_p
    dep_idx = np.flatnonzero(is_deposit)
    tx_frames: list[pd.DataFrame] = []
    bonus_frames: list[pd.DataFrame] = []
    uid_all = users["user_id"].to_numpy()

    if len(dep_idx):
        mu = np.array([DEPOSIT_MU[v] for v in vip[dep_idx]])
        amount = np.round(np.exp(rng.normal(mu, 0.42)), 2)
        amount = np.clip(amount, 10, 250000)
        dep = pd.DataFrame(
            {
                "user_id": uid_all[user_idx[dep_idx]],
                "transaction_date": _datestr(date_ord[dep_idx]),
                "transaction_type": "deposit",
                "amount": amount,
                "_ord": date_ord[dep_idx],
                "_vip": vip[dep_idx],
                "_arch": archetype[dep_idx],
            }
        )
        tx_frames.append(dep.drop(columns=["_vip", "_arch"]))
        # Reload bonus on a subset of deposits.
        reload = rng.random(len(dep_idx)) < np.where(dep["_arch"].to_numpy() == "promo_sensitive", 0.55, 0.18)
        if reload.any():
            bonus_amount = np.round(dep.loc[reload, "amount"].to_numpy() * rng.uniform(0.05, 0.25, size=int(reload.sum())), 2)
            used = (rng.random(int(reload.sum())) < 0.72).astype(np.int64)
            bonus_frames.append(
                pd.DataFrame(
                    {
                        "user_id": dep.loc[reload, "user_id"].to_numpy(),
                        "bonus_date": dep.loc[reload, "transaction_date"].to_numpy(),
                        "bonus_type": "Reload",
                        "bonus_amount": bonus_amount,
                        "bonus_used_flag": used,
                    }
                )
            )
            # Mirror the grant in the wallet ledger. Features read bonuses from bonuses.csv
            # and cashback from transactions, so this row is context rather than a second count.
            tx_frames.append(
                pd.DataFrame(
                    {
                        "user_id": dep.loc[reload, "user_id"].to_numpy(),
                        "transaction_date": dep.loc[reload, "transaction_date"].to_numpy(),
                        "transaction_type": "bonus",
                        "amount": bonus_amount,
                        "_ord": dep.loc[reload, "_ord"].to_numpy(),
                    }
                )
            )
        cashback = rng.random(len(dep_idx)) < 0.10
        if cashback.any():
            cb_amount = np.round(dep.loc[cashback, "amount"].to_numpy() * rng.uniform(0.03, 0.12, size=int(cashback.sum())), 2)
            cb_ord = dep.loc[cashback, "_ord"].to_numpy()
            tx_frames.append(
                pd.DataFrame(
                    {
                        "user_id": dep.loc[cashback, "user_id"].to_numpy(),
                        "transaction_date": _datestr(cb_ord),
                        "transaction_type": "cashback",
                        "amount": cb_amount,
                        "_ord": cb_ord,
                    }
                )
            )

    withdraw_p = np.full(n, 0.035)
    near_exit = np.isin(mode, ("gradual_exit", "shock_exit")) & (days_before >= 0) & (days_before <= 7)
    withdraw_p = np.where(near_exit, 0.16, withdraw_p)
    withdraw_p = np.where(np.isin(vip, ("Gold", "Platinum", "Diamond")), withdraw_p * 1.25, withdraw_p)
    is_wd = rng.random(n) < withdraw_p
    if is_wd.any():
        wd_amount = np.round(np.maximum(entry_fee[is_wd] * games_proxy(rng, int(is_wd.sum())), 20) * rng.uniform(0.8, 4.5, size=int(is_wd.sum())), 2)
        tx_frames.append(
            pd.DataFrame(
                {
                    "user_id": uid_all[user_idx[is_wd]],
                    "transaction_date": _datestr(date_ord[is_wd]),
                    "transaction_type": "withdrawal",
                    "amount": wd_amount,
                    "_ord": date_ord[is_wd],
                }
            )
        )

    # Welcome bonus once, on the registration date when it falls inside the extract.
    welcome_reg = users["reg_ord"].to_numpy()
    welcome_ok = (welcome_reg >= _epoch(date(2024, 6, 1))) & (rng.random(len(users)) < 0.72)
    if welcome_ok.any():
        w_users = users.loc[welcome_ok]
        w_vip = w_users["vip_segment"].to_numpy()
        base = np.array([{"Regular": 50, "Bronze": 75, "Silver": 100, "Gold": 200, "Platinum": 400, "Diamond": 1000}[v] for v in w_vip], dtype=float)
        base = np.round(base * rng.uniform(0.8, 1.2, size=len(w_users)), 2)
        used_p = np.where(w_users["cohort"].to_numpy() == "loyal", 0.8, 0.55)
        bonus_frames.append(
            pd.DataFrame(
                {
                    "user_id": w_users["user_id"].to_numpy(),
                    "bonus_date": w_users["registration_date"].to_numpy(),
                    "bonus_type": "Welcome",
                    "bonus_amount": base,
                    "bonus_used_flag": (rng.random(len(w_users)) < used_p).astype(np.int64),
                }
            )
        )

    # Occasional free-game grants for promo-sensitive players.
    promo_rows = np.flatnonzero((archetype == "promo_sensitive") & (rng.random(n) < 0.08))
    if len(promo_rows):
        bonus_frames.append(
            pd.DataFrame(
                {
                    "user_id": uid_all[user_idx[promo_rows]],
                    "bonus_date": _datestr(date_ord[promo_rows]),
                    "bonus_type": rng.choice(np.array(["Free Game", "Leaderboard", "Cashback Ticket"]), size=len(promo_rows)),
                    "bonus_amount": np.round(rng.uniform(10, 80, size=len(promo_rows)), 2),
                    "bonus_used_flag": (rng.random(len(promo_rows)) < 0.64).astype(np.int64),
                }
            )
        )

    if tx_frames:
        transactions = pd.concat(tx_frames, ignore_index=True)
        transactions.insert(
            0,
            "transaction_id",
            np.arange(id_state["transaction_id"], id_state["transaction_id"] + len(transactions)),
        )
        id_state["transaction_id"] += len(transactions)
        transactions = transactions[["transaction_id", "user_id", "transaction_date", "transaction_type", "amount"]]
    else:
        transactions = pd.DataFrame(columns=["transaction_id", "user_id", "transaction_date", "transaction_type", "amount"])

    if bonus_frames:
        bonuses = pd.concat(bonus_frames, ignore_index=True)
        bonuses.insert(0, "bonus_id", np.arange(id_state["bonus_id"], id_state["bonus_id"] + len(bonuses)))
        id_state["bonus_id"] += len(bonuses)
        bonuses = bonuses[["bonus_id", "user_id", "bonus_date", "bonus_type", "bonus_amount", "bonus_used_flag"]]
    else:
        bonuses = pd.DataFrame(columns=["bonus_id", "user_id", "bonus_date", "bonus_type", "bonus_amount", "bonus_used_flag"])
    return transactions, bonuses


def games_proxy(rng: np.random.Generator, n: int) -> np.ndarray:
    return rng.uniform(30, 400, size=n)


def _historical_events(
    users: pd.DataFrame,
    rng: np.random.Generator,
    cfg: ProjectConfig,
    id_state: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Sparse pre-detail events so lifetime totals are not just the last quarter."""
    recent_start = _epoch(cfg.detail_start)
    reg = users["reg_ord"].to_numpy()
    play_end = users["play_end_ord"].to_numpy()
    hist_last = np.minimum(play_end + 1, recent_start)
    span = (hist_last - reg).clip(min=0).astype(np.int64)
    hist_p = np.clip(users["daily_p"].to_numpy() * 0.75, 0.01, 0.4)
    # Binomial with per-row n. Skip rows with a huge span product by capping draws.
    n_hist = np.zeros(len(users), dtype=np.int64)
    positive = span > 0
    if positive.any():
        n_hist[positive] = rng.binomial(span[positive], hist_p[positive])
    # Cap so one veteran cannot explode the extract.
    n_hist = np.minimum(n_hist, 40)
    total = int(n_hist.sum())
    empty_g = pd.DataFrame(columns=["game_id", "user_id", "game_date", "game_type", "game_variant", "entry_fee", "game_result", "games_played", "duration_minutes", "rake", "tournament_flag"])
    empty_s = pd.DataFrame(columns=["session_id", "user_id", "session_date", "session_duration", "login_count", "app_version", "device_type"])
    empty_t = pd.DataFrame(columns=["transaction_id", "user_id", "transaction_date", "transaction_type", "amount"])
    empty_b = pd.DataFrame(columns=["bonus_id", "user_id", "bonus_date", "bonus_type", "bonus_amount", "bonus_used_flag"])
    if total == 0:
        return empty_g, empty_t, empty_b, empty_s

    idx = np.repeat(np.arange(len(users)), n_hist)
    span_exp = np.repeat(span, n_hist)
    reg_exp = np.repeat(reg, n_hist)
    offsets = rng.integers(np.zeros(total, dtype=np.int64), np.maximum(span_exp, 1))
    # integers high is exclusive; span_exp is the exclusive end offset.
    date_ord = reg_exp + np.minimum(offsets, np.maximum(span_exp - 1, 0))
    uid = users["user_id"].to_numpy()[idx]
    vip = users["vip_segment"].to_numpy()[idx]
    arch = users["archetype"].to_numpy()[idx]
    device = users["device_type"].to_numpy()[idx]
    prefs = users[[f"pref_{i}" for i in range(4)]].to_numpy(dtype=float)[idx]
    favs = users[[f"fav_{i}" for i in range(4)]].to_numpy()[idx]
    lam = users["games_lambda"].to_numpy()[idx]

    u = rng.random(total)
    cdf = np.cumsum(prefs, axis=1)
    cdf[:, -1] = 1.0
    type_idx = np.argmax(u[:, None] <= cdf, axis=1)
    game_type = np.array(GAME_TYPES, dtype=object)[type_idx]
    variant = favs[np.arange(total), type_idx]
    entry_fee = np.empty(total, dtype=float)
    for level, ladder in FEE_LADDER.items():
        mask = vip == level
        if mask.any():
            entry_fee[mask] = np.array(ladder)[rng.integers(0, len(ladder), size=int(mask.sum()))]
    entry_fee = np.round(entry_fee, 2)
    low = arch == "low_value_engaged"
    entry_fee[low] = np.minimum(entry_fee[low], 25)
    games_played = np.clip(rng.poisson(lam) + 1, 1, 36).astype(np.int64)
    duration = np.round(games_played * rng.uniform(1.8, 4.0, size=total), 1)
    rake = np.round(entry_fee * games_played * rng.uniform(0.08, 0.15, size=total), 2)
    result = np.where(rng.random(total) < 0.27, "win", np.where(rng.random(total) < 0.78, "loss", "drop"))
    game_ids = np.arange(id_state["game_id"], id_state["game_id"] + total, dtype=np.int64)
    id_state["game_id"] += total
    games = pd.DataFrame(
        {
            "game_id": game_ids,
            "user_id": uid,
            "game_date": _datestr(date_ord),
            "game_type": game_type,
            "game_variant": variant,
            "entry_fee": entry_fee,
            "game_result": result,
            "games_played": games_played,
            "duration_minutes": duration,
            "rake": rake,
            "tournament_flag": (game_type == "Tournaments").astype(np.int64),
        }
    )
    session_ids = np.arange(id_state["session_id"], id_state["session_id"] + total, dtype=np.int64)
    id_state["session_id"] += total
    sessions = pd.DataFrame(
        {
            "session_id": session_ids,
            "user_id": uid,
            "session_date": games["game_date"].to_numpy(),
            "session_duration": np.round(duration + rng.uniform(2, 8, size=total), 1),
            "login_count": 1 + rng.poisson(0.3, size=total),
            "app_version": _app_versions(date_ord, rng),
            "device_type": device,
        }
    )
    dep_mask = rng.random(total) < 0.18
    if dep_mask.any():
        mu = np.array([DEPOSIT_MU[v] for v in vip[dep_mask]])
        amount = np.round(np.clip(np.exp(rng.normal(mu, 0.4)), 10, 250000), 2)
        tx = pd.DataFrame(
            {
                "transaction_id": np.arange(id_state["transaction_id"], id_state["transaction_id"] + int(dep_mask.sum())),
                "user_id": uid[dep_mask],
                "transaction_date": _datestr(date_ord[dep_mask]),
                "transaction_type": "deposit",
                "amount": amount,
            }
        )
        id_state["transaction_id"] += int(dep_mask.sum())
    else:
        tx = empty_t
    return games, tx, empty_b, sessions


def _append_csv(df: pd.DataFrame, path: Path, header: bool) -> None:
    if df.empty:
        if header and not path.exists():
            df.to_csv(path, index=False)
        return
    df.to_csv(path, mode="a", header=header, index=False)


def generate_raw_data(cfg: ProjectConfig, n_users: int | None = None) -> dict[str, int]:
    """Generate raw CSVs under ``data/raw`` and a small latent debug file.

    The debug file is gitignored. It is not an input to feature engineering.
    """
    configure_logging()
    cfg.ensure_directories()
    n_users = int(n_users or cfg.n_users)
    if n_users < 1000:
        raise ValueError("n_users must be at least 1,000")
    rng = np.random.default_rng(cfg.seed)
    raw = cfg.path("raw_dir")
    for name in ("users.csv", "games.csv", "transactions.csv", "sessions.csv", "bonuses.csv", "_debug_users.csv"):
        target = raw / name
        if target.exists():
            target.unlink()

    logger.info("Building %s synthetic players (seed=%s)", f"{n_users:,}", cfg.seed)
    users = build_users(cfg, n_users, rng)
    public_cols = [
        "user_id",
        "registration_date",
        "age",
        "gender",
        "city",
        "state",
        "device_type",
        "acquisition_channel",
        "acquisition_campaign",
        "registration_platform",
        "vip_segment",
    ]
    users[public_cols].to_csv(raw / "users.csv", index=False)
    users[["user_id", "archetype", "cohort", "mode", "daily_p", "play_end_ord"]].to_csv(raw / "_debug_users.csv", index=False)

    id_state = {"game_id": 1, "session_id": 1, "transaction_id": 1, "bonus_id": 1}
    counts = {"users": n_users, "games": 0, "sessions": 0, "transactions": 0, "bonuses": 0}
    header = {"games": True, "sessions": True, "transactions": True, "bonuses": True}
    paths = {
        "games": raw / "games.csv",
        "sessions": raw / "sessions.csv",
        "transactions": raw / "transactions.csv",
        "bonuses": raw / "bonuses.csv",
    }
    chunk = cfg.chunk_size
    for start in range(0, n_users, chunk):
        stop = min(start + chunk, n_users)
        logger.info("Simulating players %s-%s", start + 1, stop)
        games, sessions, transactions, bonuses = _simulate_chunk(users.iloc[start:stop], rng, cfg, id_state)
        frames = {"games": games, "sessions": sessions, "transactions": transactions, "bonuses": bonuses}
        for key, frame in frames.items():
            _append_csv(frame, paths[key], header[key])
            header[key] = False
            counts[key] += len(frame)
        logger.info(
            "Chunk rows | games=%s sessions=%s tx=%s bonuses=%s",
            f"{len(games):,}",
            f"{len(sessions):,}",
            f"{len(transactions):,}",
            f"{len(bonuses):,}",
        )

    manifest = {
        "n_users": n_users,
        "seed": cfg.seed,
        "counts": counts,
        "disclaimer": (
            "This project uses synthetic data inspired by common online gaming analytics "
            "use cases. It does not contain confidential or proprietary Junglee Games data."
        ),
    }
    (raw / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Raw generation complete: %s", counts)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic gaming event data")
    parser.add_argument("--n-users", type=int, default=None, help="Override config n_users")
    args = parser.parse_args()
    generate_raw_data(load_config(), n_users=args.n_users)


if __name__ == "__main__":
    main()
