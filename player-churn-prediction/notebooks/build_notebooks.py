"""Generate the analysis notebooks. Re-run if the cell source needs to change."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent
DISCLAIMER = (
    "This project uses synthetic data inspired by common online gaming analytics "
    "use cases. It does not contain confidential or proprietary Junglee Games data."
)


def _md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(source.strip() + "\n")


def _code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(source.strip() + "\n")


def _nb(cells: list[nbf.NotebookNode]) -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    }
    return nb


SETUP = """
from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.display import Markdown, display

ROOT = Path.cwd().resolve()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
import os
os.chdir(ROOT)
sns.set_theme(style="whitegrid", context="notebook")
pd.set_option("display.float_format", lambda v: f"{v:,.4f}")
print("Project root:", ROOT)
"""


def notebook_eda() -> nbf.NotebookNode:
    return _nb(
        [
            _md(
                f"""
# 01 — Exploratory analysis

{DISCLAIMER}

Population: players with at least one game in the 30 days before each prediction date.
Label: no games in the following 30 days. Charts below use the June holdout unless noted.
Every rate is computed in this notebook from `data/processed/churn_dataset.csv`.
"""
            ),
            _code(SETUP),
            _code(
                """
from src.eda_report import build_eda
insights = build_eda()
holdout = pd.read_csv(ROOT / "data/processed/churn_dataset.csv")
holdout = holdout.loc[holdout["dataset_split"] == "test"].copy()
rate = float(holdout["churned"].mean())
display(Markdown(
    f"**June holdout:** {len(holdout):,} active players, churn rate **{rate:.1%}**. "
    "That is the share who played in the prior 30 days and then recorded no game "
    "in the next 30. CRM is not trying to 'predict the 78% who stay' — it is trying "
    "to find this minority before the month is over."
))
"""
            ),
            _code(
                """
def show_table(name, column, interpretation):
    table = pd.read_csv(ROOT / "reports/aggregates" / name)
    display(table)
    top = table.sort_values("churn_rate", ascending=False).iloc[0]
    bottom = table.sort_values("churn_rate", ascending=False).iloc[-1]
    display(Markdown(
        f"**{interpretation}** Highest: `{top[column]}` at {top['churn_rate']:.1%} "
        f"({int(top['players']):,} players). Lowest: `{bottom[column]}` at {bottom['churn_rate']:.1%} "
        f"({int(bottom['players']):,} players)."
    ))
    return table

show_table("by_vip.csv", "vip_segment", "VIP is a route and a value cut, not a single-cause explanation of lapse.")
show_table("by_channel.csv", "acquisition_channel", "Channel gaps that survive are about acquisition quality. They are usually smaller than recency gaps, which is what you want before you overfit media mix.")
show_table("by_device.csv", "device_type", "Device shifts engagement slightly. It should not be the story you take to CRM.")
show_table("by_game_type.csv", "preferred_game_type", "Preferred game is the product the journey should mention. A large churn gap here means the format, not just the player, is part of the lapse.")
show_table("by_tenure.csv", "tenure_bucket", "New accounts and veterans do not lapse for the same operational reason. Tenure buckets tell you whether the book is a welcome-journey problem or a save-the-regular problem.")
"""
            ),
            _code(
                """
show_table("by_games.csv", "games_bucket", "Players with very few games in the feature window are closer to an empty next month. High-volume players still churn — those are the shock cases a recency-only rule misses.")
show_table("by_deposit.csv", "deposit_bucket", "Funding and play move together, imperfectly. A funded player can still leave, and an unfunded grinder can stay.")
show_table("by_withdrawal.csv", "withdrawal_bucket", "Withdrawal amount is not a clean 'about to leave' flag on its own. Combined with high risk it becomes the win-back route, because some cash-outs are healthy.")
show_table("by_recency.csv", "recency_bucket", "Days since last game is the cleanest single cut in this book. The gradient from 'played yesterday' to 'played two weeks ago' is the practical version of the churn definition.")
show_table("by_sessions.csv", "session_bucket", "Session frequency tracks the habit. A player who still opens the app is a different save from one who has stopped logging in.")
show_table("by_activity_decline.csv", "activity_decline_flag", "The decline flag is a CRM key, not the whole model. Flagged players churn more; unflagged players still contain shock exits.")
show_table("by_value.csv", "value_bucket", "Lifetime rake quartiles show whether value and risk move together. High value is not automatically low risk — that is the VIP-at-risk book.")
"""
            ),
            _code(
                """
from IPython.display import Image
for figure, note in [
    ("recency_boxplot.png", "The churned group sits further from the last game. Overlap remains, so a hard recency rule still misses recent players who stop suddenly."),
    ("games_distribution_by_churn.png", "Churned players are shifted toward fewer games, with a long right tail. Volume alone will not separate the classes."),
    ("correlation_heatmap.png", "Correlations with churn are real and moderate. No single column is the label in disguise."),
    ("cohort_churn_heatmap.png", "Registration cohort by snapshot is the acquisition view of the same definition. Read down a cohort to see whether a class got riskier as it aged, and across a snapshot to see the month."),
]:
    display(Image(filename=str(ROOT / "reports/figures" / figure)))
    display(Markdown(note))

corr = pd.read_csv(ROOT / "reports/aggregates/correlation_matrix.csv", index_col=0)
display(corr["churned"].sort_values().to_frame("correlation_with_churn"))
display(Markdown(
    f"Recency correlation with churn is {insights['corr_days_since_last_game']:.2f}. "
    f"Games in 30 days: {insights['corr_games_30d']:.2f}. "
    f"Week-on-week games change: {insights['corr_games_change']:.2f}. "
    "Negative volume and negative week-on-week change both point at higher churn, which matches the operating story."
))
"""
            ),
        ]
    )


def notebook_baseline() -> nbf.NotebookNode:
    return _nb(
        [
            _md(
                f"""
# 02 — Logistic regression baseline

{DISCLAIMER}

A linear model is the baseline a stakeholder can audit. It is trained on the April snapshot and scored on June, with the decision threshold chosen on May. Preprocessing is median imputation, standardization, and one-hot encoding, fit inside the pipeline so the holdout does not set the medians.
"""
            ),
            _code(SETUP),
            _code(
                """
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from src.preprocessing import make_one_hot_preprocessor, model_feature_frame
from src.evaluation import classification_metrics, tune_threshold

frame = pd.read_csv(ROOT / "data/processed/churn_dataset.csv")
splits = {}
for name in ("train", "valid", "test"):
    part = frame.loc[frame["dataset_split"] == name].reset_index(drop=True)
    splits[name] = (model_feature_frame(part), part["churned"].to_numpy().astype(int))

pipe = Pipeline([
    ("pre", make_one_hot_preprocessor(scale_numeric=True)),
    ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=500, solver="lbfgs")),
])
pipe.fit(splits["train"][0], splits["train"][1])
p_valid = pipe.predict_proba(splits["valid"][0])[:, 1]
p_test = pipe.predict_proba(splits["test"][0])[:, 1]
chosen = tune_threshold(splits["valid"][1], p_valid, beta=1.5)
metrics = classification_metrics(splits["test"][1], p_test, chosen["threshold"])
at_half = classification_metrics(splits["test"][1], p_test, 0.5)
display(pd.DataFrame([
    {"operating_point": "May-tuned F1.5", **{k: metrics[k] for k in ("threshold","accuracy","precision","recall","f1","roc_auc","pr_auc")}},
    {"operating_point": "0.50", **{k: at_half[k] for k in ("threshold","accuracy","precision","recall","f1","roc_auc","pr_auc")}},
]))
base = float(splits["test"][1].mean())
display(Markdown(
    f"June base rate is **{base:.1%}**. Accuracy at the tuned threshold is **{metrics['accuracy']:.1%}**. "
    f"A classifier that calls every player retained scores about **{1-base:.1%}** accuracy and **zero** recall. "
    f"This baseline's recall is **{metrics['recall']:.1%}** and PR-AUC is **{metrics['pr_auc']:.3f}** "
    f"against a base-rate PR-AUC of {base:.3f}. "
    "Recall matters because a missed churner is a player the desk never called. "
    "PR-AUC matters because it judges the ranking across thresholds when the positive class is the minority. "
    "Accuracy mostly restates the base rate."
))
cm = metrics["confusion_matrix"]
display(Markdown(
    f"Confusion matrix at the tuned threshold — true negatives {cm['tn']:,}, "
    f"false positives {cm['fp']:,} (contacted a player who stayed), "
    f"false negatives {cm['fn']:,} (missed a churner), true positives {cm['tp']:,}."
))
"""
            ),
        ]
    )


def notebook_comparison() -> nbf.NotebookNode:
    return _nb(
        [
            _md(
                f"""
# 03 — Model comparison

{DISCLAIMER}

The full search ran in `src/train.py` (stratified cross-validation on an April subsample, refit on all April rows, threshold tuned on May, metrics on June). This notebook recomputes the holdout metrics from the saved probabilities so the table is not a pasted number.
"""
            ),
            _code(SETUP),
            _code(
                """
from src.evaluation import classification_metrics

metrics = json.loads((ROOT / "reports/model_metrics/metrics.json").read_text())
preds = pd.read_csv(ROOT / "reports/model_metrics/test_predictions.csv")
rows = []
for record in metrics["comparison"]:
    name = record["model"]
    recomputed = classification_metrics(preds["y_true"].to_numpy(), preds[f"p_{name}"].to_numpy(), record["threshold"])
    rows.append({
        "Model": name,
        "Accuracy": recomputed["accuracy"],
        "Precision": recomputed["precision"],
        "Recall": recomputed["recall"],
        "F1": recomputed["f1"],
        "ROC-AUC": recomputed["roc_auc"],
        "PR-AUC": recomputed["pr_auc"],
        "Threshold": record["threshold"],
        "May PR-AUC": record["validation_pr_auc"],
    })
table = pd.DataFrame(rows).sort_values("PR-AUC", ascending=False)
display(table)
display(Markdown(
    f"Champion **{metrics['champion']}** was selected on May PR-AUC, not on June accuracy. "
    "Selecting on the test month would leak the holdout into the choice."
))
"""
            ),
            _code(
                """
base = float(preds["y_true"].mean())
display(Markdown(
    f"June base rate {base:.1%}. Calling everyone retained would post accuracy {1-base:.1%} "
    "and catch no churners. The comparison table's accuracy column is therefore a poor referee."
))
champ = metrics["champion_test"]["confusion_matrix"]
display(Markdown(
    f"On the champion, a **false positive** is one of the {champ['fp']:,} players flagged who still played "
    f"in the next 30 days — a contact, and possibly an incentive, spent on someone who was staying. "
    f"A **false negative** is one of the {champ['fn']:,} churners the threshold did not flag. "
    "The desk's cost ratio decides which error is more expensive. Beta 1.5 on the May threshold "
    "leans toward catching churners, and it is a policy choice, not a law."
))
display(Image := __import__("IPython").display.Image(filename=str(ROOT / "reports/figures/model_comparison.png")))
display(__import__("IPython").display.Image(filename=str(ROOT / "reports/figures/roc_curves.png")))
display(__import__("IPython").display.Image(filename=str(ROOT / "reports/figures/pr_curves.png")))
display(__import__("IPython").display.Image(filename=str(ROOT / "reports/figures/confusion_matrix.png")))
"""
            ),
        ]
    )


def notebook_temporal() -> nbf.NotebookNode:
    return _nb(
        [
            _md(
                f"""
# 04 — Temporal validation

{DISCLAIMER}

A random split of one month answers: "If tomorrow looks like today, how well do we rank?"
A temporal split answers the question operations actually has: "If we train through this month, what happens next month?"
Player behavior, promotions, and mix shift. A random split also lets near-duplicate rows of the same regime sit on both sides of the cut.
"""
            ),
            _code(SETUP),
            _code(
                """
metrics = json.loads((ROOT / "reports/model_metrics/metrics.json").read_text())
temporal = metrics["random_split"]["temporal_test_metrics"]
random_split = metrics["random_split"]["metrics"]
compare = pd.DataFrame([
    {"split": "Temporal: train April, test June", **{k: temporal[k] for k in ("accuracy","precision","recall","f1","roc_auc","pr_auc")}},
    {"split": "Random: 70/30 inside June", **{k: random_split[k] for k in ("accuracy","precision","recall","f1","roc_auc","pr_auc")}},
])
display(compare)
gap = random_split["pr_auc"] - temporal["pr_auc"]
display(Markdown(
    f"In-time PR-AUC is {random_split['pr_auc']:.3f}. "
    f"The April-to-June PR-AUC is {temporal['pr_auc']:.3f} "
    f"(difference {gap:+.3f}). "
    "The random split is the optimistic number. The temporal number is the one to put on a model card, "
    "because the desk will always score a later week than the one the model was fit on. "
    "Hyperparameters were chosen on April cross-validation and the threshold on May; "
    "the random-split row uses those same hyperparameters refit inside June, so the gap is about the split, not a second search on the holdout."
))
"""
            ),
        ]
    )


def notebook_explain() -> nbf.NotebookNode:
    return _nb(
        [
            _md(
                f"""
# 05 — Explainability

{DISCLAIMER}

Global bars are mean absolute contributions from the champion. A positive local contribution pushed that player's score toward churn. Contributions explain the score. They are not an estimate of what happens if a product manager changes the feature.
"""
            ),
            _code(SETUP),
            _code(
                """
summary = json.loads((ROOT / "reports/model_metrics/explain_summary.json").read_text())
importance = pd.read_csv(ROOT / "reports/model_metrics/shap_importance.csv")
permutation = pd.read_csv(ROOT / "reports/model_metrics/permutation_importance.csv")
display(Markdown(f"**Method.** {summary['method']}"))
display(Markdown("### Mean absolute contribution"))
display(importance.head(12))
display(Markdown("### Permutation importance (drop in holdout PR-AUC)"))
display(permutation.head(12))
from IPython.display import Image
display(Image(filename=str(ROOT / "reports/figures/shap_importance.png")))
display(Image(filename=str(ROOT / "reports/figures/permutation_importance.png")))
display(Image(filename=str(ROOT / "reports/figures/shap_dependence_top_feature.png")))
top = importance.iloc[0]
display(Markdown(
    f"The strongest average contributor is **{top['label']}** "
    f"(mean absolute contribution {top['mean_abs_shap']:.4f}). "
    "Read the dependence chart as 'how this feature moves the score in this model,' "
    "not as 'shortening recency by a day will save this many players.'"
))
"""
            ),
            _code(
                """
scores = pd.read_csv(ROOT / "reports/scores/player_risk_scores.csv")
examples = scores.nlargest(3, "churn_probability")[
    ["user_id", "churn_probability", "risk_band", "segment",
     "top_risk_driver_1", "top_risk_driver_2", "top_risk_driver_3",
     "days_since_last_game", "games_30d", "games_change_7d_vs_previous_7d",
     "active_days_30d", "deposit_amount_30d", "recommended_action"]
]
display(Markdown("### Three highest-scoring synthetic players"))
display(examples)
low = scores.nsmallest(1, "churn_probability")[
    ["user_id", "churn_probability", "risk_band", "days_since_last_game", "games_30d", "recommended_action"]
]
display(Markdown("### A low-score contrast"))
display(low)
display(Markdown(
    "Drivers are blank when the contribution did not increase risk. "
    "Do not fill that gap with a story the model did not support."
))
"""
            ),
        ]
    )


def notebook_lift() -> nbf.NotebookNode:
    return _nb(
        [
            _md(
                f"""
# 06 — Lift and gains

{DISCLAIMER}

The retention desk cannot call the whole active base. Decile 1 is the 10% of June players with the highest predicted probability. Capture and lift are computed here from the saved champion probabilities.
"""
            ),
            _code(SETUP),
            _code(
                """
from src.evaluation import capture_at_fractions, decile_lift

preds = pd.read_csv(ROOT / "reports/model_metrics/test_predictions.csv")
y = preds["y_true"].to_numpy()
p = preds["p_champion"].to_numpy()
lift = decile_lift(y, p)
capture = capture_at_fractions(y, p, [0.05, 0.10, 0.20])
display(lift)
display(capture)
base = float(y.mean())
top = lift.iloc[0]
at10 = capture.loc[capture["contact_fraction"] == 0.10].iloc[0]
display(Markdown(
    f"Base churn is **{base:.1%}**. The top decile churns at **{top['churn_rate']:.1%}** "
    f"(lift **{top['lift']:.2f}x**) and holds **{top['cumulative_churn_capture']:.1%}** of all churners. "
    f"Contacting the top 10% captures **{at10['recall_at_k']:.1%}** of churners "
    f"at **{at10['precision_at_k']:.1%}** precision, lift **{at10['lift']:.2f}x**. "
    f"An accuracy of {(1-base):.0%} from ignoring the problem catches **none** of them. "
    "That is why the operating conversation is lift at a contact cap, not a single accuracy number."
))
"""
            ),
            _code(
                """
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(lift["decile"].astype(str), lift["lift"], color="#1f4e79")
ax.axhline(1.0, color="grey", linestyle="--")
ax.set_title("Lift by predicted-risk decile")
ax.set_xlabel("Decile (1 = highest risk)")
ax.set_ylabel("Lift versus base churn rate")
fig.tight_layout()
fig.savefig(ROOT / "reports/figures/lift_by_decile_notebook.png", dpi=140)
plt.show()

fig, ax = plt.subplots(figsize=(6, 5))
share = np.arange(1, 11) / 10
ax.plot(share, lift["cumulative_churn_capture"], marker="o", label="Model")
ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="Random contact")
ax.set_title("Cumulative gains")
ax.set_xlabel("Share of active players contacted")
ax.set_ylabel("Share of churners captured")
ax.legend()
fig.tight_layout()
fig.savefig(ROOT / "reports/figures/cumulative_gains_notebook.png", dpi=140)
plt.show()
"""
            ),
        ]
    )


def main() -> None:
    notebooks = {
        "01_eda.ipynb": notebook_eda(),
        "02_model_baseline.ipynb": notebook_baseline(),
        "03_model_comparison.ipynb": notebook_comparison(),
        "04_temporal_validation.ipynb": notebook_temporal(),
        "05_model_explainability.ipynb": notebook_explain(),
        "06_lift_gains_analysis.ipynb": notebook_lift(),
    }
    for name, nb in notebooks.items():
        path = ROOT / name
        nbf.write(nb, path)
        print("wrote", path)


if __name__ == "__main__":
    main()
