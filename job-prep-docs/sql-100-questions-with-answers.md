# 100 SQL Interview Questions with Answers

**Prepared for:** Sonaal Topno — Senior Business Consultant / Analytics Consultant
**Level:** Senior (big tech, consulting, gaming/sports betting)
**Syntax:** PostgreSQL / BigQuery compatible (dialect notes where relevant)

---

## Sample Schema Reference

```sql
-- users(user_id, name, email, country, signup_date, is_test)
-- orders(order_id, user_id, product_id, amount, order_date, refunded)
-- products(product_id, product_name, category)
-- transactions(user_id, txn_type, amount, txn_date, txn_time)
-- events(user_id, event_type, event_time, event_date, platform)
-- experiment(user_id, variant, converted, logged_in_post_assignment)
-- gaming_txns(user_id, txn_type, amount, txn_time)  -- bet, win, bonus
-- sessions(user_id, game_id, start_time, end_time)
-- games(game_id, game_name)
-- marketing(channel, spend, user_id)
```

---

## Table of Contents

- Fundamentals (10 questions)
- JOINs (12 questions)
- Aggregations (12 questions)
- CTEs (12 questions)
- Window (15 questions)
- Business (18 questions)
- Data Quality (8 questions)
- Performance (8 questions)
- Advanced (5 questions)

---


## Fundamentals

### Q1. Find all users who signed up in January 2025.
**Difficulty:** Easy | **Category:** Fundamentals

**Answer:**
```sql
SELECT user_id, signup_date FROM users WHERE signup_date >= DATE '2025-01-01' AND signup_date < DATE '2025-02-01';
```

**Explanation:** Half-open date range avoids time-of-day bugs and stays sargable.

---

### Q2. List distinct countries from users.
**Difficulty:** Easy | **Category:** Fundamentals

**Answer:**
```sql
SELECT DISTINCT country FROM users WHERE country IS NOT NULL ORDER BY country;
```

**Explanation:** DISTINCT deduplicates; NULL filter keeps reports clean.

---

### Q3. Find users with gmail.com email domain.
**Difficulty:** Medium | **Category:** Fundamentals

**Answer:**
```sql
SELECT user_id, email FROM users WHERE email LIKE '%@gmail.com';
```

**Explanation:** LIKE works in interviews; production may use SPLIT_PART(email,'@',2).

---

### Q4. Calculate DAU for the last 7 days.
**Difficulty:** Medium | **Category:** Fundamentals

**Answer:**
```sql
SELECT DATE(event_timestamp) AS day, COUNT(DISTINCT user_id) AS dau FROM events WHERE event_timestamp >= CURRENT_DATE - INTERVAL '7 days' GROUP BY 1 ORDER BY 1;
```

**Explanation:** DAU = distinct users per calendar day; clarify timezone and qualifying events.

---

### Q5. Users who deposited but never withdrew.
**Difficulty:** Medium | **Category:** Fundamentals

**Answer:**
```sql
SELECT d.user_id FROM (SELECT DISTINCT user_id FROM transactions WHERE txn_type='deposit') d LEFT JOIN (SELECT DISTINCT user_id FROM transactions WHERE txn_type='withdraw') w ON d.user_id=w.user_id WHERE w.user_id IS NULL;
```

**Explanation:** Anti-join: in deposit set, not in withdraw set.

---

### Q6. Top 10 products by revenue.
**Difficulty:** Medium | **Category:** Fundamentals

**Answer:**
```sql
SELECT product_id, SUM(amount) AS revenue FROM orders GROUP BY 1 ORDER BY revenue DESC LIMIT 10;
```

**Explanation:** Aggregate then ORDER BY + LIMIT.

---

### Q7. Average order value per country.
**Difficulty:** Medium | **Category:** Fundamentals

**Answer:**
```sql
SELECT u.country, SUM(o.amount)/NULLIF(COUNT(DISTINCT o.order_id),0) AS aov FROM orders o JOIN users u ON o.user_id=u.user_id GROUP BY u.country;
```

**Explanation:** AOV = total revenue / distinct orders.

---

### Q8. Users active on 3+ distinct days in last 30 days.
**Difficulty:** Hard | **Category:** Fundamentals

**Answer:**
```sql
SELECT user_id FROM events WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 days' GROUP BY user_id HAVING COUNT(DISTINCT DATE(event_timestamp))>=3;
```

**Explanation:** HAVING filters post-aggregation.

---

### Q9. Case-insensitive name search for 'sonaal'.
**Difficulty:** Medium | **Category:** Fundamentals

**Answer:**
```sql
SELECT user_id, name FROM users WHERE LOWER(name)='sonaal';
```

**Explanation:** LOWER() for case-insensitive match.

---

### Q10. First deposit within 7 days of signup.
**Difficulty:** Hard | **Category:** Fundamentals

**Answer:**
```sql
WITH fe AS (SELECT u.user_id, MIN(u.signup_date) AS signup, MIN(CASE WHEN t.txn_type='deposit' THEN t.txn_date END) AS first_dep FROM users u LEFT JOIN transactions t ON u.user_id=t.user_id GROUP BY u.user_id) SELECT user_id FROM fe WHERE first_dep IS NOT NULL AND first_dep <= signup + INTERVAL '7 days';
```

**Explanation:** User-grain aggregation before date comparison.

---


## JOINs

### Q11. Orders with customer names (INNER JOIN).
**Difficulty:** Easy | **Category:** JOINs

**Answer:**
```sql
SELECT o.order_id, o.amount, u.name FROM orders o INNER JOIN users u ON o.user_id=u.user_id;
```

**Explanation:** INNER JOIN keeps only matching rows.

---

### Q12. All users with order count including zeros.
**Difficulty:** Medium | **Category:** JOINs

**Answer:**
```sql
SELECT u.user_id, u.name, COUNT(o.order_id) AS orders FROM users u LEFT JOIN orders o ON u.user_id=o.user_id GROUP BY u.user_id, u.name;
```

**Explanation:** LEFT JOIN + COUNT gives zero for users without orders.

---

### Q13. Users who ordered in both 2024 and 2025.
**Difficulty:** Medium | **Category:** JOINs

**Answer:**
```sql
SELECT user_id FROM orders WHERE EXTRACT(YEAR FROM order_date) IN (2024,2025) GROUP BY user_id HAVING COUNT(DISTINCT EXTRACT(YEAR FROM order_date))=2;
```

**Explanation:** Distinct year count must equal 2.

---

### Q14. Employee-manager pairs (self-join).
**Difficulty:** Medium | **Category:** JOINs

**Answer:**
```sql
SELECT e.employee_id, e.name AS employee, m.name AS manager FROM employees e LEFT JOIN employees m ON e.manager_id=m.employee_id;
```

**Explanation:** Self-join links row to another in same table.

---

### Q15. Products never ordered.
**Difficulty:** Hard | **Category:** JOINs

**Answer:**
```sql
SELECT p.product_id, p.product_name FROM products p LEFT JOIN orders o ON p.product_id=o.product_id WHERE o.product_id IS NULL;
```

**Explanation:** LEFT JOIN + NULL filter = anti-join.

---

### Q16. Each user's latest order only.
**Difficulty:** Hard | **Category:** JOINs

**Answer:**
```sql
WITH latest AS (SELECT user_id, MAX(order_date) AS md FROM orders GROUP BY user_id) SELECT o.* FROM orders o JOIN latest l ON o.user_id=l.user_id AND o.order_date=l.md;
```

**Explanation:** Max date per user then join back.

---

### Q17. Bought product A but not B.
**Difficulty:** Medium | **Category:** JOINs

**Answer:**
```sql
SELECT DISTINCT user_id FROM orders WHERE product_id='A' AND user_id NOT IN (SELECT user_id FROM orders WHERE product_id='B' AND user_id IS NOT NULL);
```

**Explanation:** NOT IN with NULL guard, or prefer NOT EXISTS.

---

### Q18. Revenue per product category (3-table join).
**Difficulty:** Hard | **Category:** JOINs

**Answer:**
```sql
SELECT p.category, SUM(o.amount) AS revenue FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY p.category ORDER BY revenue DESC;
```

**Explanation:** Join facts to dimension, aggregate at category grain.

---

### Q19. Duplicate order_ids.
**Difficulty:** Medium | **Category:** JOINs

**Answer:**
```sql
SELECT order_id, COUNT(*) FROM orders GROUP BY order_id HAVING COUNT(*)>1;
```

**Explanation:** Standard duplicate detection.

---

### Q20. Monthly revenue 2024 vs 2025 side by side.
**Difficulty:** Hard | **Category:** JOINs

**Answer:**
```sql
WITH r24 AS (SELECT EXTRACT(MONTH FROM order_date) m, SUM(amount) r FROM orders WHERE EXTRACT(YEAR FROM order_date)=2024 GROUP BY 1), r25 AS (SELECT EXTRACT(MONTH FROM order_date) m, SUM(amount) r FROM orders WHERE EXTRACT(YEAR FROM order_date)=2025 GROUP BY 1) SELECT COALESCE(r24.m,r25.m) AS month, r24.r AS rev_2024, r25.r AS rev_2025 FROM r24 FULL OUTER JOIN r25 ON r24.m=r25.m ORDER BY 1;
```

**Explanation:** FULL OUTER JOIN retains months in only one year.

---

### Q21. Avg session length per game.
**Difficulty:** Hard | **Category:** JOINs

**Answer:**
```sql
SELECT g.game_name, AVG(EXTRACT(EPOCH FROM (s.end_time-s.start_time))/60) AS avg_min FROM sessions s JOIN games g ON s.game_id=g.game_id GROUP BY g.game_name;
```

**Explanation:** Join sessions to game metadata; compute duration before AVG.

---

### Q22. RMG: net positive deposit-withdraw days.
**Difficulty:** Hard | **Category:** JOINs

**Answer:**
```sql
WITH d AS (SELECT user_id, txn_date, SUM(CASE WHEN txn_type='deposit' THEN amount ELSE 0 END) dep, SUM(CASE WHEN txn_type='withdraw' THEN amount ELSE 0 END) wdr FROM transactions GROUP BY 1,2) SELECT * FROM d WHERE dep>wdr;
```

**Explanation:** Aggregate to user-day before comparing.

---


## Aggregations

### Q23. Monthly revenue and order count.
**Difficulty:** Easy | **Category:** Aggregations

**Answer:**
```sql
SELECT DATE_TRUNC('month',order_date) AS month, COUNT(*) orders, SUM(amount) revenue FROM orders GROUP BY 1 ORDER BY 1;
```

**Explanation:** DATE_TRUNC for monthly buckets.

---

### Q24. Countries with >1000 users.
**Difficulty:** Medium | **Category:** Aggregations

**Answer:**
```sql
SELECT country, COUNT(*) FROM users GROUP BY country HAVING COUNT(*)>1000;
```

**Explanation:** HAVING filters groups.

---

### Q25. Median order value.
**Difficulty:** Medium | **Category:** Aggregations

**Answer:**
```sql
SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) FROM orders;
```

**Explanation:** PostgreSQL percentile; BigQuery: APPROX_QUANTILES(amount,100)[OFFSET(50)].

---

### Q26. Revenue % by category.
**Difficulty:** Medium | **Category:** Aggregations

**Answer:**
```sql
SELECT category, SUM(amount) rev, 100.0*SUM(amount)/SUM(SUM(amount)) OVER() pct FROM orders o JOIN products p ON o.product_id=p.product_id GROUP BY category;
```

**Explanation:** Window sum for grand total percentage.

---

### Q27. Rolling 7-day revenue sum.
**Difficulty:** Hard | **Category:** Aggregations

**Answer:**
```sql
SELECT order_date, SUM(amount) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS roll_7d FROM daily_revenue;
```

**Explanation:** 7-row rolling frame.

---

### Q28. New vs returning orders per day.
**Difficulty:** Medium | **Category:** Aggregations

**Answer:**
```sql
SELECT DATE(order_date) day, COUNT(*) FILTER (WHERE rn=1) new_ord, COUNT(*) FILTER (WHERE rn>1) ret_ord FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date) rn FROM orders) t GROUP BY 1;
```

**Explanation:** ROW_NUMBER identifies first order.

---

### Q29. Categories with avg >2x global avg.
**Difficulty:** Hard | **Category:** Aggregations

**Answer:**
```sql
WITH g AS (SELECT AVG(amount) ga FROM orders) SELECT p.category, AVG(o.amount) ca FROM orders o JOIN products p ON o.product_id=p.product_id CROSS JOIN g HAVING AVG(o.amount)>2*MAX(g.ga) GROUP BY p.category;
```

**Explanation:** CROSS JOIN for global benchmark.

---

### Q30. Subtotals with GROUPING SETS.
**Difficulty:** Medium | **Category:** Aggregations

**Answer:**
```sql
SELECT country, city, COUNT(*) FROM users GROUP BY GROUPING SETS ((country,city),(country),());
```

**Explanation:** Multiple aggregation levels in one query.

---

### Q31. Pivot revenue by quarter.
**Difficulty:** Medium | **Category:** Aggregations

**Answer:**
```sql
SELECT EXTRACT(YEAR FROM order_date) yr, SUM(CASE WHEN EXTRACT(QUARTER FROM order_date)=1 THEN amount END) q1, SUM(CASE WHEN EXTRACT(QUARTER FROM order_date)=2 THEN amount END) q2, SUM(CASE WHEN EXTRACT(QUARTER FROM order_date)=3 THEN amount END) q3, SUM(CASE WHEN EXTRACT(QUARTER FROM order_date)=4 THEN amount END) q4 FROM orders GROUP BY 1;
```

**Explanation:** Conditional SUM pivots without PIVOT.

---

### Q32. Gaming NGR per day.
**Difficulty:** Hard | **Category:** Aggregations

**Answer:**
```sql
SELECT DATE(txn_time) day, SUM(CASE WHEN txn_type='bet' THEN amount ELSE 0 END)-SUM(CASE WHEN txn_type='win' THEN amount ELSE 0 END)-SUM(CASE WHEN txn_type='bonus' THEN amount ELSE 0 END) ngr FROM gaming_txns GROUP BY 1;
```

**Explanation:** NGR = bets - wins - bonuses.

---

### Q33. CPA by marketing channel.
**Difficulty:** Hard | **Category:** Aggregations

**Answer:**
```sql
SELECT channel, SUM(spend)/NULLIF(COUNT(DISTINCT user_id),0) cpa FROM marketing GROUP BY channel;
```

**Explanation:** Cost per distinct acquired user.

---

### Q34. A/B conversion rate by variant.
**Difficulty:** Hard | **Category:** Aggregations

**Answer:**
```sql
SELECT variant, COUNT(DISTINCT user_id) assigned, COUNT(DISTINCT CASE WHEN converted THEN user_id END) conv, 100.0*COUNT(DISTINCT CASE WHEN converted THEN user_id END)/NULLIF(COUNT(DISTINCT user_id),0) rate FROM experiment GROUP BY variant;
```

**Explanation:** Distinct users prevent fan-out.

---


## CTEs

### Q35. Users with above-average order count.
**Difficulty:** Easy | **Category:** CTEs

**Answer:**
```sql
WITH uc AS (SELECT user_id, COUNT(*) cnt FROM orders GROUP BY user_id) SELECT user_id FROM uc WHERE cnt > (SELECT AVG(cnt) FROM uc);
```

**Explanation:** CTE computes per-user counts; subquery for average.

---

### Q36. Second highest salary.
**Difficulty:** Medium | **Category:** CTEs

**Answer:**
```sql
WITH ranked AS (SELECT salary, DENSE_RANK() OVER (ORDER BY salary DESC) rnk FROM employees) SELECT DISTINCT salary FROM ranked WHERE rnk=2;
```

**Explanation:** DENSE_RANK handles ties for Nth highest.

---

### Q37. Recursive CTE: generate dates for last 30 days.
**Difficulty:** Medium | **Category:** CTEs

**Answer:**
```sql
WITH RECURSIVE dates AS (SELECT CURRENT_DATE AS d UNION ALL SELECT d-1 FROM dates WHERE d > CURRENT_DATE-30) SELECT d FROM dates;
```

**Explanation:** Recursive CTE builds date spine.

---

### Q38. YoY revenue growth per month.
**Difficulty:** Hard | **Category:** CTEs

**Answer:**
```sql
WITH m AS (SELECT DATE_TRUNC('month',order_date) mo, SUM(amount) rev FROM orders GROUP BY 1) SELECT mo, rev, LAG(rev,12) OVER (ORDER BY mo) prev_yr, (rev-LAG(rev,12) OVER (ORDER BY mo))/NULLIF(LAG(rev,12) OVER (ORDER BY mo),0) yoy FROM m;
```

**Explanation:** LAG 12 months for YoY.

---

### Q39. Correlated subquery: users with max order per country.
**Difficulty:** Medium | **Category:** CTEs

**Answer:**
```sql
SELECT u.user_id, u.country, o.amount FROM users u JOIN orders o ON u.user_id=o.user_id WHERE o.amount = (SELECT MAX(amount) FROM orders o2 JOIN users u2 ON o2.user_id=u2.user_id WHERE u2.country=u.country);
```

**Explanation:** Correlated subquery compares to country max.

---

### Q40. Chained CTEs: signup → first deposit → days to convert.
**Difficulty:** Hard | **Category:** CTEs

**Answer:**
```sql
WITH fd AS (SELECT user_id, MIN(txn_date) first_dep FROM transactions WHERE txn_type='deposit' GROUP BY 1) SELECT u.user_id, fd.first_dep - u.signup_date AS days_to_convert FROM users u JOIN fd ON u.user_id=fd.user_id;
```

**Explanation:** Multi-step CTE pipeline for funnel metric.

---

### Q41. EXISTS: users with at least one refund.
**Difficulty:** Medium | **Category:** CTEs

**Answer:**
```sql
SELECT user_id, name FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.user_id AND o.refunded=TRUE);
```

**Explanation:** EXISTS is efficient for presence checks.

---

### Q42. Top 3 products per region.
**Difficulty:** Hard | **Category:** CTEs

**Answer:**
```sql
WITH ranked AS (SELECT region, product_id, SUM(amount) rev, ROW_NUMBER() OVER (PARTITION BY region ORDER BY SUM(amount) DESC) rn FROM orders GROUP BY region, product_id) SELECT * FROM ranked WHERE rn<=3;
```

**Explanation:** ROW_NUMBER per partition for top-N.

---

### Q43. Scalar subquery in SELECT: each order as % of user total.
**Difficulty:** Medium | **Category:** CTEs

**Answer:**
```sql
SELECT order_id, amount, 100.0*amount/(SELECT SUM(amount) FROM orders o2 WHERE o2.user_id=o.user_id) pct FROM orders o;
```

**Explanation:** Scalar subquery for per-user share.

---

### Q44. Materialized logic: 30-day churned users.
**Difficulty:** Hard | **Category:** CTEs

**Answer:**
```sql
WITH last_active AS (SELECT user_id, MAX(event_date) last_dt FROM events GROUP BY 1) SELECT user_id FROM last_active WHERE last_dt < CURRENT_DATE - INTERVAL '30 days';
```

**Explanation:** Churn = no activity in 30 days.

---

### Q45. UNION: combine deposits and withdrawals into one ledger.
**Difficulty:** Medium | **Category:** CTEs

**Answer:**
```sql
SELECT user_id, txn_date, 'deposit' type, amount FROM transactions WHERE txn_type='deposit' UNION ALL SELECT user_id, txn_date, 'withdraw', -amount FROM transactions WHERE txn_type='withdraw';
```

**Explanation:** UNION ALL preserves all rows; sign convention for withdrawals.

---

### Q46. Fraud: users with >5 deposits in 1 hour.
**Difficulty:** Hard | **Category:** CTEs

**Answer:**
```sql
WITH hourly AS (SELECT user_id, DATE_TRUNC('hour',txn_time) hr, COUNT(*) cnt FROM transactions WHERE txn_type='deposit' GROUP BY 1,2) SELECT user_id, hr, cnt FROM hourly WHERE cnt>5;
```

**Explanation:** Aggregate to user-hour grain for velocity check.

---


## Window

### Q47. Running total of daily revenue.
**Difficulty:** Easy | **Category:** Window

**Answer:**
```sql
SELECT order_date, amount, SUM(amount) OVER (ORDER BY order_date) running_total FROM daily_revenue;
```

**Explanation:** Cumulative SUM with ORDER BY in OVER.

---

### Q48. Rank employees by salary per department.
**Difficulty:** Medium | **Category:** Window

**Answer:**
```sql
SELECT employee_id, dept, salary, RANK() OVER (PARTITION BY dept ORDER BY salary DESC) rnk FROM employees;
```

**Explanation:** PARTITION BY resets ranking per department.

---

### Q49. LAG: compare each day's revenue to previous day.
**Difficulty:** Medium | **Category:** Window

**Answer:**
```sql
SELECT order_date, amount, LAG(amount) OVER (ORDER BY order_date) prev, amount-LAG(amount) OVER (ORDER BY order_date) diff FROM daily_revenue;
```

**Explanation:** LAG accesses previous row.

---

### Q50. LEAD: days until next purchase per user.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
SELECT user_id, order_date, LEAD(order_date) OVER (PARTITION BY user_id ORDER BY order_date) next_order, LEAD(order_date) OVER (PARTITION BY user_id ORDER BY order_date)-order_date days_between FROM orders;
```

**Explanation:** LEAD for forward-looking gap.

---

### Q51. First and last value in partition.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
SELECT user_id, order_date, amount, FIRST_VALUE(amount) OVER (PARTITION BY user_id ORDER BY order_date) first_amt, LAST_VALUE(amount) OVER (PARTITION BY user_id ORDER BY order_date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) last_amt FROM orders;
```

**Explanation:** LAST_VALUE needs explicit frame bounds.

---

### Q52. NTILE: divide users into revenue quartiles.
**Difficulty:** Medium | **Category:** Window

**Answer:**
```sql
SELECT user_id, total_rev, NTILE(4) OVER (ORDER BY total_rev) quartile FROM (SELECT user_id, SUM(amount) total_rev FROM orders GROUP BY user_id) t;
```

**Explanation:** NTILE for equal-sized buckets.

---

### Q53. Gaps and islands: consecutive login days.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
WITH flagged AS (SELECT user_id, login_date, login_date - (ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date))::int grp FROM logins) SELECT user_id, MIN(login_date) streak_start, MAX(login_date) streak_end, COUNT(*) streak_len FROM flagged GROUP BY user_id, grp HAVING COUNT(*)>=3;
```

**Explanation:** Date minus row number groups consecutive dates.

---

### Q54. Sessionization: 30-minute gap.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
WITH diff AS (SELECT user_id, event_time, CASE WHEN event_time - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) > INTERVAL '30 min' OR LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) IS NULL THEN 1 ELSE 0 END new_sess FROM events) SELECT user_id, SUM(new_sess) OVER (PARTITION BY user_id ORDER BY event_time) session_id, event_time FROM diff;
```

**Explanation:** Flag new session when gap >30 min; cumulative sum assigns session IDs.

---

### Q55. Moving average 7-day.
**Difficulty:** Medium | **Category:** Window

**Answer:**
```sql
SELECT day, dau, AVG(dau) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) ma7 FROM daily_dau;
```

**Explanation:** AVG window for smoothing.

---

### Q56. Percent rank of product revenue.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
SELECT product_id, revenue, PERCENT_RANK() OVER (ORDER BY revenue) pct_rank FROM (SELECT product_id, SUM(amount) revenue FROM orders GROUP BY product_id) t;
```

**Explanation:** PERCENT_RANK for relative standing.

---

### Q57. Deduplicate: keep latest row per user.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY updated_at DESC) rn FROM user_profiles) SELECT * FROM ranked WHERE rn=1;
```

**Explanation:** ROW_NUMBER=1 is standard dedup pattern.

---

### Q58. Difference from partition average.
**Difficulty:** Medium | **Category:** Window

**Answer:**
```sql
SELECT user_id, amount, amount - AVG(amount) OVER (PARTITION BY user_id) diff_from_avg FROM orders;
```

**Explanation:** Compare each row to partition mean.

---

### Q59. Cumulative distinct users per day.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
SELECT day, COUNT(DISTINCT user_id) OVER (ORDER BY day) cumulative_users FROM (SELECT DISTINCT DATE(event_time) day, user_id FROM events) t;
```

**Explanation:** Distinct in window counts unique users to date.

---

### Q60. RMG: running deposit total per user.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
SELECT user_id, txn_time, amount, SUM(amount) OVER (PARTITION BY user_id ORDER BY txn_time) running_deposits FROM transactions WHERE txn_type='deposit';
```

**Explanation:** Running sum partitioned by user.

---

### Q61. Sportsbet: weekly active users trend.
**Difficulty:** Hard | **Category:** Window

**Answer:**
```sql
SELECT week, COUNT(DISTINCT user_id) wau, LAG(COUNT(DISTINCT user_id)) OVER (ORDER BY week) prev_wau FROM (SELECT DATE_TRUNC('week',event_time) week, user_id FROM events) t GROUP BY week;
```

**Explanation:** WAU with week-over-week via LAG on aggregate.

---


## Business

### Q62. Cohort retention: D7 retention rate.
**Difficulty:** Medium | **Category:** Business

**Answer:**
```sql
WITH cohorts AS (SELECT user_id, DATE_TRUNC('month',signup_date) cohort FROM users), activity AS (SELECT user_id, DATE(event_time) active_day FROM events) SELECT c.cohort, COUNT(DISTINCT c.user_id) cohort_size, COUNT(DISTINCT CASE WHEN a.active_day BETWEEN c.cohort AND c.cohort+INTERVAL '7 days' THEN c.user_id END)*100.0/COUNT(DISTINCT c.user_id) d7_ret FROM cohorts c LEFT JOIN activity a ON c.user_id=a.user_id GROUP BY c.cohort;
```

**Explanation:** Join cohort to activity; conditional distinct for retained users.

---

### Q63. Full retention matrix (week 0-4).
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
WITH c AS (SELECT user_id, DATE_TRUNC('week',signup_date) cohort FROM users), a AS (SELECT user_id, DATE_TRUNC('week',event_time) active_week FROM events) SELECT c.cohort, EXTRACT(WEEK FROM a.active_week - c.cohort) week_n, COUNT(DISTINCT c.user_id) users FROM c JOIN a ON c.user_id=a.user_id GROUP BY 1,2 ORDER BY 1,2;
```

**Explanation:** Retention heatmap data without PIVOT.

---

### Q64. Funnel: signup → deposit → first bet conversion.
**Difficulty:** Medium | **Category:** Business

**Answer:**
```sql
WITH s AS (SELECT COUNT(DISTINCT user_id) n FROM users), d AS (SELECT COUNT(DISTINCT user_id) n FROM transactions WHERE txn_type='deposit'), b AS (SELECT COUNT(DISTINCT user_id) n FROM transactions WHERE txn_type='bet') SELECT s.n signups, d.n depositors, 100.0*d.n/s.n dep_rate, b.n bettors, 100.0*b.n/d.n bet_rate FROM s,d,b;
```

**Explanation:** Step conversion with distinct user counts.

---

### Q65. A/B test: statistical summary by variant.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT variant, COUNT(DISTINCT user_id) n, AVG(converted::int) conv_rate, STDDEV(converted::int) std FROM experiment GROUP BY variant;
```

**Explanation:** Report n, rate, and variance for significance discussion.

---

### Q66. Churn: users inactive 30+ days after last activity.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT user_id FROM (SELECT user_id, MAX(event_date) last_active FROM events GROUP BY user_id) t WHERE last_active < CURRENT_DATE - INTERVAL '30 days';
```

**Explanation:** Simple churn definition; state assumptions.

---

### Q67. Reactivation: churned users who returned.
**Difficulty:** Medium | **Category:** Business

**Answer:**
```sql
WITH churned AS (SELECT user_id, MAX(event_date) last_a FROM events GROUP BY user_id HAVING MAX(event_date)<CURRENT_DATE-INTERVAL '30 days') SELECT c.user_id FROM churned c JOIN events e ON c.user_id=e.user_id WHERE e.event_date > c.last_a + INTERVAL '30 days';
```

**Explanation:** Users with activity after churn window.

---

### Q68. LTV: cumulative revenue per user at 30/60/90 days.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
WITH user_rev AS (SELECT u.user_id, u.signup_date, o.order_date, o.amount FROM users u JOIN orders o ON u.user_id=o.user_id) SELECT user_id, SUM(CASE WHEN order_date<=signup_date+30 THEN amount END) ltv_30, SUM(CASE WHEN order_date<=signup_date+60 THEN amount END) ltv_60, SUM(CASE WHEN order_date<=signup_date+90 THEN amount END) ltv_90 FROM user_rev GROUP BY user_id;
```

**Explanation:** Conditional sum for period LTV.

---

### Q69. Free-to-cash conversion rate.
**Difficulty:** Medium | **Category:** Business

**Answer:**
```sql
SELECT 100.0*COUNT(DISTINCT CASE WHEN first_cash IS NOT NULL THEN user_id END)/COUNT(DISTINCT user_id) f2c_rate FROM (SELECT u.user_id, MIN(CASE WHEN t.txn_type='deposit' THEN t.txn_date END) first_cash FROM users u LEFT JOIN transactions t ON u.user_id=t.user_id GROUP BY u.user_id) t;
```

**Explanation:** Core RMG metric from your Junglee experience.

---

### Q70. ARPU by month.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT DATE_TRUNC('month',e.event_time) month, SUM(revenue)/COUNT(DISTINCT e.user_id) arpu FROM events e GROUP BY 1;
```

**Explanation:** ARPU = total revenue / distinct active users.

---

### Q71. NGR lift from A/B test on money movement.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT variant, SUM(ngr) total_ngr, SUM(ngr)/COUNT(DISTINCT user_id) ngr_per_user FROM experiment_results GROUP BY variant;
```

**Explanation:** Tie to your +4.2% NGR A/B testing bullet.

---

### Q72. Marketing attribution: last-touch channel per conversion.
**Difficulty:** Medium | **Category:** Business

**Answer:**
```sql
WITH last_touch AS (SELECT user_id, channel, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY touch_time DESC) rn FROM marketing_touches WHERE converted) SELECT channel, COUNT(*) conversions FROM last_touch WHERE rn=1 GROUP BY channel;
```

**Explanation:** Last-touch attribution model.

---

### Q73. Cohort revenue curve.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT cohort_month, months_since, SUM(amount) revenue FROM (SELECT DATE_TRUNC('month',u.signup_date) cohort_month, DATE_TRUNC('month',o.order_date) order_month, o.amount FROM users u JOIN orders o ON u.user_id=o.user_id) t CROSS JOIN LATERAL (SELECT EXTRACT(MONTH FROM AGE(order_month, cohort_month)) months_since) m GROUP BY 1,2 ORDER BY 1,2;
```

**Explanation:** Revenue by months since signup.

---

### Q74. Fraud: flag accounts with deposit-withdraw ratio <0.1 within 24h.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
WITH pairs AS (SELECT user_id, SUM(CASE WHEN txn_type='deposit' THEN amount END) dep, SUM(CASE WHEN txn_type='withdraw' THEN amount END) wdr FROM transactions WHERE txn_time >= CURRENT_DATE-1 GROUP BY user_id) SELECT user_id FROM pairs WHERE wdr/NULLIF(dep,0)<0.1 AND dep>1000;
```

**Explanation:** Money laundering pattern detection.

---

### Q75. Segment users by RFM score.
**Difficulty:** Medium | **Category:** Business

**Answer:**
```sql
WITH rfm AS (SELECT user_id, CURRENT_DATE-MAX(order_date) recency, COUNT(*) frequency, SUM(amount) monetary FROM orders GROUP BY user_id) SELECT user_id, NTILE(3) OVER (ORDER BY recency DESC) r, NTILE(3) OVER (ORDER BY frequency) f, NTILE(3) OVER (ORDER BY monetary) m FROM rfm;
```

**Explanation:** RFM segmentation with NTILE.

---

### Q76. Experiment contamination: users in multiple variants.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT user_id, COUNT(DISTINCT variant) variants FROM experiment GROUP BY user_id HAVING COUNT(DISTINCT variant)>1;
```

**Explanation:** Data quality check before A/B analysis.

---

### Q77. Day-1/Day-7/Day-30 retention for signup cohorts.
**Difficulty:** Medium | **Category:** Business

**Answer:**
```sql
SELECT signup_week, COUNT(DISTINCT user_id) signups, COUNT(DISTINCT CASE WHEN days_since_signup=1 THEN user_id END) d1, COUNT(DISTINCT CASE WHEN days_since_signup=7 THEN user_id END) d7, COUNT(DISTINCT CASE WHEN days_since_signup=30 THEN user_id END) d30 FROM (SELECT u.user_id, DATE_TRUNC('week',u.signup_date) signup_week, DATE(e.event_time)-u.signup_date days_since_signup FROM users u JOIN events e ON u.user_id=e.user_id) t GROUP BY signup_week;
```

**Explanation:** Classic retention table for gaming.

---

### Q78. Revenue-to-deposit ratio improvement.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT month, SUM(revenue)/NULLIF(SUM(deposits),0) rev_to_dep FROM monthly_metrics GROUP BY month;
```

**Explanation:** Your +12pp revenue-to-deposit metric.

---

### Q79. Power BI equivalent: top campaigns by ROI in SQL.
**Difficulty:** Hard | **Category:** Business

**Answer:**
```sql
SELECT campaign, (SUM(revenue)-SUM(spend))/NULLIF(SUM(spend),0) roi FROM campaigns GROUP BY campaign ORDER BY roi DESC LIMIT 10;
```

**Explanation:** ROI for marketing analytics at Sportsbet.

---


## Data Quality

### Q80. NULL-safe average.
**Difficulty:** Medium | **Category:** Data Quality

**Answer:**
```sql
SELECT AVG(COALESCE(revenue,0)) FROM orders;
```

**Explanation:** COALESCE only if NULL means zero; otherwise AVG ignores NULLs.

---

### Q81. NOT IN trap with NULLs.
**Difficulty:** Medium | **Category:** Data Quality

**Answer:**
```sql
SELECT user_id FROM users WHERE NOT EXISTS (SELECT 1 FROM blocked b WHERE b.user_id=users.user_id);
```

**Explanation:** NOT EXISTS is NULL-safe; NOT IN is not.

---

### Q82. Join fan-out diagnosis.
**Difficulty:** Medium | **Category:** Data Quality

**Answer:**
```sql
SELECT COUNT(*) raw, COUNT(DISTINCT o.order_id) distinct_orders FROM orders o JOIN promotions p ON o.order_id=p.order_id;
```

**Explanation:** Compare COUNT vs COUNT DISTINCT to detect fan-out.

---

### Q83. Safe division.
**Difficulty:** Easy | **Category:** Data Quality

**Answer:**
```sql
SELECT converted*100.0/NULLIF(total,0) rate FROM metrics;
```

**Explanation:** NULLIF prevents divide-by-zero; BigQuery: SAFE_DIVIDE.

---

### Q84. Timezone: DAU in IST.
**Difficulty:** Medium | **Category:** Data Quality

**Answer:**
```sql
SELECT DATE(event_time AT TIME ZONE 'Asia/Kolkata') day, COUNT(DISTINCT user_id) dau FROM events GROUP BY 1;
```

**Explanation:** AT TIME ZONE for India ops.

---

### Q85. Exclude test accounts.
**Difficulty:** Medium | **Category:** Data Quality

**Answer:**
```sql
SELECT * FROM users WHERE COALESCE(is_test,FALSE)=FALSE;
```

**Explanation:** COALESCE handles legacy NULL test flags.

---

### Q86. Late-arriving events: idempotent daily snapshot.
**Difficulty:** Hard | **Category:** Data Quality

**Answer:**
```sql
INSERT INTO daily_dau (day, dau, computed_at) SELECT DATE(event_time), COUNT(DISTINCT user_id), NOW() FROM events WHERE DATE(event_time)=CURRENT_DATE-1 GROUP BY 1 ON CONFLICT (day) DO UPDATE SET dau=EXCLUDED.dau, computed_at=NOW();
```

**Explanation:** Upsert for reproducible daily metrics.

---

### Q87. Intent-to-treat vs per-protocol conversion.
**Difficulty:** Hard | **Category:** Data Quality

**Answer:**
```sql
SELECT variant, AVG(converted::int) itt_rate FROM experiment GROUP BY variant; -- ITT
SELECT variant, AVG(converted::int) pp_rate FROM experiment WHERE logged_in_post_assignment GROUP BY variant; -- Per-protocol
```

**Explanation:** Two denominators; state which you'd report to leadership.

---


## Performance

### Q88. Rewrite non-sargable date filter.
**Difficulty:** Medium | **Category:** Performance

**Answer:**
```sql
-- Slow: WHERE DATE(created_at)='2025-03-01'
SELECT * FROM events WHERE created_at >= '2025-03-01' AND created_at < '2025-03-02';
```

**Explanation:** Range on raw column allows index use.

---

### Q89. Explain when to index user_id.
**Difficulty:** Medium | **Category:** Performance

**Answer:**
```sql
CREATE INDEX idx_events_user ON events(user_id);
```

**Explanation:** Index high-cardinality join/filter columns.

---

### Q90. Partition pruning on BigQuery.
**Difficulty:** Hard | **Category:** Performance

**Answer:**
```sql
SELECT * FROM events WHERE _PARTITIONDATE BETWEEN '2025-01-01' AND '2025-01-31';
```

**Explanation:** Filter partition column to scan less data.

---

### Q91. Avoid SELECT * in production.
**Difficulty:** Medium | **Category:** Performance

**Answer:**
```sql
SELECT user_id, event_type, event_time FROM events WHERE user_id=12345;
```

**Explanation:** Select only needed columns; reduces I/O.

---

### Q92. Pre-aggregate with materialized view.
**Difficulty:** Hard | **Category:** Performance

**Answer:**
```sql
CREATE MATERIALIZED VIEW daily_dau AS SELECT DATE(event_time) day, COUNT(DISTINCT user_id) dau FROM events GROUP BY 1;
```

**Explanation:** Materialized views for repeated expensive aggregations.

---

### Q93. JOIN order: filter before join.
**Difficulty:** Medium | **Category:** Performance

**Answer:**
```sql
SELECT u.user_id FROM users u JOIN orders o ON u.user_id=o.user_id WHERE o.order_date >= CURRENT_DATE-7;
```

**Explanation:** Filter driving table early to reduce join size.

---

### Q94. APPROX_COUNT_DISTINCT for large scale.
**Difficulty:** Hard | **Category:** Performance

**Answer:**
```sql
SELECT APPROX_COUNT_DISTINCT(user_id) FROM events;
```

**Explanation:** HyperLogLog approximation for billion-row tables.

---

### Q95. Clustering recommendation.
**Difficulty:** Medium | **Category:** Performance

**Answer:**
```sql
-- Cluster events on (user_id, event_date) for user-level time-range queries
```

**Explanation:** Mention clustering/partitioning in interview even if DDL varies by warehouse.

---


## Advanced

### Q96. Design metric: define and SQL for 'engaged depositor'.
**Difficulty:** Hard | **Category:** Advanced

**Answer:**
```sql
-- Definition: deposited AND played 3+ days in last 7
WITH deps AS (SELECT DISTINCT user_id FROM transactions WHERE txn_type='deposit' AND txn_date>=CURRENT_DATE-7), active AS (SELECT user_id FROM events WHERE event_date>=CURRENT_DATE-7 GROUP BY user_id HAVING COUNT(DISTINCT event_date)>=3) SELECT COUNT(*) FROM deps d JOIN active a ON d.user_id=a.user_id;
```

**Explanation:** Senior signal: define metric before writing SQL.

---

### Q97. Multi-step: diagnose 20% DAU drop.
**Difficulty:** Hard | **Category:** Advanced

**Answer:**
```sql
-- Step 1: segment by platform
SELECT platform, COUNT(DISTINCT user_id) dau FROM events WHERE event_date=CURRENT_DATE-1 GROUP BY platform;
-- Step 2: compare to prior week same day
-- Step 3: check new user vs returning split
```

**Explanation:** Show structured debugging approach, not just one query.

---

### Q98. Build a churn prediction feature table.
**Difficulty:** Hard | **Category:** Advanced

**Answer:**
```sql
SELECT user_id, COUNT(DISTINCT event_date) active_days_30d, SUM(amount) spend_30d, CURRENT_DATE-MAX(event_date) days_since_last FROM events WHERE event_date>=CURRENT_DATE-30 GROUP BY user_id;
```

**Explanation:** Feature engineering SQL for ML — ties to your churn models.

---

### Q99. Cross-brand Flutter analysis: users on both Junglee and Sportsbet.
**Difficulty:** Hard | **Category:** Advanced

**Answer:**
```sql
SELECT j.user_id FROM junglee_users j INNER JOIN sportsbet_users s ON j.email_hash=s.email_hash;
```

**Explanation:** Group-level identity resolution scenario.

---

### Q100. Executive summary query: weekly KPI dashboard.
**Difficulty:** Hard | **Category:** Advanced

**Answer:**
```sql
SELECT DATE_TRUNC('week',CURRENT_DATE) week, (SELECT COUNT(DISTINCT user_id) FROM events WHERE event_date>=CURRENT_DATE-7) wau, (SELECT SUM(amount) FROM transactions WHERE txn_type='deposit' AND txn_date>=CURRENT_DATE-7) deposits, (SELECT SUM(ngr) FROM daily_ngr WHERE day>=CURRENT_DATE-7) ngr;
```

**Explanation:** Single-row KPI summary — what you'd put in a Power BI exec dashboard.

---
