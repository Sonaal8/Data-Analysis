# Delta Exchange — Lead Business Analyst Interview Prep (SQL + Tableau)

**Prepared for:** Sonaal Topno  
**Role:** Lead Business Analyst — Delta Exchange (crypto derivatives: futures, options; global volume; India FIU-registered entity)  
**Last updated:** September 2026  

**Related SQL drill in Context (`docs/`):**

- [sql-interview-questions-senior-bc.md](./sql-interview-questions-senior-bc.md) — senior scenario framing, edge cases, Junglee/Sportsbet tie-ins  
- [sql-100-questions-with-answers.md](./sql-100-questions-with-answers.md) — 100 Q&A for fundamentals, windows, cohorts, A/B  
- [role-requirements-interview-prep.md](./role-requirements-interview-prep.md) — 60-second pitch pattern, STAR stories, KPI/OKR language  

**Question counts (this doc):** SQL **42** (27 full SQL + explanation; 15 framework/hints) · Tableau **36** (22 model answers; 14 frameworks) · Combined cases **5**

---

## Part A: Role & company context (brief)

### What Delta Exchange does

Delta Exchange is a **crypto derivatives** platform: **perpetual futures**, **dated futures**, and **options** on major underlyings (e.g. BTC, ETH). Traders get 24/7 markets, **margin** and **leverage**, **maker/taker** fee tiers, **funding** on perps, and tools aimed at retail and pro users (web/mobile, APIs, algo marketplace). For India-facing positioning, listings often highlight **INR margin/settlement**, local onboarding, and **FIU registration**—i.e. a regulated, high-velocity financial product surface.

**Business metrics leadership cares about:** notional **trading volume**, **active traders** (DAU/WAU/MAU with a “placed a trade” definition), **open interest (OI)**, **fee revenue** (maker vs taker mix), **funding** economics, **liquidations**, **deposit/withdrawal** flows, **KYC conversion**, **retention** of funded traders, and **product mix** (which contracts drive volume and margin).

### What a Lead BA likely owns

| Area | Typical ownership |
|------|-------------------|
| **Trading & product analytics** | Volume/OI by product; new listings; fee tier changes; API vs UI mix; options vs futures |
| **Growth & marketing** | Acquisition funnels, referral/campaign attribution, activation (signup → KYC → first trade → repeat) |
| **Retention & engagement** | Cohort retention, churn drivers, reactivation, cross-sell across products |
| **Risk-adjacent analytics** | Unusual volume/OI spikes, concentration, wash-trading *signals* (analytics flags—not legal/compliance sign-off) |
| **Experimentation** | A/B on onboarding, UI, fee promos, notifications; guardrails on revenue and risk metrics |
| **Stakeholder reporting** | Executive dashboards (Tableau), ad-hoc SQL, narrative for Product/Engineering/Marketing |

JD emphasis: **SQL**, **Tableau**, **R/Python** for stats/ML, cross-functional influence, **actionable** insights—not slide-only reporting.

### How Sonaal’s experience transfers

| Delta concept | Sonaal anchor (Flutter / Junglee / Sportsbet / Ipsos) |
|---------------|--------------------------------------------------------|
| **High-velocity consumer platform** | RMG + sports betting: real-money events, 24/7 usage, promo-heavy economics |
| **Handle / volume → revenue** | Sportsbet handle; Junglee NGR/ARPU; “volume × take rate × mix” thinking |
| **Churn → trader retention** | New-user churn −21%, existing −12%; dormant reactivation ~6% revenue |
| **A/B on money paths** | Money-movement experiments: NGR +4.2%, ARPU +2.1%, rev/deposit +12pp |
| **Fraud / abuse signals** | XGBoost fraud detection 84% accuracy—parallel to unusual trading / multi-account patterns |
| **Regulated context** | RMG + FIU-adjacent crypto narrative: KYC gates, responsible limits, audit-friendly metrics |
| **Executive storytelling** | Power BI/Tableau, campaign analytics, workshop-style KPI definition |

**Interview line:** *“I’ve spent years defining metrics executives trust on regulated, real-money platforms—then proving causality with experiments and models. Crypto derivatives is a new asset class, but the playbook—activation, retention, fee mix, and risk-aware guardrails—is the same.”*

---

## Part B: SQL interview prep (42 questions)

**Assumed schema (interview fiction—state grain aloud):**

- `users(user_id, signup_ts, country, kyc_status, kyc_approved_ts)`  
- `trades(trade_id, user_id, symbol, product_type, side, qty, price_usd, fee_usd, is_maker, trade_ts)`  
- `positions(symbol, snapshot_ts, open_interest_usd)`  
- `funding(symbol, funding_ts, funding_rate)`  
- `deposits(user_id, amount_usd, deposit_ts, status)`  
- `ab_users(user_id, experiment_id, variant, assigned_ts)`  
- `ab_outcomes(user_id, experiment_id, first_trade_ts, trades_7d)`  

**Notation:** PostgreSQL-style SQL; adapt `DATE_TRUNC` / `TIMESTAMP` to your warehouse.

---

### Category 1 — Trading & fintech metrics (8 questions)

#### B1.1 — Daily notional volume by product (CORE — full answer)

**Question:** Compute **daily notional volume** (USD) and **trade count** by `product_type` for the last 30 days.

```sql
SELECT
  DATE_TRUNC('day', trade_ts)::date AS trade_date,
  product_type,
  COUNT(*) AS trade_count,
  SUM(qty * price_usd) AS notional_volume_usd
FROM trades
WHERE trade_ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
```

**Explanation:** Notional = `qty * price` per fill; grain is **day × product**. Clarify: include only **filled** trades, UTC vs IST day boundary, and whether **options** use contract multiplier if `qty` is contracts.

---

#### B1.2 — Maker vs taker fee revenue (CORE — full answer)

**Question:** Total **fee revenue** and **% maker volume** by week.

```sql
WITH weekly AS (
  SELECT
    DATE_TRUNC('week', trade_ts) AS week_start,
    SUM(fee_usd) AS fee_revenue_usd,
    SUM(qty * price_usd) AS total_notional_usd,
    SUM(CASE WHEN is_maker THEN qty * price_usd ELSE 0 END) AS maker_notional_usd
  FROM trades
  WHERE trade_ts >= CURRENT_DATE - INTERVAL '90 days'
  GROUP BY 1
)
SELECT
  week_start,
  fee_revenue_usd,
  maker_notional_usd / NULLIF(total_notional_usd, 0) AS maker_volume_share
FROM weekly
ORDER BY 1;
```

**Explanation:** Maker share is a **volume** mix metric; fee revenue may not be proportional if fee schedules differ—mention joining a `fee_schedule` table if asked.

---

#### B1.3 — Open interest at end of day (CORE — full answer)

**Question:** Latest **open interest (USD)** per `symbol` as of each calendar day (one row per symbol-day).

```sql
WITH daily_snapshots AS (
  SELECT
    symbol,
    DATE_TRUNC('day', snapshot_ts)::date AS snap_date,
    open_interest_usd,
    ROW_NUMBER() OVER (
      PARTITION BY symbol, DATE_TRUNC('day', snapshot_ts)
      ORDER BY snapshot_ts DESC
    ) AS rn
  FROM positions
)
SELECT symbol, snap_date, open_interest_usd
FROM daily_snapshots
WHERE rn = 1;
```

**Explanation:** OI is a **snapshot** metric—take last snapshot per day, not sum of intraday rows.

---

#### B1.4 — Average funding rate by symbol (7-day) (CORE — full answer)

**Question:** 7-day **average funding rate** per symbol (funding events may be every 8h).

```sql
SELECT
  symbol,
  AVG(funding_rate) AS avg_funding_rate_7d,
  COUNT(*) AS funding_events
FROM funding
WHERE funding_ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY symbol
ORDER BY avg_funding_rate_7d DESC;
```

**Explanation:** For perps, funding affects carry cost; executives often care about **extreme** rates—pair with percentiles in follow-up.

---

#### B1.5 — Realized PnL proxy from trades (framework)

**Question:** Estimate **daily realized fee-adjusted volume** by user (simplified; no position ledger).

**Framework:** Without a positions table, state you need `realized_pnl` from ledger or reconstruct from fills + marks. If given `daily_user_pnl(user_id, trade_date, realized_pnl)`, aggregate with `SUM(realized_pnl) GROUP BY trade_date`. Discuss **mark price** timing and **funding** separately.

---

#### B1.6 — Fee per million notional (CORE — full answer)

**Question:** **Effective take rate** (bps) = fees / notional × 10,000 by `product_type` (last 7 days).

```sql
SELECT
  product_type,
  SUM(fee_usd) AS total_fees_usd,
  SUM(qty * price_usd) AS total_notional_usd,
  SUM(fee_usd) / NULLIF(SUM(qty * price_usd), 0) * 10000 AS effective_bps
FROM trades
WHERE trade_ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY product_type;
```

**Explanation:** bps = basis points of notional; split `is_maker` if fee tiers differ; subtract rebates if `fee_usd` is net.

---

#### B1.7 — Top symbols by volume share (CORE — full answer)

**Question:** Each symbol’s **% of total** notional yesterday.

```sql
WITH yesterday AS (
  SELECT
    symbol,
    SUM(qty * price_usd) AS notional_usd
  FROM trades
  WHERE trade_ts >= CURRENT_DATE - INTERVAL '1 day'
    AND trade_ts < CURRENT_DATE
  GROUP BY symbol
)
SELECT
  symbol,
  notional_usd,
  notional_usd / SUM(notional_usd) OVER () AS volume_share
FROM yesterday
ORDER BY volume_share DESC;
```

**Explanation:** Window denominator gives **shares that sum to 1**; use `CURRENT_DATE` boundaries consistent with warehouse timezone.

---

#### B1.8 — Options vs futures mix MoM (framework)

**Question:** Month-over-month change in **futures vs options** volume share.

**Framework:** Monthly notional by `product_type` → shares → `LAG` on share; watch **new listings** as structural breaks.

---

### Category 2 — User / trader cohorts & KYC funnel (7 questions)

#### B2.1 — KYC funnel conversion (CORE — full answer)

**Question:** Of users who signed up in March 2026, % reaching **KYC approved** within 7 days.

```sql
WITH march_signups AS (
  SELECT user_id, signup_ts
  FROM users
  WHERE signup_ts >= '2026-03-01' AND signup_ts < '2026-04-01'
),
converted AS (
  SELECT u.user_id
  FROM march_signups u
  JOIN users k ON k.user_id = u.user_id
  WHERE k.kyc_status = 'approved'
    AND k.kyc_approved_ts <= u.signup_ts + INTERVAL '7 days'
)
SELECT
  COUNT(DISTINCT m.user_id) AS signups,
  COUNT(DISTINCT c.user_id) AS kyc_7d,
  COUNT(DISTINCT c.user_id)::decimal / NULLIF(COUNT(DISTINCT m.user_id), 0) AS kyc_7d_rate
FROM march_signups m
LEFT JOIN converted c ON c.user_id = m.user_id;
```

**Explanation:** Funnel time box is **from signup**; exclude users still pending at day 7 unless definition says “ever within 7d.”

---

#### B2.2 — Activation: first trade within 72h of KYC (CORE — full answer)

**Question:** % of KYC-approved users whose **first trade** is within 72 hours of `kyc_approved_ts`.

```sql
WITH first_trade AS (
  SELECT user_id, MIN(trade_ts) AS first_trade_ts
  FROM trades
  GROUP BY user_id
),
cohort AS (
  SELECT u.user_id, u.kyc_approved_ts
  FROM users u
  WHERE u.kyc_status = 'approved'
    AND u.kyc_approved_ts >= '2026-01-01'
)
SELECT
  COUNT(*) AS kyc_approved_users,
  COUNT(*) FILTER (
    WHERE ft.first_trade_ts <= c.kyc_approved_ts + INTERVAL '72 hours'
  ) AS activated_72h,
  COUNT(*) FILTER (
    WHERE ft.first_trade_ts <= c.kyc_approved_ts + INTERVAL '72 hours'
  )::decimal / NULLIF(COUNT(*), 0) AS activation_rate
FROM cohort c
LEFT JOIN first_trade ft ON ft.user_id = c.user_id;
```

**Explanation:** `LEFT JOIN` so non-traders count in denominator—clarify if denominator should be “funded only.”

---

#### B2.3 — Weekly cohort size by signup week (CORE — full answer)

**Question:** Count of new users per **signup week** (last 12 weeks).

```sql
SELECT
  DATE_TRUNC('week', signup_ts) AS signup_week,
  COUNT(*) AS new_users
FROM users
WHERE signup_ts >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY 1
ORDER BY 1;
```

**Explanation:** Anchor cohort on **signup**, not first trade—different question.

---

#### B2.4 — Traders who traded 3+ distinct symbols in first week (CORE — full answer)

**Question:** Among users with first trade in last 30d, % trading **≥3 symbols** in first 7 days.

```sql
WITH first_trade AS (
  SELECT user_id, MIN(trade_ts) AS ft
  FROM trades
  GROUP BY user_id
  HAVING MIN(trade_ts) >= CURRENT_DATE - INTERVAL '30 days'
),
first_week AS (
  SELECT
    ft.user_id,
    COUNT(DISTINCT t.symbol) AS symbols_traded
  FROM first_trade ft
  JOIN trades t
    ON t.user_id = ft.user_id
   AND t.trade_ts >= ft.ft
   AND t.trade_ts < ft.ft + INTERVAL '7 days'
  GROUP BY ft.user_id
)
SELECT
  COUNT(*) AS new_traders,
  COUNT(*) FILTER (WHERE symbols_traded >= 3) AS diversified_traders,
  COUNT(*) FILTER (WHERE symbols_traded >= 3)::decimal / NULLIF(COUNT(*), 0) AS pct_diversified
FROM first_week;
```

**Explanation:** “First week” is anchored on **first trade**, not signup—common activation quality metric for multi-product exchanges.

---

#### B2.5 — Deposit before first trade (framework)

**Question:** Median hours from **first successful deposit** to **first trade**.

**Framework:** Per-user `MIN` deposit ts (status='success') and `MIN` trade ts → `EXTRACT(EPOCH FROM (trade - deposit))/3600` → `PERCENTILE_CONT(0.5)`.

---

#### B2.6 — Power users: top decile by 30d volume (CORE — full answer)

**Question:** Identify users in **top 10%** by notional last 30 days.

```sql
WITH user_vol AS (
  SELECT
    user_id,
    SUM(qty * price_usd) AS notional_30d
  FROM trades
  WHERE trade_ts >= CURRENT_DATE - INTERVAL '30 days'
  GROUP BY user_id
),
ranked AS (
  SELECT
    user_id,
    notional_30d,
    NTILE(10) OVER (ORDER BY notional_30d DESC) AS volume_decile
  FROM user_vol
)
SELECT user_id, notional_30d
FROM ranked
WHERE volume_decile = 1;
```

**Explanation:** Decile 1 = top 10%; exclude `is_wash_flag = true` users if column exists before VIP targeting.

---

#### B2.7 — Cross-country signup quality (framework)

**Question:** KYC approval rate by `country` with minimum volume filter.

**Framework:** Aggregate by country → `HAVING COUNT(*) >= 100` for stability; mention **geo compliance** restrictions separately.

---

### Category 3 — Time series & volume spikes (6 questions)

#### B3.1 — Hourly volume vs same hour last week (CORE — full answer)

**Question:** For each hour today, compare notional to **same hour 7 days ago** (% change).

```sql
WITH hourly AS (
  SELECT
    DATE_TRUNC('hour', trade_ts) AS hour_ts,
    SUM(qty * price_usd) AS notional_usd
  FROM trades
  WHERE trade_ts >= CURRENT_DATE - INTERVAL '8 days'
  GROUP BY 1
),
today AS (
  SELECT * FROM hourly WHERE hour_ts >= DATE_TRUNC('day', CURRENT_TIMESTAMP)
),
prior AS (
  SELECT
    hour_ts + INTERVAL '7 days' AS hour_ts_aligned,
    notional_usd AS notional_prior_week
  FROM hourly
)
SELECT
  t.hour_ts,
  t.notional_usd,
  p.notional_prior_week,
  (t.notional_usd - p.notional_prior_week) / NULLIF(p.notional_prior_week, 0) AS pct_change_vs_pw
FROM today t
LEFT JOIN prior p ON p.hour_ts_aligned = t.hour_ts
ORDER BY t.hour_ts;
```

**Explanation:** Align on **clock hour**; for crypto, also consider **BTC volatility** events as exogenous drivers.

---

#### B3.2 — Detect hours with volume > 3× trailing 7-day avg for that hour-of-day (CORE — full answer)

**Question:** Flag **anomaly hours** (spike definition above).

```sql
WITH hourly AS (
  SELECT
    DATE_TRUNC('hour', trade_ts) AS hour_ts,
    EXTRACT(HOUR FROM trade_ts) AS hod,
    SUM(qty * price_usd) AS notional_usd
  FROM trades
  WHERE trade_ts >= CURRENT_DATE - INTERVAL '30 days'
  GROUP BY 1, 2
),
baseline AS (
  SELECT
    hod,
    AVG(notional_usd) AS avg_notional_hod
  FROM hourly
  WHERE hour_ts < DATE_TRUNC('day', CURRENT_TIMESTAMP)
  GROUP BY hod
)
SELECT h.hour_ts, h.notional_usd, b.avg_notional_hod
FROM hourly h
JOIN baseline b ON b.hod = h.hod
WHERE h.hour_ts >= CURRENT_DATE - INTERVAL '2 days'
  AND h.notional_usd > 3 * b.avg_notional_hod;
```

**Explanation:** Seasonality by **hour-of-day** beats global average; mention listing events / API outages as follow-up joins.

---

#### B3.3 — 7-day rolling average daily volume (CORE — full answer)

```sql
WITH daily AS (
  SELECT
    DATE_TRUNC('day', trade_ts)::date AS d,
    SUM(qty * price_usd) AS notional_usd
  FROM trades
  GROUP BY 1
)
SELECT
  d,
  notional_usd,
  AVG(notional_usd) OVER (
    ORDER BY d
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS rolling_7d_avg
FROM daily
ORDER BY d;
```

**Explanation:** Frame **ROWS** vs **RANGE** for gaps in calendar days.

---

#### B3.4 — Day-over-day % change with zero-safe divide (CORE — full answer)

```sql
WITH daily AS (
  SELECT
    DATE_TRUNC('day', trade_ts)::date AS d,
    SUM(qty * price_usd) AS notional_usd
  FROM trades
  GROUP BY 1
)
SELECT
  d,
  notional_usd,
  LAG(notional_usd) OVER (ORDER BY d) AS prior_day_notional,
  (notional_usd - LAG(notional_usd) OVER (ORDER BY d))
    / NULLIF(LAG(notional_usd) OVER (ORDER BY d), 0) AS dod_pct_change
FROM daily
ORDER BY d DESC
LIMIT 30;
```

**Explanation:** `NULLIF` avoids divide-by-zero on quiet days; first day has NULL change.

---

#### B3.5 — Cumulative volume in month (framework)

**Framework:** `SUM(notional) OVER (PARTITION BY month ORDER BY d)` for “month-to-date volume” charts.

---

#### B3.6 — Volume per active trader per day (CORE — full answer)

**Question:** **Volume per active trader** = daily notional / distinct traders that day.

```sql
SELECT
  DATE_TRUNC('day', trade_ts)::date AS d,
  SUM(qty * price_usd) AS notional_usd,
  COUNT(DISTINCT user_id) AS active_traders,
  SUM(qty * price_usd) / NULLIF(COUNT(DISTINCT user_id), 0) AS volume_per_active_trader
FROM trades
WHERE trade_ts >= CURRENT_DATE - INTERVAL '60 days'
GROUP BY 1
ORDER BY 1;
```

**Explanation:** Rising volume with flat “per trader” suggests **breadth**; flat traders with up per-trader suggests **whale** activity.

---

### Category 4 — Window functions & cohort retention (7 questions)

#### B4.1 — Classic weekly retention after first trade (CORE — full answer)

**Question:** For users whose **first trade** was in week W0, what % traded again in week W1, W2, W4?

```sql
WITH first_trade AS (
  SELECT user_id, DATE_TRUNC('week', MIN(trade_ts)) AS cohort_week
  FROM trades
  GROUP BY user_id
),
activity AS (
  SELECT
    t.user_id,
    ft.cohort_week,
    DATE_TRUNC('week', t.trade_ts) AS active_week
  FROM trades t
  JOIN first_trade ft ON ft.user_id = t.user_id
),
cohort_size AS (
  SELECT cohort_week, COUNT(DISTINCT user_id) AS users
  FROM first_trade
  GROUP BY cohort_week
)
SELECT
  a.cohort_week,
  (a.active_week - a.cohort_week) / INTERVAL '1 week' AS weeks_since_first,
  COUNT(DISTINCT a.user_id) AS active_users,
  COUNT(DISTINCT a.user_id)::decimal / NULLIF(cs.users, 0) AS retention_rate
FROM activity a
JOIN cohort_size cs ON cs.cohort_week = a.cohort_week
WHERE (a.active_week - a.cohort_week) IN (
  INTERVAL '0 weeks', INTERVAL '1 week', INTERVAL '2 weeks', INTERVAL '4 weeks'
)
GROUP BY 1, 2, cs.users
ORDER BY 1, 2;
```

**Explanation:** Cohort anchor = **first trade** (funded trader), not signup; incomplete weeks need censoring.

---

#### B4.2 — Running total volume per user (CORE — full answer)

```sql
SELECT
  user_id,
  trade_ts,
  qty * price_usd AS notional,
  SUM(qty * price_usd) OVER (
    PARTITION BY user_id
    ORDER BY trade_ts
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_notional
FROM trades;
```

**Explanation:** Useful for **tier upgrades** and whale monitoring.

---

#### B4.3 — Rank top 5 traders per day by volume (CORE — full answer)

```sql
WITH daily_user AS (
  SELECT
    DATE_TRUNC('day', trade_ts)::date AS d,
    user_id,
    SUM(qty * price_usd) AS notional_usd
  FROM trades
  GROUP BY 1, 2
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY d ORDER BY notional_usd DESC) AS rn
  FROM daily_user
)
SELECT * FROM ranked WHERE rn <= 5;
```

**Explanation:** `ROW_NUMBER` vs `DENSE_RANK` if ties should all appear in top 5.

---

#### B4.4 — Days since last trade (CORE — full answer)

```sql
WITH last_activity AS (
  SELECT
    user_id,
    MAX(trade_ts) AS last_trade_ts
  FROM trades
  GROUP BY user_id
)
SELECT
  user_id,
  CURRENT_DATE - last_trade_ts::date AS days_since_last_trade
FROM last_activity
WHERE last_trade_ts < CURRENT_DATE - INTERVAL '7 days'
ORDER BY days_since_last_trade DESC;
```

**Explanation:** Filter inactive traders for **reactivation** lists; define “churned” threshold (e.g. 30d) with product.

---

#### B4.5 — Second-trade within 14 days (framework)

**Framework:** `MIN` and `NTH_VALUE` or two-row window: time between 1st and 2nd trade—early retention KPI.

---

#### B4.6 — Cohort revenue (fees) by signup month (framework)

**Framework:** Join signup month to trades → `SUM(fee_usd)` by `months_since_signup` pivot.

---

#### B4.7 — Stickiness: DAU/WAU (framework)

**Framework:** Distinct traders per day / distinct traders in trailing 7d—define UTC day.

---

### Category 5 — Risk-adjacent patterns (high level) (5 questions)

*Disclaimer: analytics flags for investigation—not legal advice or compliance determinations.*

#### B5.1 — Same-IP multiple accounts trading one symbol (CORE — full answer)

**Question:** IPs with **≥5 distinct user_id** trading the same `symbol` on the same day (given `sessions(user_id, ip, session_ts)`).

```sql
WITH daily_ip AS (
  SELECT
    DATE_TRUNC('day', s.session_ts)::date AS d,
    s.ip,
    t.symbol,
    COUNT(DISTINCT s.user_id) AS distinct_users
  FROM sessions s
  JOIN trades t ON t.user_id = s.user_id
    AND DATE_TRUNC('day', t.trade_ts) = DATE_TRUNC('day', s.session_ts)
  WHERE s.session_ts >= CURRENT_DATE - INTERVAL '7 days'
  GROUP BY 1, 2, 3
)
SELECT * FROM daily_ip WHERE distinct_users >= 5;
```

**Explanation:** Flag for **review**; VPN/shared mobile NAT create false positives—pair with device graph if available.

---

#### B5.2 — User concentration: top 1% share of volume (CORE — full answer)

```sql
WITH user_vol AS (
  SELECT user_id, SUM(qty * price_usd) AS notional
  FROM trades
  WHERE trade_ts >= CURRENT_DATE - INTERVAL '30 days'
  GROUP BY user_id
),
ordered AS (
  SELECT
    user_id,
    notional,
    SUM(notional) OVER () AS total_notional,
    SUM(notional) OVER (ORDER BY notional DESC) AS cum_notional
  FROM user_vol
)
SELECT
  MAX(cum_notional / NULLIF(total_notional, 0)) FILTER (
    WHERE cum_notional <= 0.01 * MAX(total_notional) OVER ()
  ) AS top_1pct_volume_share_approx
FROM ordered;
```

**Explanation:** Simpler alt: `NTILE(100)` on users; sum notional where tile=1. Discuss **market maker** exemptions.

---

#### B5.3 — Round-trip volume within 5 minutes (framework)

**Question:** Users with buy and sell notional ratio ≈ 1 within 5-minute windows (wash *signal*).

**Framework:** Bucket trades to 5m → per user/symbol sum buy vs sell notional → filter high balance and min volume.

---

#### B5.4 — Sudden leverage / position size jump (framework)

**Framework:** Compare max position to 30d median per user; needs positions history—not compliance ruling.

---

#### B5.5 — Off-hours API burst (framework)

**Framework:** Trades with `source='api'` hourly z-score vs baseline; join rate limits from logs.

---

### Category 6 — A/B tests on product features (5 questions)

#### B6.1 — Intent-to-treat conversion lift (CORE — full answer)

**Question:** Conversion = **first trade within 7d of assignment**; compare variants.

```sql
WITH assigned AS (
  SELECT user_id, variant, assigned_ts
  FROM ab_users
  WHERE experiment_id = 'onboarding_v3'
),
outcome AS (
  SELECT
    a.user_id,
    a.variant,
    MIN(t.trade_ts) AS first_trade_ts
  FROM assigned a
  LEFT JOIN trades t
    ON t.user_id = a.user_id
   AND t.trade_ts >= a.assigned_ts
   AND t.trade_ts < a.assigned_ts + INTERVAL '7 days'
  GROUP BY 1, 2
)
SELECT
  variant,
  COUNT(*) AS assigned_users,
  COUNT(*) FILTER (WHERE first_trade_ts IS NOT NULL) AS converted,
  COUNT(*) FILTER (WHERE first_trade_ts IS NOT NULL)::decimal
    / NULLIF(COUNT(*), 0) AS conversion_rate
FROM outcome
GROUP BY variant;
```

**Explanation:** ITT includes users who never saw UI if assignment is at login; mention **SRM** check on counts.

---

#### B6.2 — Exclude cross-over users (CORE — full answer)

```sql
WITH assigned AS (
  SELECT user_id, variant, assigned_ts
  FROM ab_users
  WHERE experiment_id = 'onboarding_v3'
),
crossover AS (
  SELECT user_id
  FROM ab_users
  WHERE experiment_id = 'onboarding_v3'
  GROUP BY user_id
  HAVING COUNT(DISTINCT variant) > 1
)
SELECT a.*
FROM assigned a
LEFT JOIN crossover x ON x.user_id = a.user_id
WHERE x.user_id IS NULL;
```

**Explanation:** Use clean set for **per-protocol**; report both ITT and clean if asked.

---

#### B6.3 — A/B on fee promo: revenue per user (CORE — full answer)

**Question:** Average **fee revenue per assigned user** in 14 days post-assignment by variant.

```sql
WITH assigned AS (
  SELECT user_id, variant, assigned_ts
  FROM ab_users
  WHERE experiment_id = 'fee_promo_q2'
),
fees AS (
  SELECT
    a.user_id,
    a.variant,
    COALESCE(SUM(t.fee_usd), 0) AS fees_14d
  FROM assigned a
  LEFT JOIN trades t
    ON t.user_id = a.user_id
   AND t.trade_ts >= a.assigned_ts
   AND t.trade_ts < a.assigned_ts + INTERVAL '14 days'
  GROUP BY 1, 2
)
SELECT
  variant,
  COUNT(*) AS users,
  AVG(fees_14d) AS avg_fee_per_user,
  SUM(fees_14d) AS total_fees
FROM fees
GROUP BY variant;
```

**Explanation:** Promo may lift volume but **lower** fee/user—pair with `SUM(qty*price_usd)` guardrail and liquidation counts.

---

#### B6.4 — Sequential test bias (framework)

**Framework:** Mention peeking, pre-registered sample size, or sequential testing tools—don’t stop at first significance.

---

#### B6.5 — Stratify by country (framework)

**Framework:** `GROUP BY variant, country` or CUPED on pre-period volume for variance reduction.

---

### Category 7 — Joins, grain & debugging (4 questions — frameworks)

#### B7.1 — Fan-out when joining users to trades (framework)

**Framework:** Aggregates trades **before** join; demonstrate duplicate inflation if joining raw trades to user attributes.

#### B7.2 — Reconcile Tableau total vs SQL (framework)

**Framework:** Compare filters, inner vs left join, distinct grain, timezone—see [sql-100-questions-with-answers.md](./sql-100-questions-with-answers.md) reconciliation scenarios.

#### B7.3 — Late-arriving trades (framework)

**Framework:** Partition by `trade_ts` vs `ingested_at`; restate last 3 days metrics in ETL job.

#### B7.4 — Optimize heavy aggregation (framework)

**Framework:** Pre-aggregate daily mart; filter on partition key; avoid `SELECT *`—link senior BC guide §performance.

---

### SQL quick map to existing guides

| Topic in this doc | Drill deeper in |
|-------------------|-----------------|
| Retention, funnels | `sql-100` cohort sections; `sql-interview-questions-senior-bc` §cohorts |
| A/B, contamination | `role-requirements-interview-prep` §SQL; `sql-100` experiment questions |
| Window functions | `sql-100` §windows; senior BC §multi-step |
| Gaming → crypto metaphor | Junglee churn/NGR stories in `role-requirements-interview-prep` |

---

## Part C: Tableau interview prep (36 questions)

---

### Category 1 — LOD expressions (7 questions, 5 with model answers)

#### C1.1 — FIXED: fee revenue per trader vs company average (MODEL)

**Q:** Each trader’s 30d fees vs **overall average fees per trader**.

**Answer:**  
`{ FIXED [user_id] : SUM([fee_usd]) }` on a view with filters for last 30d.  
Company avg: `{ FIXED : AVG({ FIXED [user_id] : SUM([fee_usd]) }) }` or LOD on a trader-level scaffold.  
**Calc:** `[User Fees] - [Company Avg User Fees]`.  
**Say aloud:** FIXED sets grain; filters on trade date affect inner aggregates unless INCLUDE/EXCLUDE needed.

---

#### C1.2 — INCLUDE: state-level avg volume with national context (MODEL)

**Q:** Bar chart of volume by `symbol` colored vs **category average**.

**Answer:** `AVG({ INCLUDE [product_type] : SUM([notional]) })` — verify whether SUM is pre-aggregated in datasource.

---

#### C1.3 — EXCLUDE: subtotal without product breakdown (MODEL)

**Q:** Table with product rows but **total row** without product dimension.

**Answer:** `{ EXCLUDE [product_type] : SUM([notional]) }` alongside `SUM([notional])`.

---

#### C1.4 — FIXED cohort retention numerator (MODEL)

**Q:** % of March cohort active in week 4.

**Answer:** Build **cohort dimension** (first trade month) in SQL or LOD `MIN([trade_ts])` per user → `% active` with `{ FIXED [cohort_month], [week_n] : COUNTD([user_id]) }` — prefer SQL mart for retention matrices.

---

#### C1.5 — COUNTD users with LOD vs table calc (MODEL)

**Q:** When use `COUNTD` vs `{ FIXED [user_id] : MAX(1) }`?

**Answer:** COUNTD at viz grain; LOD when blending or fixing grain mismatched to viz level (e.g. user attrs on trade-level data).

---

#### C1.6 — LOD performance (framework)

**Framework:** LODs force extra queries; prefer **warehouse mart** for heavy FIXED; use `{ FIXED [user_id] : ... }` only when necessary.

---

#### C1.7 — Nested LOD caveat (framework)

**Framework:** Tableau limits nesting; push complex nested logic to SQL/Power Query.

---

### Category 2 — Calculated fields & table calculations (6 questions, 4 model)

#### C2.1 — Bps take rate (MODEL)

`SUM([fee_usd]) / SUM([notional_usd]) * 10000`

---

#### C2.2 — WoW % change (MODEL)

`ZN( (SUM([notional]) - LOOKUP(SUM([notional]), -1)) / ABS(LOOKUP(SUM([notional]), -1)) )`  
Table calc: compute using **Table (across)** on week dimension.

---

#### C2.3 — INDEX filter top 10 symbols (MODEL)

`INDEX() <= 10` after sorting by `-SUM([notional])` — mention **rank** tie handling.

---

#### C2.4 — RUNNING_SUM for MTD volume (MODEL)

`RUNNING_SUM(SUM([notional]))` with Month on filter, Day on columns.

---

#### C2.5 — DATEPARSE / DATETIME for crypto UTC (framework)

**Framework:** Align warehouse UTC; `DATETRUNC('hour', [trade_ts])` in calc or in SQL.

---

#### C2.6 — IF/ELSE tier label (framework)

**Framework:** `IF [30d_volume] >= 1000000 THEN "Whale" ELSEIF ... END`

---

### Category 3 — Dashboard design: executives vs traders (5 questions, 3 model)

#### C3.1 — Executive dashboard (MODEL)

**Answer:**  
- **One screen:** MTD volume, fee revenue, active traders, KYC conversion, retention sparkline.  
- **Minimal interactivity:** region/product filter, 30/90d toggle.  
- **Annotations** for listings, incidents.  
- **Color:** neutral; RAG only on goals.  
- **No order book** clutter.

---

#### C3.2 — Trader-facing / desk dashboard (MODEL)

**Answer:**  
- **High refresh** (near real-time if supported).  
- **OI, funding, top movers, liquidation feed**, per-symbol drill.  
- Dense tables OK; dark theme common.  
- Latency and **exact timestamps** matter.

---

#### C3.3 — Mobile vs desktop (MODEL)

**Answer:** Device layouts in Tableau; prioritize KPI cards + one trend on phone; defer heavy LOD sheets.

---

#### C3.4 — KPI card + trend pairing (framework)

**Framework:** Big number + `% vs prior period` small text; sync period parameter.

---

#### C3.5 — Explain volume drop in 3 bullets for CEO (framework)

**Framework:** Mix (product), concentration (whale), external (BTC move)—link to Part D.

---

### Category 4 — Performance optimization (4 questions, 2 model)

#### C4.1 — Extract vs live (MODEL)

**Answer:** Executives: nightly/hourly **hyper extract**; traders: live with row-level security or dedicated mart; limit marks.

---

#### C4.2 — Reduce mark count (MODEL)

**Answer:** Pre-aggregate to day×symbol; hide unused fields; avoid `% of total` table calcs on millions of rows; use **context filters**.

---

#### C4.3 — Context filters (framework)

**Framework:** Apply selective dimension as context so other calcs compute on smaller set.

---

#### C4.4 — Performance Recorder (framework)

**Framework:** Record load/interaction; fix slow sheets first; push calcs to DB.

---

### Category 5 — Data blending vs joins (3 questions, 2 model)

#### C5.1 — When blend (MODEL)

**Answer:** Different grains/dbs (e.g. **marketing spend** daily + **trades** hourly) with linking field date; watch **many-to-many** inflate.

---

#### C5.2 — When join in SQL (MODEL)

**Answer:** Large fact+fact joins, retention, anything needing **predictable grain**—prefer warehouse join → single Tableau connection.

---

#### C5.3 — Validate blend results (framework)

**Framework:** Compare blended KPI to SQL gold query; check linking field cardinality.

---

### Category 6 — Parameters, actions, sets (5 questions, 3 model)

#### C6.1 — Parameter-driven metric switch (MODEL)

**Answer:** Parameter `Metric` = Volume / Fees / Traders → calculated field  
`CASE [Metric] WHEN 'Volume' THEN SUM([notional]) ... END`

---

#### C6.2 — Filter action drill (MODEL)

**Answer:** Dashboard action: select symbol on overview → filter detail sheets (OI, funding, top traders).

---

#### C6.3 — Sets for whale watchlist (MODEL)

**Answer:** Top N by volume set + combined set for “strategic accounts”; use in filter or highlight.

---

#### C6.4 — Parameter + date range (framework)

**Framework:** `trade_ts` between `[Start Parameter]` and `[End Parameter]` on context.

---

#### C6.5 — URL action to external block explorer (framework)

**Framework:** Optional; less common for CEX—API status page link for incidents.

---

### Category 7 — Storytelling for non-technical stakeholders (3 questions, 2 model)

#### C7.1 — Structure a 10-minute readout (MODEL)

**Answer:** (1) **Headline** (2) **So what** for P&L (3) **3 drivers** with charts (4) **Recommendation** (5) **Risks/caveats** (data lag, one-off events).

---

#### C7.2 — Annotate BTC crash week (MODEL)

**Answer:** Reference line + text: “11 Mar liquidation cascade”; separate **volatility** from **platform bug**.

---

#### C7.3 — Avoid chart junk (framework)

**Framework:** Dual axis sparingly; start bar axis at zero for volume; label last point.

---

### Category 8 — Hands-on scenarios (3 step-by-step, 1 framework)

#### C8.1 — BUILD: Daily trading volume by product (MODEL — step-by-step)

1. **Connect** to `daily_product_metrics` mart (grain: `date`, `product_type`, `notional_usd`, `trade_count`) or SQL custom query aggregating `trades`.  
2. **Verify grain** in Data Source: one row per date×product.  
3. **Sheet 1 — Trend:** Columns `trade_date` (continuous day), Rows `SUM(notional_usd)`, Color `product_type`, filter last 90 days.  
4. **Sheet 2 — Share:** Pie or bar `% of total` with **quick table calc** “Percent of Total” along product.  
5. **Sheet 3 — Quality:** `COUNTD(user_id)` or `trade_count` to spot volume without traders (bot/API).  
6. **Dashboard:** Stack trend full width; place share + KPI cards (MTD volume, MoM %); add **parameter** for product filter and **highlighter** for options vs futures.  
7. **QA:** Compare MTD to SQL `SUM` sanity check; document **UTC** in subtitle.  
8. **Publish:** Schedule extract refresh after ETL SLA; set permissions by role.

---

#### C8.2 — BUILD: KYC funnel dashboard (MODEL — abbreviated steps)

Funnel chart from ordered stages (signup → KYC submit → approved → deposit → first trade); conversion % table calc between stages; cohort filter on signup week.

---

#### C8.3 — BUILD: Funding rate heatmap (MODEL — abbreviated)

Rows `symbol`, columns `hour`, color `AVG(funding_rate)`; filter perp only; tooltip OI.

---

#### C8.4 — BUILD: Executive risk snapshot (framework)

Concentration KPI, anomaly flags from SQL, liquidation count trend—keep legal review on labels.

---

### Tableau frameworks batch (remaining practice)

| ID | Question | Framework hint |
|----|----------|----------------|
| C9.1 | Dual-axis volume + OI | Shared date axis; synchronize; OI on right axis |
| C9.2 | Show both % and absolute | Two calcs or combo chart |
| C9.3 | Dynamic title with filter | `"Volume for " + ATTR([symbol])` |
| C9.4 | Replace null with 0 | `ZN()` or `IFNULL` |
| C9.5 | Discrete vs continuous date | Week bars vs line trend |
| C9.6 | Row-level security | User filter on `country` or desk |
| C9.7 | Published data source governance | Certified fields, descriptions |
| C9.8 | Export for board pack | PDF pixel size; hide filters |
| C9.9 | Explain INCLUDE with example | One sentence + whiteboard dimensions |
| C9.10 | When NOT to use Tableau | Sub-second algo trading UI—use custom front-end |

---

## Part D: Combined SQL + Tableau case studies (5)

### D1 — Volume dropped 15% week-over-week

1. **Confirm:** Same definition (notional vs contracts), timezone, incomplete week censoring.  
2. **SQL:** Decompose `SUM(notional)` by `product_type`, `symbol`, `client_type` (API/UI), `country`; WoW with `LAG`.  
3. **Tableau:** Highlight tree map of contribution to delta; waterfall of **mix shift**.  
4. **Hypotheses:** Lost whale, listing delist, competitor promo, incident, BTC low-vol week.  
5. **Prove:** Trader-level concentration (top 10 users’ share); join **marketing calendar**.  
6. **Recommend:** If whale churn → VIP desk; if product → fee promo with risk guardrails; if market → communicate context to execs.

---

### D2 — KYC conversion improved but activated traders flat

SQL: funnel conversion by stage week-over-week; time-to-first-trade distribution. Tableau: slope chart stages. Diagnose **deposit friction** or **first-trade UX**; run A/B on onboarding (Part B6).

---

### D3 — Maker share fell after fee schedule change

SQL: maker % and fee revenue per day pre/post; segment by tier. Tableau: dual period dashboard with parameter cutover date. Check **unintended taker migration** and net revenue (not just volume).

---

### D4 — Anomaly flag: 3× hourly volume on one symbol

SQL: spike sheet (B3.2); join news/listing table; IP concentration (B5.1). Tableau: annotate timeline; desk dashboard for OI/funding. Escalate path: analytics → product/risk → compliance if warranted.

---

### D5 — A/B wins on signup CTR but fee revenue down

SQL: ITT on conversion + **secondary** `SUM(fee_usd)` per user 14d; check **SRM** and whale in treatment. Tableau: experiment dashboard with guardrail metrics. Recommend: ship UX, adjust fee promo, or segment variant.

---

## Part E: 60-second pitch + Top 5 STAR stories (Delta JD)

### 60-second pitch (Delta-tuned)

> I'm **Sonaal Topno**, a Senior Business Consultant with 10+ years turning data into revenue and retention outcomes—currently with **Flutter Entertainment**, on deployment to **Sportsbet Melbourne** for marketing and insights, after three years driving RMG analytics at **Junglee Games**.
>
> I own the full loop: **define KPIs** executives trust, **query at scale in SQL**, **ship Tableau or Power BI** leaders actually use, and **prove impact with A/B tests and models**. At Junglee I cut new-user churn **21%**, lifted **NGR 4.2%** on money-movement experiments, and built **84%-accuracy** fraud detection. At Sportsbet I deliver campaign analytics and faster insight delivery with **Databricks SQL** and modern tooling.
>
> **Delta** is derivatives at crypto speed—volume, OI, funding, and trader lifecycle. I've done the same muscle in **regulated, real-money consumer platforms**: activation funnels, fee economics, churn, and risk-aware experimentation. I'd love to help Delta grow **traders and volume** without flying blind on margin and product mix.

*Pause after the three Junglee numbers; close with:* “I can walk through one experiment from hypothesis to SQL to dashboard.”

---

### Top 5 STAR stories mapped to Lead BA @ Delta

| # | Story | **S**ituation | **T**ask | **A**ction | **R**esult | JD hook |
|---|--------|---------------|----------|------------|------------|---------|
| 1 | **Money-movement A/B (Rummy.com)** | Revenue growth stalled; trust in “gut” promos | Design test on deposit/withdraw UX with guardrails | SQL cohorts, holdouts, exec readout in BI | **NGR +4.2%**, ARPU +2.1%, rev/deposit +12pp | Experimentation, SQL, stakeholder influence |
| 2 | **Churn model deployment** | High early churn on real-money games | Build + operationalize churn scores | Python/GBM, segments, CRM triggers | New-user churn **−21%**, existing **−12%** | Predictive analytics (R/Python), retention ≈ trader retention |
| 3 | **Fraud / high-risk detection** | Bonus abuse threatening margin | Risk scoring with explainable flags | XGBoost, SQL feature pipelines, ops playbook | **84%** accuracy; faster review queues | Risk-adjacent analytics (not legal advice) |
| 4 | **Sportsbet campaign analytics** | APAC marketing needed faster decisions | Self-serve dashboards + ad-hoc SQL | Power BI, Databricks SQL, MCP-assisted workflows | Shorter cycle time; leadership visibility on campaigns | Tableau-like storytelling, cross-func marketing/product |
| 5 | **Ipsos segmentation cost takeout** | Client media spend inefficient | Predictive targeting model | R/Python, segmentation, KPI tracking | **~30%** marketing cost reduction | Growth efficiency; non-tech client communication |

*Rehearse each in **≤90 seconds**; add Delta bridge line: “Same pattern for KYC → first trade → repeat volume.”*

---

## Part F: Acknowledgement email template (recruiter)

**Subject:** Lead Business Analyst — thank you (Sonaal Topno)

---

Hi [Recruiter Name],

Thank you for reaching out about the **Lead Business Analyst** role at **Delta Exchange**. I’m interested in the opportunity and appreciate you sharing the details.

I have **10+ years** in analytics and business consulting on regulated, high-velocity consumer platforms (currently **Flutter Entertainment / Sportsbet**, previously **Junglee Games**), with strong hands-on **SQL**, **Tableau/Power BI**, and **Python** for analysis and experimentation. I’d welcome a conversation on how I can support Delta’s trading, growth, and product analytics priorities.

Please let me know suitable times for a call in the coming days. I’ve attached my latest resume for your reference.

Best regards,  
**Sonaal Topno**  
[Phone] | [LinkedIn] | [Email]

---

*Note: Recruiter addressed you as “Sonal”—politely use your correct spelling **Sonaal** in signature and subject line only; no need to correct them bluntly in the opening line unless you want: “(spelling: Sonaal Topno)”.*

---

## Prep checklist (this week)

| Day | Focus |
|-----|--------|
| 1 | Part A + pitch + STAR 1–2 |
| 2 | SQL Cat 1–2 (write queries without looking) |
| 3 | SQL Cat 3–4 + `sql-100` windows drill |
| 4 | SQL Cat 5–7 + Tableau LOD (C1) |
| 5 | Tableau dashboards C3, C8 + Performance |
| 6 | Part D cases out loud (whiteboard) |
| 7 | Mock: 2 SQL + 1 Tableau scenario + questions for them |

**Questions for Delta (ask the panel):** How do you define **active trader**? Where does **metric truth** live (warehouse vs Tableau)? How do analytics and **risk/compliance** interact on flags? What’s the **experimentation** stack? What would success look like in **90 days** for this lead?

---

*End of document.*
