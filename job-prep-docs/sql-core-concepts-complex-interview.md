# SQL Core Concepts — Complex Interview Level

**Prepared for:** Sonaal Topno — Senior / Lead Business Analyst (Delta Exchange, big tech, gaming analytics)  
**Focus:** Conceptual depth for senior BA / analytics interviews — not beginner syntax drills.  
**Dialect:** PostgreSQL / BigQuery-style SQL unless noted.

**Practice drills (syntax + 100 worked Q&A):** [sql-100-questions-with-answers.md](./sql-100-questions-with-answers.md)

**Question count in this doc:** **56** complex scenario/concept questions + **15** rapid-fire “must know”

---

## Part 1 — Concept primers (read once, then drill questions)

### SQL logical execution order

SQL is **declarative**: you describe *what*, the engine decides *how*. For interviews, state the **logical** order (not necessarily physical):

1. `FROM` (+ `JOIN`) — build row sets  
2. `WHERE` — filter rows **before** grouping  
3. `GROUP BY` — collapse to grain  
4. `HAVING` — filter **groups**  
5. `SELECT` — project expressions (including aggregates)  
6. `DISTINCT` — dedupe projected rows  
7. `ORDER BY` — sort  
8. `LIMIT` / `OFFSET` — cap rows  

**Interview hook:** `WHERE` cannot reference `SELECT` aliases in standard SQL; `HAVING` can reference aggregates but not non-aggregated columns unless they’re in `GROUP BY`.

### JOIN semantics

- **INNER:** keep only matching keys on both sides.  
- **LEFT:** all left rows; right columns NULL when no match.  
- **FULL OUTER:** preserve both sides; NULLs where unmatched.  
- **CROSS:** Cartesian product (every left × every right).  
- **Semi-join** (`EXISTS` / `IN`): “is there *any* match?” — no row multiplication.  
- **Anti-join** (`NOT EXISTS` / `NOT IN` / `LEFT JOIN … WHERE right.key IS NULL`): “no match exists.”  

**Trap:** joining at wrong grain multiplies rows → inflated `SUM`/`COUNT(*)`.

### NULL logic

- `NULL` means **unknown**, not zero or empty string.  
- Any comparison with `NULL` (`=`, `<>`, `<`) yields **UNKNOWN** (filtered out by `WHERE` unless you use `IS NULL`).  
- `COUNT(*)` counts rows; `COUNT(col)` ignores NULLs in `col`.  
- `SUM`/`AVG` ignore NULLs; `AVG` denominator is non-null values only.  
- Three-valued logic: TRUE, FALSE, UNKNOWN — `WHERE` keeps only TRUE.

### Set theory

Relational algebra maps to SQL: **selection** (`WHERE`), **projection** (`SELECT`), **join**, **union** (`UNION` / `UNION ALL`), **difference** (`EXCEPT` / `NOT IN` patterns), **intersection** (`INTERSECT`).  
`UNION` dedupes; `UNION ALL` is faster and preserves duplicates — choose intentionally.

### Grain

**Grain** = what one row **means** (e.g. one user-day, one order line, one trade fill). Every metric must be defined at a grain; joins must **preserve or intentionally change** grain.  
Rule: write the grain in English before writing SQL.

### ACID (OLTP)

- **Atomicity:** all-or-nothing transaction.  
- **Consistency:** constraints hold after commit.  
- **Isolation:** concurrent transactions don’t see each other’s uncommitted work (level-dependent).  
- **Durability:** committed data survives failure.  

Analytics warehouses often relax isolation; still know why double-counting happens without idempotent loads.

### Isolation levels (conceptual)

From weakest to strongest (typical anomalies):

| Level | Dirty read | Non-repeatable read | Phantom read |
|-------|------------|---------------------|--------------|
| Read uncommitted | possible | possible | possible |
| Read committed | no | possible | possible |
| Repeatable read | no | no | possible (varies by DB) |
| Serializable | no | no | no |

**BA angle:** reporting “as of close” vs real-time ledger may disagree — define snapshot time and isolation.

### Indexes (conceptual)

B-tree (range/equality), hash (equality), bitmap (low cardinality in some engines).  
**Sargable** predicates: `col = x`, `col BETWEEN`, `col LIKE 'prefix%'` — not `YEAR(col) = 2025` on indexed `col` without functional index.  
Covering index: includes projected columns → index-only scan.

### Partitioning

Split large tables by **partition key** (date, region). Pruning skips partitions in queries.  
**Trap:** partition key must appear in filters for benefit; wrong partition column (e.g. `user_id` when queries are daily revenue) wastes scans.

### OLTP vs OLAP

| | OLTP | OLAP |
|---|------|------|
| Workload | many short writes | heavy reads, scans, aggregates |
| Schema | normalized | denormalized / star |
| Consistency | strong, row-level | eventual / snapshot |
| Examples | orders, trades, ledger | marts, dashboards |

### Star schema basics

**Fact** table at transaction/event grain (measures: amount, qty). **Dimensions** describe context (user, product, date).  
**Surrogate keys** in dims; facts store dimension keys + degenerate dimensions (e.g. `order_id` on fact).  
**Slowly changing dimensions (SCD):** Type 1 overwrite, Type 2 history rows with `valid_from`/`valid_to`.

---

## Part 2 — Complex interview questions by concept

---

### Section A — Joins & relational algebra (7 questions)

#### A1. Users with no trades in the last 30 days

**Question:** From `users` and `trades`, list users who had **zero** trades in the last 30 days (but may have traded earlier).

**What they’re testing:** Anti-join vs filter; time window semantics.

**Model answer:** Prefer `NOT EXISTS` (null-safe, no duplicate explosion):

```sql
SELECT u.user_id
FROM users u
WHERE NOT EXISTS (
  SELECT 1
  FROM trades t
  WHERE t.user_id = u.user_id
    AND t.trade_ts >= CURRENT_DATE - INTERVAL '30 days'
);
```

Alternative: aggregate per user in a CTE, `LEFT JOIN` users, `HAVING MAX(trade_ts) < cutoff OR MAX IS NULL` — but distinguish “never traded” vs “inactive 30d.”

**Traps:** `LEFT JOIN trades ON … AND trade_ts >= …` then `WHERE t.trade_id IS NULL` — correct for anti-join; `NOT IN (SELECT user_id …)` breaks if subquery has NULL `user_id`. Inner join + `COUNT = 0` after wrong join drops users incorrectly.

---

#### A2. Order revenue with optional refund (one row per order)

**Question:** `orders` and `refunds` (0–1 refund per order). Report `order_id`, `gross`, `refund_amount`, `net` without duplicating orders.

**What they’re testing:** One-to-many join inflation; aggregation before join.

**Model answer:** Pre-aggregate refunds:

```sql
SELECT o.order_id, o.amount AS gross,
       COALESCE(r.refund_amount, 0) AS refund_amount,
       o.amount - COALESCE(r.refund_amount, 0) AS net
FROM orders o
LEFT JOIN (
  SELECT order_id, SUM(amount) AS refund_amount
  FROM refunds
  GROUP BY order_id
) r ON r.order_id = o.order_id;
```

**Traps:** `LEFT JOIN refunds` without `GROUP BY` → multiple rows per order; `SUM(o.amount)` doubles gross.

---

#### A3. Relational algebra equivalence

**Question:** Is `SELECT DISTINCT a.id FROM a JOIN b ON …` always equivalent to `SELECT a.id FROM a WHERE EXISTS (SELECT 1 FROM b WHERE …)`?

**What they’re testing:** Semi-join vs inner join + distinct.

**Model answer:** Equivalent **if** the join condition is many-to-one from `a` to `b` (each `a` row matches at most one `b` row) or you only need existence. If one `a` matches many `b`, inner join duplicates `a.id` before DISTINCT — still equivalent to EXISTS for **presence**, but DISTINCT hides join multiplicity cost. For counting `a` rows with a match, use `EXISTS` or `COUNT(DISTINCT a.id)`.

**Traps:** Saying they’re always identical in **performance** or **plan**; using `COUNT(*)` after bad join.

---

#### A4. Full outer join reconciliation

**Question:** Compare `ledger_internal` and `ledger_external` by `txn_id`. Show matched, internal-only, external-only with amounts.

**What they’re testing:** FULL OUTER JOIN; reconciliation framing.

**Model answer:**

```sql
SELECT
  COALESCE(i.txn_id, e.txn_id) AS txn_id,
  i.amount AS internal_amt,
  e.amount AS external_amt,
  CASE
    WHEN i.txn_id IS NULL THEN 'external_only'
    WHEN e.txn_id IS NULL THEN 'internal_only'
    WHEN i.amount = e.amount THEN 'matched'
    ELSE 'amount_mismatch'
  END AS status
FROM ledger_internal i
FULL OUTER JOIN ledger_external e ON e.txn_id = i.txn_id;
```

**Traps:** `LEFT JOIN` only → miss external-only; comparing floats without tolerance; duplicate `txn_id` on either side (fix grain first).

---

#### A5. Crypto: attributing first deposit channel to later trades

**Question:** `users`, `deposits` (first deposit per user has `channel`), `trades`. Attribute each user’s **lifetime fee_usd** to first-deposit channel.

**What they’re testing:** Join at user grain; “first event” subquery.

**Model answer:**

```sql
WITH first_dep AS (
  SELECT user_id, channel
  FROM (
    SELECT user_id, channel,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY deposit_ts) AS rn
    FROM deposits
    WHERE status = 'completed'
  ) x
  WHERE rn = 1
),
user_fees AS (
  SELECT user_id, SUM(fee_usd) AS total_fees
  FROM trades
  GROUP BY user_id
)
SELECT fd.channel, SUM(uf.total_fees) AS fees_by_channel
FROM first_dep fd
JOIN user_fees uf ON uf.user_id = fd.user_id
GROUP BY fd.channel;
```

**Traps:** Joining every deposit to every trade; using `MIN(deposit_ts)` without tying channel to that row.

---

#### A6. Gaming: session overlaps with purchases

**Question:** `sessions(user_id, start_time, end_time)` and `purchases(user_id, purchase_ts)`. Count purchases that occurred **during** an active session.

**What they’re testing:** Range join / inequality join (non-equi).

**Model answer:**

```sql
SELECT COUNT(*) AS purchases_in_session
FROM purchases p
WHERE EXISTS (
  SELECT 1
  FROM sessions s
  WHERE s.user_id = p.user_id
    AND p.purchase_ts >= s.start_time
    AND p.purchase_ts <  s.end_time
);
```

**Traps:** Equi-join only on `user_id` → Cartesian within user; `BETWEEN` with inclusive end double-counting at boundaries.

---

#### A7. When CROSS JOIN is correct

**Question:** Build a calendar of every `product_id` × every `date` in a range, including days with zero sales.

**What they’re testing:** Spine / scaffolding with CROSS JOIN.

**Model answer:** `dates` CTE × `products`, then `LEFT JOIN` sales aggregated at product-day grain. CROSS JOIN is intentional to create complete grid; filter dates in `dates`, not after cross join explosion without need.

**Traps:** Calling CROSS JOIN always wrong; missing LEFT JOIN to sales → only days with sales remain.

---

### Section B — Aggregations & grain (7 questions)

#### B1. Average order value vs average line item price

**Question:** Same `orders` table: “AOV” vs “average item price” — same metric?

**What they’re testing:** Grain of denominator.

**Model answer:** AOV = `SUM(order_total) / COUNT(DISTINCT order_id)` at order grain. Average line price = `SUM(line_amount) / SUM(qty)` at line grain. Weighted vs unweighted averages — a user with one $100 order and ten $10 orders has AOV $55 but different interpretations if you average orders vs lines.

**Traps:** `AVG(order_total)` when orders table is at line grain without grouping by order first.

---

#### B2. DAU from events — distinct users or sessions?

**Question:** Define DAU for a crypto exchange from `events`.

**What they’re testing:** Metric definition before SQL.

**Model answer:** State definition: e.g. “distinct `user_id` with at least one `trade_executed` event UTC day.” SQL: `COUNT(DISTINCT user_id)` grouped by `DATE_TRUNC('day', event_ts)`. Clarify logged-out traffic, bots, test accounts, multiple devices (still one user). WAU/MAU use rolling windows — not sum of daily DAUs.

**Traps:** `COUNT(*)`; counting sessions as users; summing daily DAU for monthly “MAU.”

---

#### B3. HAVING without GROUP BY

**Question:** Can `HAVING COUNT(*) > 1` appear without `GROUP BY`?

**What they’re testing:** Whole-table aggregate filter.

**Model answer:** Yes — one implicit group (entire table). Equivalent to filtering in outer query on scalar subquery. Prefer clarity: `WITH cte AS (…) SELECT * FROM cte WHERE cnt > 1`.

**Traps:** Confusing `WHERE` (row filter) with `HAVING` (group filter).

---

#### B4. Rollup with NULL subtotals

**Question:** Explain `GROUP BY ROLLUP (country, product)` behavior.

**What they’re testing:** `GROUPING SETS` / rollup NULL meaning.

**Model answer:** Produces subtotals: (country, product), (country), grand total. NULL in `product` may mean “subtotal for country” not “unknown product” — use `GROUPING(country), GROUPING(product)` in engines that support it to distinguish.

**Traps:** Treating rollup NULL as missing data in joins.

---

#### B5. Gaming: GGR (gross gaming revenue)

**Question:** `gaming_txns(txn_type, amount)` with types `bet`, `win`, `bonus`. Define GGR in SQL.

**What they’re testing:** Business metric = set of txn types at correct sign.

**Model answer:** Typically GGR = stakes − wins (bonuses excluded or netted per policy). Example:

```sql
SELECT SUM(CASE WHEN txn_type = 'bet' THEN amount
              WHEN txn_type = 'win' THEN -amount
              ELSE 0 END) AS ggr
FROM gaming_txns
WHERE txn_type IN ('bet', 'win');
```

State policy on cancelled bets, free spins, and bonus wallet vs cash.

**Traps:** `SUM(amount)` without sign; including bonus as revenue.

---

#### B6. Maker share at daily grain

**Question:** `% maker volume` by day when one user has both maker and taker fills.

**What they’re testing:** Ratio of sums, not average of ratios.

**Model answer:** `SUM(CASE WHEN is_maker THEN notional END) / SUM(notional)` per day — **not** `AVG(CASE WHEN is_maker THEN 1 ELSE 0 END)` per trade weighted wrong at user level unless defined that way.

**Traps:** Averaging daily percentages without volume weighting for monthly rollup.

---

#### B7. COUNT DISTINCT approximate at scale

**Question:** When is `APPROX_COUNT_DISTINCT` acceptable in a BA metric?

**What they’re testing:** OLAP tradeoffs; stakeholder communication.

**Model answer:** Large-scale exploratory dashboards (unique devices, unique addresses) where ±1–2% error is acceptable and SLA matters. Not for financial reconciliation or regulatory counts — use exact `COUNT(DISTINCT)` or pre-aggregated marts.

**Traps:** Approximate for revenue or fee totals; hiding error bounds from stakeholders.

---

### Section C — Subqueries, CTEs, correlation (6 questions)

#### C1. Correlated vs uncorrelated subquery

**Question:** Get each user’s **latest** trade row (all columns).

**What they’re testing:** Window vs correlated subquery.

**Model answer:** Prefer window:

```sql
SELECT * FROM (
  SELECT t.*, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY trade_ts DESC) AS rn
  FROM trades t
) x WHERE rn = 1;
```

Correlated: `WHERE trade_ts = (SELECT MAX(trade_ts) FROM trades t2 WHERE t2.user_id = t.user_id)` — ties need `ROW_NUMBER` or `DISTINCT ON`.

**Traps:** `MAX(trade_ts)` join without handling duplicate timestamps; non-correlated subquery returning multiple rows.

---

#### C2. CTE readability and optimization

**Question:** Are CTEs always “optimization fences”?

**What they’re testing:** Engine behavior (Postgres 12+ inlining vs materialization).

**Model answer:** Depends on engine/version. In interviews: CTEs clarify **logic** and **grain**; mention `MATERIALIZED` hint where supported if reuse is expensive. Don’t assume CTE always hurts or helps.

**Traps:** Religious “never use CTE”; nesting 10 levels without commenting grain.

---

#### C3. IN vs EXISTS

**Question:** Find users who traded symbol `BTC-PERP`.

**What they’re testing:** Semi-join choice.

**Model answer:** `EXISTS (SELECT 1 FROM trades t WHERE t.user_id = u.user_id AND t.symbol = 'BTC-PERP')` — stops at first hit, null-safe. `IN` works if subquery is null-free on key.

**Traps:** `NOT IN` with NULLs in subquery → unknown → empty result.

---

#### C4. Lateral join pattern

**Question:** Top 3 trades per user (Postgres).

**What they’re testing:** `LATERAL` / `APPLY` mental model.

**Model answer:** `FROM users u, LATERAL (SELECT … FROM trades t WHERE t.user_id = u.user_id ORDER BY trade_ts DESC LIMIT 3) top3` — per-user subquery executed with outer row context. Equivalent to window filter.

**Traps:** `LIMIT 3` without `PARTITION BY` user in wrong place.

---

#### C5. Crypto: running cumulative deposits vs withdrawals

**Question:** Per user, running balance from `ledger_entries` (signed amounts).

**What they’re testing:** Ordered cumulative sum — usually window, not correlated.

**Model answer:** `SUM(amount) OVER (PARTITION BY user_id ORDER BY entry_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`.

**Traps:** Correlated subquery O(n²); wrong window frame (entire partition vs running).

---

#### C6. Recursive CTE use case

**Question:** When would a BA use a recursive CTE in SQL?

**What they’re testing:** Graph/hierarchy traversal.

**Model answer:** Org hierarchy rollups, referral trees (with depth cap), campaign attribution chains — e.g. sum volume under a referral subtree. Always specify cycle protection and max depth for production.

**Traps:** Using recursion for simple date spines (use generator table instead).

---

### Section D — Window functions (7 questions)

#### D1. ROW_NUMBER vs RANK vs DENSE_RANK

**Question:** Rank users by weekly volume — award “top 10” slots with ties.

**What they’re testing:** Tie behavior.

**Model answer:** `RANK` → 1,2,2,4; `DENSE_RANK` → 1,2,2,3; `ROW_NUMBER` → arbitrary tie-break needs extra `ORDER BY`. Top 10 by `RANK` may return >10 rows if ties at 10.

**Traps:** `ROW_NUMBER` without tie-break column; `LIMIT 10` after `RANK` without subquery filter `rank <= 10`.

---

#### D2. Frame: ROWS vs RANGE

**Question:** 7-day **moving average** of daily revenue — which frame?

**What they’re testing:** Physical rows vs logical value range.

**Model answer:** For calendar days with gaps, use `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` only if every day exists; else generate spine or use `RANGE INTERVAL '6 days' PRECEDING` (engine-specific). State assumption.

**Traps:** `RANGE` with duplicates on `ORDER BY` column; averaging already-aggregated daily rows with wrong frame.

---

#### D3. LAG for period-over-period

**Question:** MoM revenue growth %.

**What they’re testing:** `LAG` null handling; divide by zero.

**Model answer:**

```sql
WITH m AS (
  SELECT DATE_TRUNC('month', d) AS month, SUM(revenue) AS rev
  FROM daily_revenue GROUP BY 1
)
SELECT month, rev,
       (rev - LAG(rev) OVER (ORDER BY month)) / NULLIF(LAG(rev) OVER (ORDER BY month), 0) AS mom_growth
FROM m;
```

**Traps:** Sorting months as strings; `LAG` without `ORDER BY`; infinity on zero prior month.

---

#### D4. FIRST_VALUE vs MIN in window

**Question:** Get each trade’s **session start** for same user/session_id.

**What they’re testing:** Window vs join.

**Model answer:** `FIRST_VALUE(start_time) OVER (PARTITION BY session_id ORDER BY event_ts)` or join to `sessions` on key — prefer join if session dimension is trusted source of truth.

**Traps:** `MIN(start_time)` over partition that spans multiple sessions.

---

#### D5. NTILE for deciles

**Question:** Split traders into deciles by 30d volume for tier analysis.

**What they’re testing:** `NTILE(10)` distribution.

**Model answer:** Aggregate to user grain first, then `NTILE(10) OVER (ORDER BY volume_30d)`. Ties can skew bucket sizes slightly depending on engine.

**Traps:** `NTILE` on trade-level rows; not excluding wash/test accounts.

---

#### D6. Filtering on window results

**Question:** “Second trade ever” per user.

**What they’re testing:** Subquery filter on window.

**Model answer:**

```sql
SELECT user_id, trade_ts, notional
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY trade_ts) AS rn
  FROM trades
) t
WHERE rn = 2;
```

**Traps:** `WHERE ROW_NUMBER() …` in same query level (invalid in standard SQL).

---

#### D7. Gaming: sessionization with gaps

**Question:** Events stream → sessions with 30-minute gap rule.

**What they’re testing:** `LAG` + conditional new session flag + running sum of flags.

**Model answer:** `is_new = CASE WHEN event_ts - LAG(event_ts) OVER (PARTITION BY user_id ORDER BY event_ts) > INTERVAL '30 min' THEN 1 ELSE 0 END`; `session_id = SUM(is_new) OVER (PARTITION BY user_id ORDER BY event_ts ROWS UNBOUNDED PRECEDING)`.

**Traps:** Global `session_id`; ignoring cross-platform same user.

---

### Section E — NULLs & duplicates (5 questions)

#### E1. NULL in UNIQUE constraint

**Question:** Can two rows share `email = NULL` in a UNIQUE column?

**What they’re testing:** SQL NULL uniqueness (Postgres: multiple NULLs allowed in UNIQUE).

**Model answer:** In PostgreSQL, UNIQUE treats NULLs as distinct — duplicates allowed. Use `UNIQUE NULLS NOT DISTINCT` (PG15+) or partial unique index `WHERE email IS NOT NULL` for business rule “one unknown email max.”

**Traps:** Assuming NULL = NULL in uniqueness; using `COALESCE(email,'')` creating fake collisions.

---

#### E2. Duplicate detection

**Question:** Find `order_id` appearing more than once in `order_staging`.

**What they’re testing:** `HAVING COUNT(*) > 1`.

**Model answer:** `SELECT order_id, COUNT(*) FROM order_staging GROUP BY order_id HAVING COUNT(*) > 1`.

**Traps:** `SELECT DISTINCT order_id` — hides duplicates; deleting without keeping survivor rule.

---

#### E3. COALESCE vs IFNULL semantics

**Question:** `COALESCE(a, b, 0)` when `a = 0` and `b = 5`?

**What they’re testing:** COALESCE only skips NULL, not zero.

**Model answer:** Returns `0`. If business wants “first positive,” need `CASE` logic — common in fee waiver flags.

**Traps:** Using COALESCE to treat 0 as missing.

---

#### E4. DISTINCT ON (Postgres)

**Question:** Latest KYC status per user from event log.

**What they’re testing:** Postgres-specific dedup.

**Model answer:** `SELECT DISTINCT ON (user_id) user_id, status, updated_at FROM kyc_events ORDER BY user_id, updated_at DESC` — portable pattern is `ROW_NUMBER`.

**Traps:** Wrong `ORDER BY` — keeps arbitrary row per user.

---

#### E5. Crypto: wallet address normalization

**Question:** Duplicate users due to case-sensitive `0xABC` vs `0xabc`.

**What they’re testing:** Data quality before join.

**Model answer:** `LOWER(address)` in join key; document checksum validation off-SQL. Dedupe with `ROW_NUMBER` over normalized key keeping earliest `user_id`.

**Traps:** Case-sensitive join inflates user counts; deleting accounts without merge policy.

---

### Section F — Performance & indexes (6 questions)

#### F1. Why did this query slow down after a deploy?

**Question:** `WHERE DATE(trade_ts) = '2025-09-01'` on 10B-row table.

**What they’re testing:** Sargability.

**Model answer:** Function on column prevents index use on `trade_ts`. Rewrite: `trade_ts >= '2025-09-01' AND trade_ts < '2025-09-02'`.

**Traps:** Adding index on `DATE(trade_ts)` without fixing queries.

---

#### F2. Selectivity and join order

**Question:** Filter 1% of trades by `symbol`, join to large `users` — what matters?

**What they’re testing:** Predicate pushdown; filter early.

**Model answer:** Reduce fact rows first; ensure join keys indexed; stats up to date. Explain conceptually — optimizer usually pushes filters, but views and OR conditions can block it.

**Traps:** `SELECT *` wide rows; joining before filter in nested views.

---

#### F3. Clustering / partitioning by date

**Question:** Warehouse table partitioned by `event_date`. Query filters `user_id = X` only.

**What they’re testing:** Partition pruning miss.

**Model answer:** Full scan across partitions unless secondary index/cluster on `user_id` or separate mart keyed by user. BA recommends query patterns or mart design aligned with access path.

**Traps:** Assuming partition always speeds up every query.

---

#### F4. DISTINCT vs GROUP BY for dedup

**Question:** Performance difference `SELECT DISTINCT user_id` vs `GROUP BY user_id`?

**What they’re testing:** Often same plan; intent clarity.

**Model answer:** Optimizer may dedupe identically. Use `GROUP BY` when aggregating other columns; `DISTINCT` for projection dedup.

**Traps:** `DISTINCT` after join without fixing grain — hides bug.

---

#### F5. Materialized view for dashboards

**Question:** When should analytics team materialize?

**What they’re testing:** Pre-aggregation tradeoff.

**Model answer:** Heavy queries on stable grain (daily KPIs) with acceptable staleness (refresh hourly). Document refresh SLA and source of truth.

**Traps:** Materializing every ad-hoc; stale MV without monitoring.

---

#### F6. Explaining EXPLAIN to a PM

**Question:** You ran EXPLAIN — seq scan on large table. One sentence for PM?

**What they’re testing:** Communication.

**Model answer:** “The database read the whole table instead of using an index shortcut — like scanning every page of a book instead of the index — so the query was slow; we can fix filters or pre-aggregate for the dashboard.”

**Traps:** Blaming “the database” without actionable metric/grain fix.

---

### Section G — Transactions & consistency (5 questions)

#### G1. Double spend in reporting

**Question:** ETL loads same `trade_id` twice. Metric impact?

**What they’re testing:** Idempotency; primary keys.

**Model answer:** Volume and fees double unless deduped. Fix: `MERGE`/`INSERT … ON CONFLICT DO NOTHING`, primary key on `trade_id`, reconciliation job comparing counts to source.

**Traps:** `DELETE` then insert without transaction; soft duplicates with different surrogate keys.

---

#### G2. Read committed anomaly in dashboard

**Question:** User sees balance flicker during transfer.

**What they’re testing:** Non-repeatable read / timing.

**Model answer:** Two queries in one report at different times — not same transaction snapshot. Use snapshot isolation for consistent read or single query with joins.

**Traps:** Expecting warehouse snapshot to match real-time ledger to the cent.

---

#### G3. Isolation level pick for batch job

**Question:** Nightly aggregate job vs intraday OLTP — locking concern?

**What they’re testing:** Long-running transactions on OLTP.

**Model answer:** Run aggregates against replica or warehouse snapshot; avoid `SELECT SUM` holding locks on hot tables. Serializable on OLTP only when necessary.

**Traps:** Running heavy BI on primary without replica.

---

#### G4. eventual consistency in crypto deposits

**Question:** User “deposited” but trade fails — how define funded user?

**What they’re testing:** State machine; status column.

**Model answer:** Metric uses `status = 'confirmed'` and `confirmations >= N` per policy; SQL filters explicit states — not `amount > 0` alone.

**Traps:** Counting pending deposits in activation rate.

---

#### G5. Optimistic locking

**Question:** `UPDATE account SET balance = balance - 100 WHERE user_id = ? AND version = ?` — why?

**What they’re testing:** Concurrency control concept.

**Model answer:** Prevents lost update when two withdrawals race; if `version` mismatch, retry. BA defines audit rules; engineering implements.

**Traps:** `balance = 500` absolute update without version check.

---

### Section H — Data modeling for analytics (5 questions)

#### H1. Fact table grain choice

**Question:** One row per trade fill vs one row per order?

**What they’re testing:** Dimensional modeling.

**Model answer:** Fills for execution analytics (fees, slippage); orders for funnel/conversion. Often both facts with conformed `user_id`, `product_id`. Don’t mix grains in one fact without role-playing clarity.

**Traps:** Storing daily aggregates only in fact — loses drill-down.

---

#### H2. Junk dimension

**Question:** Many low-cardinality flags on trade fact — pattern?

**What they’re testing:** Junk dimension / degenerate dimensions.

**Model answer:** Combine boolean flags into one junk dimension key or leave as degenerate columns if small. Reduces wide fact explosion.

**Traps:** Normalizing each flag to separate dim with only 2 rows each — overkill.

---

#### H3. Bridge table

**Question:** User belongs to multiple segments — how to model for SQL?

**What they’re testing:** Many-to-many.

**Model answer:** `user_segment_bridge(user_id, segment_id, valid_from, valid_to)` — join through bridge; watch fan-out when aggregating revenue (allocate or dedupe user revenue).

**Traps:** `segment_id` CSV column on user — breaks filters and SCD.

---

#### H4. Conformed dimensions

**Question:** What does “conformed date dimension” mean?

**What they’re testing:** Cross-fact consistency.

**Model answer:** Single `dim_date` used by all facts — fiscal week, holidays consistent. Metrics across marts comparable.

**Traps:** Each team builds own date table with different fiscal calendar.

---

#### H5. SCD Type 2 query

**Question:** Attribute trade to user’s **country at trade time** when country changes.

**What they’re testing:** Type 2 join predicate.

**Model answer:**

```sql
SELECT t.trade_id, d.country
FROM trades t
JOIN dim_user d
  ON d.user_id = t.user_id
 AND t.trade_ts >= d.valid_from
 AND t.trade_ts <  COALESCE(d.valid_to, '9999-12-31');
```

**Traps:** Join on `user_id` only → current country only; `BETWEEN` off-by-one on `valid_to`.

---

### Section I — Business scenarios (cohort, funnel, SCD) (8 questions)

#### I1. Cohort retention (week 0 = signup week)

**Question:** Weekly cohort retention through week 8 (activity = placed trade).

**What they’re testing:** Cohort grain; activity join.

**Model answer:** Cohort key = `DATE_TRUNC('week', signup_ts)`. For each user, `weeks_since = DATEDIFF(week, cohort_week, activity_week)`. Retention = active users in week k / cohort size. Use spine of weeks 0..8 left join aggregates.

**Traps:** Calendar week vs rolling 7d; denominators including users who signed up mid-week inconsistently.

---

#### I2. Funnel conversion with time window

**Question:** Signup → KYC → first trade within 7 days of signup.

**What they’re testing:** Sequential conditions; timestamps.

**Model answer:** Per user: `signup_ts`, `MIN(kyc_approved_ts)`, `MIN(trade_ts WHERE trade_ts >= signup_ts)`. Conversion flags with `<= signup_ts + 7 days`. Report `%` at each step on same denominator (signed up) or step-to-step — **state which**.

**Traps:** `COUNT(DISTINCT)` mixed grains; trades before KYC if policy requires KYC first.

---

#### I3. A/B experiment — intent-to-treat

**Question:** `variant` assigned but some never log in. Analyze conversion.

**What they’re testing:** ITT vs per-protocol.

**Model answer:** ITT: group by assigned `variant`, denominator all assigned. Per-protocol: subset logged-in — biased. SQL ITT:

```sql
SELECT variant,
       COUNT(*) AS assigned,
       COUNT(*) FILTER (WHERE converted) AS conversions,
       AVG(converted::int) AS conv_rate
FROM ab_users
GROUP BY variant;
```

**Traps:** Only analyzing users with events; peeking daily without correction (mention as stats issue).

---

#### I4. Funding rate impact (crypto)

**Question:** Compare PnL for users heavily long perp before positive funding events.

**What they’re testing:** Event study framing; SQL feature windows.

**Model answer:** Define exposure: OI or net position before `funding_ts`; bucket users; compare `SUM(realized_pnl)` in window after vs control — state confounders (market beta). SQL: join positions snapshot to funding calendar, aggregate per user per event.

**Traps:** Confusing funding **payment** with **direction** of rate; lookahead bias using post-funding position.

---

#### I5. Liquidation cascade metric

**Question:** Count liquidation events and notional in a 1-hour spike.

**What they’re testing:** Event definition; time bucketing.

**Model answer:** `WHERE event_type = 'liquidation'` grain one row per liquidation; sum `notional_liquidated` by `DATE_TRUNC('hour', ts)`. Compare to 30d same-hour baseline (window or join).

**Traps:** Counting orders not liquidations; double-count partial liquidations.

---

#### I6. Gaming: first-time depositor conversion

**Question:** FTD rate by campaign in first 14 days.

**What they’re testing:** Attribution window; first deposit definition.

**Model answer:** Join user to marketing touch with attribution rule (last click before signup or first touch); FTD = `MIN(deposit_ts WHERE amount >= min_deposit)` within 14d of install. Rate = FTD users / installs per campaign.

**Traps:** Crediting campaign after deposit; including organic as campaign NULL mishandled.

---

#### I7. Churn definition SQL

**Question:** Trader “churned” if no trade in 30 days — snapshot logic.

**What they’re testing:** As-of date parameterization.

**Model answer:** For each `as_of_date`, `last_trade_ts < as_of_date - 30 days` and was active before (had trade in prior 90d). Parameterize `as_of_date` — not `CURRENT_DATE` hardcoded in mart without documentation.

**Traps:** Calling never-active users churned; ignoring reactivation.

---

#### I8. SCD Type 1 vs 2 business choice

**Question:** User fixes typo in country — dim update strategy?

**What they’re testing:** SCD tradeoff.

**Model answer:** Type 1 if only reporting current geo; Type 2 if historical revenue must stay in old country for audit. SQL for Type 2: close old row `valid_to = now()`, insert new row.

**Traps:** Type 2 for every typo → dimension bloat without policy.

---

## Part 3 — Top 15 “must know” rapid-fire

1. **Logical SQL order:** FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY.  
2. **INNER vs LEFT:** LEFT keeps unmatched left rows; use for “optional enrichment” and anti-join patterns with NULL check.  
3. **Grain first:** Write one-row definition before metrics.  
4. **NULL:** `NOT IN` + NULL in subquery → empty; prefer `NOT EXISTS`.  
5. **`COUNT(*)` vs `COUNT(col)`:** null handling differs.  
6. **Join inflation:** Aggregate to grain before joining one-to-many.  
7. **`WHERE` vs `HAVING`:** row filter vs group filter.  
8. **Window:** filter with `WHERE rn = 1` in outer query, not same level.  
9. **RANK ties:** top-N may exceed N rows.  
10. **Sargable dates:** range on timestamp, not `DATE(col)`.  
11. **OLTP vs OLAP:** don’t run dashboard scans on primary without plan.  
12. **Fact vs dim:** facts = measures at grain; dims = context; conformed keys.  
13. **SCD2 join:** `valid_from` / `valid_to` on trade timestamp.  
14. **ITT experiments:** analyze all assigned users.  
15. **Reconciliation:** FULL OUTER JOIN + status column; fix grain duplicates first.

---

## How to use this doc

1. Read **Part 1** once; whiteboard execution order and JOIN Venn diagrams from memory.  
2. For each section in **Part 2**, answer aloud without SQL, then add SQL — target 5–8 minutes per hard question in Delta / Lead BA loops.  
3. Cross-train fintech (**A5, B5, B6, C5, E5, G4, I4, I5**) and gaming (**A6, B5, D7, I6**) scenarios with your Flutter/Sportsbet stories.  
4. Drill syntax and repetition on **[sql-100-questions-with-answers.md](./sql-100-questions-with-answers.md)** (100 Q&A with worked SQL).

---

*End of guide — 56 concept questions + 15 rapid-fire.*
