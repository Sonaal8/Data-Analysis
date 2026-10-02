# Business problem

This project uses synthetic data inspired by common online gaming analytics use cases. It does not contain confidential or proprietary Junglee Games data.

## Decision this system supports

An online gaming platform wants to know, among players who are still active, who is likely to go quiet for the next 30 days. CRM, Product, and VIP retention can then spend a limited contact budget before the player has already lapsed.

The model does not choose the offer and it does not prove that an offer will work. It ranks risk. A separate rule layer routes that risk to an action. Incremental retention is measured later with an experiment.

## Who is scored

The scored book is the recently active base: players who registered before the prediction date and played at least one game in the prior 30 days. Players who are already silent are a reactivation list, not this model. Mixing them in would make the problem look easier than it is, because many of them are already gone.

## What "churn" means here

A player is churned if they have no gaming activity for 30 consecutive days after the prediction date. Wallet events alone do not count as retained. The business loss is a player who stops playing.

## Why it matters in gaming

Monthly activity is bursty. A slots or rummy player can look healthy on a Monday and be gone by the next bonus cycle. Acquisition cost is sunk, VIP hosts are scarce, and a blanket bonus to the whole active base burns margin on people who were going to play anyway. The economic question is concentration: if the desk can only speak to about 10% of active players, which 10% contains the most future silence?

## What good looks like

- A ranked list with a probability, a risk band, the main behavioral reasons, and a route (VIP, payments, engagement, low-friction return).
- An honest holdout: train on an earlier month, judge the next month.
- A lift curve the CRM lead can read without a statistics degree.
- A written experiment design before anyone claims the program "saved" players.

## What this system refuses to claim

- That a high score means an incentive will retain the player.
- That accuracy near 80% is a success. With a churn rate around one in five, accuracy is mostly the retained majority.
- That a driver is a causal lever. "Days since last game" is a risk marker. It is not, by itself, proof that a push notification works.
