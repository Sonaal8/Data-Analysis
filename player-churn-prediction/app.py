"""Retention intelligence dashboard.

Reads saved scores, aggregates, and metrics. It does not retrain on startup.

This project uses synthetic data inspired by common online gaming analytics
use cases. It does not contain confidential or proprietary Junglee Games data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
DISCLAIMER = (
    "This project uses synthetic data inspired by common online gaming analytics "
    "use cases. It does not contain confidential or proprietary Junglee Games data."
)


def _read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_scores() -> pd.DataFrame | None:
    frame = _read_csv(ROOT / "reports" / "scores" / "player_risk_scores.csv")
    if frame is None:
        return None
    frame["user_id"] = frame["user_id"].astype(str)
    return frame


@st.cache_data(show_spinner=False)
def load_metrics() -> dict | None:
    return _read_json(ROOT / "reports" / "model_metrics" / "metrics.json")


def _missing() -> None:
    st.error(
        "Saved scoring artifacts are not in this folder yet. From the project root run "
        "`python -m src.pipeline` (or the individual train / explain / score modules) "
        "and reopen the app."
    )


def page_overview(scores: pd.DataFrame) -> None:
    st.header("Executive overview")
    st.caption("Scored book: players active in the 30 days before 2025-06-15. Holdout outcomes are shown only because this is a backtest.")
    players = len(scores)
    holdout = float(scores["churned_holdout"].mean()) if "churned_holdout" in scores.columns else float("nan")
    high = int(scores["risk_band"].isin(["HIGH", "CRITICAL"]).sum())
    critical = int((scores["risk_band"] == "CRITICAL").sum())
    avg_p = float(scores["churn_probability"].mean())
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Active players", f"{players:,}")
    c2.metric("Holdout churn rate", f"{holdout:.1%}")
    c3.metric("High risk", f"{high:,}")
    c4.metric("Critical risk", f"{critical:,}")
    c5.metric("Average churn probability", f"{avg_p:.1%}")
    st.caption(
        "High risk counts HIGH and CRITICAL. The holdout churn rate is observed silence "
        "in the 30 days after the scoring date. Average probability is the model's "
        "unconditional score, not a promise that those players can be saved."
    )

    band_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    band = scores["risk_band"].value_counts().reindex(band_order).fillna(0).rename_axis("band").reset_index(name="players")
    fig = px.bar(band, x="band", y="players", title="Players by risk band", text_auto=True)
    fig.update_layout(xaxis_title="Risk band", yaxis_title="Players", showlegend=False)
    st.plotly_chart(fig, width="stretch")

    hist = px.histogram(
        scores,
        x="churn_probability",
        nbins=40,
        title="Distribution of predicted churn probability",
    )
    hist.update_layout(xaxis_title="Predicted probability of no game in the next 30 days", yaxis_title="Players")
    st.plotly_chart(hist, width="stretch")


def _rate_chart(path: Path, column: str, title: str) -> None:
    table = _read_csv(path)
    if table is None or table.empty:
        st.info(f"Missing aggregate {path.name}. Run `python -m src.eda_report`.")
        return
    fig = px.bar(table, x=column, y="churn_rate", hover_data=["players"], title=title)
    fig.update_layout(xaxis_title="", yaxis_title="Holdout churn rate", yaxis_tickformat=".0%")
    st.plotly_chart(fig, width="stretch")


def page_analytics() -> None:
    st.header("Churn analytics")
    st.caption("June holdout. Rates are observed outcomes among players who were active in the prior 30 days.")
    aggregates = ROOT / "reports" / "aggregates"
    _rate_chart(aggregates / "by_vip.csv", "vip_segment", "Churn rate by VIP segment")
    _rate_chart(aggregates / "by_channel.csv", "acquisition_channel", "Churn rate by acquisition channel")
    _rate_chart(aggregates / "by_game_type.csv", "preferred_game_type", "Churn rate by preferred game type")
    _rate_chart(aggregates / "by_tenure.csv", "tenure_bucket", "Churn rate by tenure")
    _rate_chart(aggregates / "by_games.csv", "games_bucket", "Churn rate by games in the last 30 days")
    _rate_chart(aggregates / "by_recency.csv", "recency_bucket", "Churn rate by days since last game")


def page_player(scores: pd.DataFrame) -> None:
    st.header("Player risk")
    st.caption("Search a synthetic user id. Drivers are the features pushing this player's score up, not a causal story.")
    query = st.text_input("user_id", value=str(scores.iloc[0]["user_id"]))
    match = scores.loc[scores["user_id"] == query.strip()]
    if match.empty:
        st.warning("No scored player with that id on the 2025-06-15 book.")
        return
    row = match.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Churn probability", f"{row['churn_probability']:.1%}")
    c2.metric("Risk band", str(row["risk_band"]))
    c3.metric("Segment", str(row["segment"]))
    c4.metric("VIP", str(row["vip_segment"]))
    st.subheader("Recommended action")
    st.info(str(row["recommended_action"]))
    st.caption("The action is a routing rule. It is not an estimated lift from sending the message.")

    left, right = st.columns(2)
    with left:
        st.subheader("Engagement")
        st.write(
            {
                "Games, 30 days": int(row["games_30d"]),
                "Active days, 30 days": int(row["active_days_30d"]),
                "Sessions, 30 days": int(row["sessions_30d"]),
                "Days since last game": int(row["days_since_last_game"]),
                "Week-on-week games change": round(float(row["games_change_7d_vs_previous_7d"]), 2),
                "Activity decline flag": int(row["activity_decline_flag"]),
                "Preferred game": row["preferred_game_type"],
                "Tenure (days)": int(row["player_tenure_days"]),
            }
        )
    with right:
        st.subheader("Monetary")
        st.write(
            {
                "Deposits, 30 days": round(float(row["deposit_amount_30d"]), 2),
                "Withdrawals, 30 days": round(float(row["withdrawal_amount_30d"]), 2),
                "Rake, 30 days": round(float(row["rake_30d"]), 2),
                "Lifetime rake": round(float(row["lifetime_rake"]), 2),
                "Lifetime deposits": round(float(row["lifetime_deposit"]), 2),
                "Deposit decline flag": int(row["deposit_decline_flag"]),
                "Bonus dependency": round(float(row["bonus_dependency_ratio"]), 2),
            }
        )
    st.subheader("Top risk drivers")
    for label in (row["top_risk_driver_1"], row["top_risk_driver_2"], row["top_risk_driver_3"]):
        if isinstance(label, str) and label:
            st.write(f"- {label}")


def _slice_table(scores: pd.DataFrame, fraction: float) -> pd.DataFrame:
    k = max(1, int(round(len(scores) * fraction)))
    top = scores.nlargest(k, "churn_probability")
    captured = int(top["churned_holdout"].sum()) if "churned_holdout" in top.columns else None
    total = int(scores["churned_holdout"].sum()) if "churned_holdout" in scores.columns else None
    base = (total / len(scores)) if total is not None else None
    rate = (captured / k) if captured is not None else None
    return pd.DataFrame(
        [
            {
                "contact_share": f"{fraction:.0%}",
                "players_contacted": k,
                "holdout_churners_captured": captured,
                "recall": None if not total else captured / total,
                "precision": rate,
                "lift": None if not base else rate / base,
            }
        ]
    )


def page_targeting(scores: pd.DataFrame) -> None:
    st.header("Retention targeting")
    st.caption("If the desk can only contact a slice of the active base, these are the players at the top of the score.")
    rows = pd.concat([_slice_table(scores, f) for f in (0.05, 0.10, 0.20)], ignore_index=True)
    show = rows.copy()
    for col in ("recall", "precision"):
        show[col] = show[col].map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
    show["lift"] = show["lift"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}x")
    st.dataframe(show, width="stretch", hide_index=True)
    st.caption(
        "Recall is the share of all June churners sitting inside the contacted slice. "
        "Lift is that slice's churn rate divided by the book rate. "
        "This is concentration, not the effect of the contact."
    )
    choice = st.selectbox("Show the list for", ["5%", "10%", "20%"], index=1)
    fraction = {"5%": 0.05, "10%": 0.10, "20%": 0.20}[choice]
    k = max(1, int(round(len(scores) * fraction)))
    st.dataframe(
        scores.nlargest(k, "churn_probability")[
            [
                "user_id",
                "churn_probability",
                "risk_band",
                "segment",
                "vip_segment",
                "recommended_action",
                "days_since_last_game",
                "games_30d",
            ]
        ].head(50),
        width="stretch",
        hide_index=True,
    )
    st.caption("First 50 rows of the slice, highest probability first.")


def page_performance(metrics: dict | None) -> None:
    st.header("Model performance")
    st.caption("June holdout. The model and the threshold were frozen using April and May.")
    if not metrics:
        st.info("Missing reports/model_metrics/metrics.json.")
        return
    test = metrics["champion_test"]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("ROC-AUC", f"{test['roc_auc']:.3f}")
    c2.metric("PR-AUC", f"{test['pr_auc']:.3f}")
    c3.metric("Precision", f"{test['precision']:.3f}")
    c4.metric("Recall", f"{test['recall']:.3f}")
    c5.metric("F1", f"{test['f1']:.3f}")
    c6.metric("Accuracy", f"{test['accuracy']:.3f}")
    st.caption(
        f"Champion: {metrics['champion']}. Operating threshold {test['threshold']:.2f}, "
        "chosen on May to maximize F-beta (beta 1.5). Accuracy is shown and was not the selection rule."
    )
    comparison = pd.DataFrame(metrics["comparison"])
    st.subheader("Model comparison at each model's own validation threshold")
    st.dataframe(
        comparison[["model", "accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "threshold"]],
        width="stretch",
        hide_index=True,
    )
    st.caption("False positives spend a contact on someone who would have stayed. False negatives are silent churners the desk never called. Recall and PR-AUC describe that tradeoff. Accuracy does not.")

    curves = metrics.get("curves", {}).get(metrics["champion"])
    if curves:
        roc = go.Figure()
        roc.add_trace(go.Scatter(x=curves["fpr"], y=curves["tpr"], name=metrics["champion"]))
        roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Chance", line=dict(dash="dash")))
        roc.update_layout(title="ROC — June holdout", xaxis_title="False positive rate", yaxis_title="True positive rate")
        st.plotly_chart(roc, width="stretch")
        pr = go.Figure()
        pr.add_trace(go.Scatter(x=curves["recall"], y=curves["precision"], name=metrics["champion"]))
        pr.update_layout(title="Precision-recall — June holdout", xaxis_title="Recall", yaxis_title="Precision")
        st.plotly_chart(pr, width="stretch")

    cm = test["confusion_matrix"]
    matrix = pd.DataFrame(
        [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]],
        index=["Actually retained", "Actually churned"],
        columns=["Predicted retained", "Predicted churn"],
    )
    st.subheader("Confusion matrix")
    st.dataframe(matrix, width="stretch")

    lift = pd.DataFrame(metrics["lift_deciles"])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=lift["decile"], y=lift["lift"], name="Lift"))
    fig.add_hline(y=1.0, line_dash="dash")
    fig.update_layout(title="Lift by risk decile (1 = highest risk)", xaxis_title="Decile", yaxis_title="Lift")
    st.plotly_chart(fig, width="stretch")
    gains = go.Figure()
    share = [i / 10 for i in range(1, 11)]
    gains.add_trace(go.Scatter(x=share, y=lift["cumulative_churn_capture"], mode="lines+markers", name="Model"))
    gains.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random", line=dict(dash="dash")))
    gains.update_layout(
        title="Cumulative gains",
        xaxis_title="Share of players contacted",
        yaxis_title="Share of churners captured",
    )
    st.plotly_chart(gains, width="stretch")
    st.dataframe(lift, width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Player Churn & Retention Intelligence", layout="wide")
    st.title("Player Churn & Retention Intelligence")
    st.caption(DISCLAIMER)
    scores = load_scores()
    metrics = load_metrics()
    page = st.sidebar.radio(
        "Page",
        [
            "Executive overview",
            "Churn analytics",
            "Player risk",
            "Retention targeting",
            "Model performance",
        ],
    )
    st.sidebar.markdown(DISCLAIMER)
    if page == "Churn analytics":
        page_analytics()
        return
    if page == "Model performance":
        page_performance(metrics)
        return
    if scores is None:
        _missing()
        return
    if page == "Executive overview":
        page_overview(scores)
    elif page == "Player risk":
        page_player(scores)
    else:
        page_targeting(scores)


if __name__ == "__main__":
    main()
