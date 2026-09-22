# Role Requirements — Interview Prep Guide

**Prepared for:** Sonaal Topno  
**Target:** Senior Business Consultant / Analytics Consultant (data-heavy, sports & gaming adjacent)  
**Use this week:** Read one section per day; rehearse **60-second pitch** + **Top 10 stories** out loud; drill SQL from linked guides.

**Related prep in Context (same `docs/` folder):**

- [sql-interview-questions-senior-bc.md](./sql-interview-questions-senior-bc.md)
- [sql-100-questions-with-answers.md](./sql-100-questions-with-answers.md)

---

## 60-second pitch

> I'm Sonaal Topno, a Senior Business Consultant with 10+ years turning data into P&L outcomes—currently at **Flutter Entertainment**, deployed to **Sportsbet Melbourne** for marketing and insights, after three years driving RMG analytics at **Junglee Games India**.
>
> I define KPIs that executives trust, validate changes with **A/B tests**, and ship recommendations—not just dashboards. At Junglee I cut new-user churn **21%**, lifted **NGR 4.2%** through money-movement experiments, and deployed **84%-accuracy** fraud detection. At Sportsbet I lead campaign analytics, **Power BI** reporting, and faster delivery using **Databricks SQL** and AI-assisted tooling.
>
> I'm strongest where **SQL, experimentation, and gaming economics** meet stakeholder decisions: what to measure, how to test it, and what to do next in a fast, regulated consumer business.

*Delivery tip:* Pause after the three Junglee numbers; end with “happy to walk through one experiment end-to-end.”

---

## Top 10 stories (map to requirements)

| # | Story (headline) | Primary requirement | Proof points to memorize |
|---|------------------|---------------------|---------------------------|
| 1 | **Rummy.com money-movement A/B test** | A/B testing, KPIs | Hypothesis → design → guardrails → NGR +4.2%, ARPU +2.1%, rev/deposit +12pp |
| 2 | **Churn model rollout** | KPIs, Python/ML, proactive | New-user churn −21%, existing −12%; segmentation, deployment to CRM/campaigns |
| 3 | **Free-to-cash re-engagement** | KPIs, marketing, gaming | ~6% revenue lift; dormant users, personalized journeys |
| 4 | **XGBoost fraud detection** | SQL/ETL, gaming, analytics | 84% accuracy; high-risk flags; regulated RMG context |
| 5 | **Sportsbet campaign & insights** | BI, communication, fast pace | Power BI, ad-hoc for marketing/commercial; Flutter group mobility |
| 6 | **Cursor + MCP internal apps** | Self-driven, Python/SQL | CRM list automation, Databricks SQL MCP, faster repeatable reporting |
| 7 | **Ipsos 30% marketing cost reduction** | Segmentation, KPIs | Predictive targeting, Naive Bayes/KNN, team leadership |
| 8 | **Ipsos workflow automation (+40% efficiency)** | ETL-ish pipelines, proactive | Recommendation automation; KPI dashboards in R/Python |
| 9 | **MadCloud GTM & 1M+ downloads** | Dynamic environment, strategy | 45% Google Ads revenue growth; 0→1, unit economics |
| 10 | **KPI definition workshop (synthetic but true to role)** | OKRs, communication | “One metric, one owner, one SQL source of truth”—tie to NGR vs GGR debates |

*Practice:* Each story in **STAR** under 90 seconds; keep a “so what for the business” line ready.

---

## 1. KPIs and OKRs

### What interviewers test

- Whether you **define metrics** before optimizing them (numerator/denominator, cohort, timezone).
- If you connect **team OKRs** to measurable inputs and guardrails—not vanity metrics.
- How you **cascade** executive goals to analyst work and resolve metric conflicts.

### Key concepts

- **KPI:** Ongoing health metric (e.g., NGR, churn rate, handle); often lagging or leading variants.
- **OKR:** Objective (qualitative) + Key Results (measurable, time-bound); KRs should be outcomes, not task lists.
- **North Star vs guardrails:** Primary success metric vs metrics you must not harm (e.g., lift NGR without spike in problem gambling signals).
- **SMART KRs:** Specific, measurable, achievable, relevant, time-bound.
- **Metric tree:** Revenue → active players × ARPU × margin; decompose before blaming one lever.

### Likely questions + answer frameworks

**Q1. How do you define a good KPI for a product squad?**  
*Framework:* (1) Tie to P&L or retention outcome (2) Single owner and data source (3) Leading/lagging pair (4) Document edge cases (refunds, bonuses, geo).  
*Sonaal tie-in:* NGR vs GGR vs bonus cost at Junglee; rev/deposit ratio as operational KPI during money-movement tests.

**Q2. Tell me about a time a dashboard metric disagreed with finance.**  
*STAR:* Situation = two definitions of “revenue.” Task = align stakeholders. Action = workshop on event vs cash, SQL reconciliation doc. Result = one certified metric in Power BI / warehouse.

**Q3. How would you set OKRs for a retention team in gaming?**  
*Structured:* Objective = improve sustainable player value. KRs = churn −X%, reactivation Y%, NGR +Z% with responsible-gaming guardrails. Initiatives = experiments, CRM, not “build dashboard.”

**Q4. What’s the difference between OKRs and KPIs on your team?**  
*Talking points:* KPIs = heartbeat; OKRs = quarterly bets that move KPIs; review weekly on inputs (experiment velocity, model coverage).

**Q5. Describe a KPI you improved and how you proved causality.**  
*Use Story #1 or #2:* Metric moved after experiment or model-driven intervention; mention holdout or A/B where possible.

### Tie to Sonaal’s experience

- Junglee: **NGR +4.2%**, **ARPU +2.1%**, churn −21%/−12%, **free-to-cash** ~6% revenue, fraud precision as risk KPI.
- Sportsbet: campaign performance, handle/margin language; APAC marketing KPIs.
- Ipsos: cost-per-acquisition style KPIs, segmentation lift.

### Red flags to avoid

- Treating **OKRs as a task backlog** (“KR: build 5 reports”).
- Quoting **model accuracy** without business KPI movement.
- Ignoring **bonus/promo accounting** when discussing revenue KPIs in gaming.

---

## 2. SQL

### What interviewers test

- **Correctness** on joins, aggregation grain, and window functions in business scenarios.
- **Metric SQL:** cohort retention, funnel, A/B assignment, revenue with refunds/bonuses.
- **Communication:** explaining query logic and debugging duplicate rows.

### Key concepts

- **Grain:** one row per user-day, bet-slip, session—match the business question.
- **LEFT JOIN trap:** fan-out inflates numerators; use distinct keys or subqueries for denominators.
- **Window functions:** `ROW_NUMBER`, `LAG/LEAD`, running totals for trends and cohorts.
- **CTEs:** readable pipelines; filter contaminated A/B users before lift calc.
- **NULL handling:** `COALESCE`, `NULLIF` for safe ratios.

**Deep drill:** see **SQL guides in Context** — [sql-interview-questions-senior-bc.md](./sql-interview-questions-senior-bc.md) (scenarios + hints) and [sql-100-questions-with-answers.md](./sql-100-questions-with-answers.md) (100 Q&A with Junglee/Sportsbet/Flutter examples).

### Likely questions + answer frameworks

**Q1. Write SQL for 7-day retention after first deposit.**  
*Framework:* Define cohort (first deposit date) → activity days 1–7 → divide active by cohort size; specify timezone (IST/AEST).

**Q2. Two tables disagree on revenue—how do you investigate?**  
*Framework:* Compare grain, filters (test users, voided bets), join keys, late-arriving facts; reconcile top 10 users manually.

**Q3. Calculate A/B test conversion with contaminated users.**  
*Framework:* CTE for clean assignment → exclude cross-over → ratio with `NULLIF`; mention intent-to-treat vs per-protocol if asked.

**Q4. Rank users by LTV in last 90 days with tie-breaker.**  
*Framework:* `SUM` revenue by user → `ROW_NUMBER() OVER (ORDER BY ltv DESC, user_id)`.

**Q5. Explain why this query double-counts revenue.**  
*Framework:* Walk join diagram; fix with pre-aggregated subquery or `DISTINCT` only when key is truly unique.

### Tie to Sonaal’s experience

- PostgreSQL / BigQuery-style analytics; **Databricks SQL** at Sportsbet via MCP workflows.
- Resume outcomes (churn, NGR, fraud) all imply **repeatable SQL definitions** shared with product/marketing.

### Red flags to avoid

- **SELECT *** in production logic without stating grain.
- **Inner join** users to transactions and calling it “all users.”
- Cannot explain **one** query you wrote for an exec metric.

---

## 3. Python, BI, and data visualization

### What interviewers test

- **When** you use Python vs SQL vs BI (right tool, not resume stacking).
- **Dashboard design:** audience, refresh, drill-down, metric definitions on-page.
- **Light Python:** pandas for ad-hoc, sklearn for baselines—not production ML engineering.

### Key concepts

- **SQL for scale; Python for flexibility:** feature engineering, prototypes, statistical tests.
- **BI layers:** staging clean tables → semantic model (Power BI) → certified dashboards.
- **Chart choice:** trend = line; composition = stacked bar with care; experiment = lift + confidence interval.
- **Plotly/Jupyter:** exploration; **Power BI/Tableau/Looker Studio:** stakeholder consumption.

### Likely questions + answer frameworks

**Q1. How do you decide between Power BI and a Jupyter notebook?**  
*Framework:* Audience, refresh cadence, self-serve need, row volume; notebooks for discovery, BI for governance.

**Q2. Describe a dashboard you built that changed a decision.**  
*STAR:* Sportsbet campaign reporting or Junglee churn segments; include who viewed it and what action followed.

**Q3. How do you prevent misleading visualizations?**  
*Talking points:* Axis baseline, consistent date ranges, label definitions, sample size on experiment charts.

**Q4. Example of Python in your workflow.**  
*Framework:* Churn feature prep, A/B analysis script, or automation—keep scope analyst-level.

**Q5. How do you document metrics in BI tools?**  
*Framework:* Tooltip + linked confluence/SQL; owner name; refresh SLA.

### Tie to Sonaal’s experience

- **Power BI** dashboards at Sportsbet; R/Python dashboards at Ipsos; **Plotly**, Jupyter, **Tableau**, Looker Studio in toolkit.
- **Cursor/MCP:** faster internal apps connecting **Databricks SQL** and ops tools (monday.com)—position as delivery acceleration, not replacing BI governance.

### Red flags to avoid

- Claiming **production ML pipelines** if you only built models and partnered with eng for deploy.
- Dashboards with **20 charts and no decision.**
- Dismissing **Excel**—senior consultants still use it for exec ad-hoc.

---

## 4. ETL data pipelines

### What interviewers test

- **Conceptual fluency:** sources → transform → warehouse → BI; where things break.
- **Data quality:** freshness, duplicates, schema drift, backfills.
- **Your role** as BC/analyst vs data engineer (specs, validation, not necessarily owning Airflow DAGs).

### Key concepts

- **ETL vs ELT:** extract/load raw, transform in warehouse (common on Snowflake/Databricks).
- **Idempotency:** reruns don’t duplicate facts.
- **SCD Type 2:** slowly changing dimensions for user attributes (segment, VIP tier).
- **Lineage & SLA:** when marketing can trust “yesterday’s NGR.”
- **Validation:** row counts, null rates, key uniqueness alerts.

### Likely questions + answer frameworks

**Q1. Walk through how event data becomes a KPI dashboard.**  
*Framework:* Ingest (Kafka/S3) → raw → cleaned facts/dims → aggregate tables → BI semantic layer → certified metric.

**Q2. Pipeline broke—numbers dropped 30% overnight. What do you do?**  
*Framework:* Check upstream job status, compare row counts by day, isolate segment (geo/product), communicate ETA and interim manual estimate if needed.

**Q3. How do you spec a new data requirement for engineering?**  
*Framework:* Grain, keys, history needs, latency, sample SQL, acceptance tests (unit counts vs legacy report).

**Q4. Experience with batch vs streaming?**  
*Honest framework:* Most gaming analytics batch daily/hourly; streaming for fraud/live ops—describe what you consumed, not what you built unless true.

**Q5. How did you validate fraud or churn model input data?**  
*Use Story #4 or #2:* Missing labels, class imbalance, feature leakage checks.

### Tie to Sonaal’s experience

- **AWS S3, Athena, Lambda**; **Snowflake, Databricks** on resume.
- Fraud and churn work **depends on clean player/account tables**—emphasize QA you ran before trusting scores.
- Ipsos automation story = **pipeline mindset** for recommendations workflow.

### Red flags to avoid

- Blaming **data eng only** when analyst spec was ambiguous.
- No concept of **grain** or **late-arriving data** (settlements, chargebacks).

---

## 5. A/B testing

### What interviewers test

- **Design:** hypothesis, unit of randomization, sample size, duration, guardrails.
- **Analysis:** intent-to-treat, contamination, multiple comparisons, practical significance.
- **Business judgment:** when **not** to test (ethical, power, seasonality).

### Key concepts

- **Unit:** user, account, geo—must match intervention.
- **Primary vs guardrail metrics:** NGR primary; churn or RG metrics as guardrails.
- **SRM / sample ratio mismatch:** assignment bug if group sizes diverge.
- **Peeking:** avoid stopping early without sequential methods.
- **DiD / geo holdouts:** when user-level randomization isn’t feasible (common in marketing).

### Likely questions + answer frameworks

**Q1. Tell me about an A/B test you ran.**  
*STAR — Story #1:* Money movement on Rummy.com; hypothesis, randomization, metrics (NGR, ARPU, rev/deposit), result, rollout.

**Q2. How long would you run a test?**  
*Framework:* Power for MDE, full business cycles (payday, weekends, major sports events), pre-register duration.

**Q3. Users saw both variants—what now?**  
*Framework:* Define analysis population; per-protocol vs ITT; prevent cross-over in product.

**Q4. Test won on clicks but lost on NGR.**  
*Framework:* Optimize for P&L metric; investigate bonus abuse or adverse selection.

**Q5. How do you explain p-value to a PM?**  
*Framework:* Evidence strength under null; pair with effect size and confidence interval; decision uses business impact.

### Tie to Sonaal’s experience

- **Flagship story:** money-movement experiment—**12pp** rev/deposit, **NGR +4.2%**, **ARPU +2.1%**.
- Sportsbet: A/B experiments in marketing context; link to SQL guide hints on contaminated users.
- Ipsos: incrementality mindset via segmentation (proxy for holdouts if needed).

### Red flags to avoid

- **Peeking** and celebrating early wins.
- **Multiple metrics** without hierarchy → false discoveries.
- Ignoring **seasonality** (Grand Final, IPL, festival deposits in India).

---

## 6. Airflow (analytics consultant level)

### What interviewers test

- **Practical familiarity:** what DAGs do, how you depend on them, how you troubleshoot delays—not authoring complex operators.
- **Orchestration vs transformation:** Airflow schedules; dbt/Spark/SQL does the work.
- **Operational empathy:** backfills, dependencies, alerting.

### Key concepts

- **DAG:** directed acyclic graph of tasks with schedule (`cron`) and dependencies.
- **Task dependencies:** upstream success before downstream runs.
- **Backfill:** reprocess historical partitions after logic fix.
- **Sensors / triggers:** wait for data landing or external file.
- **Monitoring:** SLA misses, retries, on-call handoff to data platform team.

### Likely questions + answer frameworks

**Q1. What is Airflow and how have you interacted with it?**  
*Framework:* “I don’t own core DAG authorship; I consume outputs, request new tasks, and debug when SLAs slip—check task logs, last successful run, partition date.”

**Q2. Marketing dashboard is stale—what do you check?**  
*Framework:* Airflow run history → failed task → upstream ingest → comms to stakeholders with ETA.

**Q3. When would you request a backfill?**  
*Framework:* Metric definition change, bug fix, new dimension— specify date range and validation plan.

**Q4. Difference between Airflow and dbt?**  
*Framework:* Airflow = scheduler/orchestrator; dbt = transform/test in warehouse—often chained in same DAG.

**Q5. How do you document pipeline dependencies for your team?**  
*Framework:* Simple lineage diagram: source tables → daily jobs → BI datasets you certify.

### Tie to Sonaal’s experience

- Position **Databricks + warehouse jobs** as the environment where orchestration lives; your value = **clear specs and validation** when Junglee/Sportsbet KPIs refresh.
- MCP/automation = **adjacent** (workflow automation), not a substitute for Airflow knowledge.

### Red flags to avoid

- Pretending **deep Airflow development** without examples.
- Not knowing **who owns** pipeline on-call in your last role.

---

## 7. Relational databases and data warehouse

### What interviewers test

- **Modeling intuition:** facts vs dimensions, star schema, grain.
- **Warehouse patterns:** partitioning, clustering, cost vs performance.
- **Analyst workflow:** writing efficient SQL at warehouse scale.

### Key concepts

- **Star schema:** fact table (events) + dimension tables (user, product, date).
- **Normalization (OLTP)** vs **denormalization (OLAP)** for read-heavy analytics.
- **Partitioning:** by date for prune; clustering on high-cardinality filter columns.
- **Slowly changing dimensions:** track history of user status/VIP.
- **Data warehouse vs lakehouse:** structured metrics layer on raw events (Databricks/Snowflake pattern).

### Likely questions + answer frameworks

**Q1. Design a schema for betting handle and NGR reporting.**  
*Framework:* Fact_bets (handle, payout, bonus cost, timestamps) + dim_user + dim_product + dim_date; define grain (bet vs slip).

**Q2. Why is my warehouse query expensive?**  
*Framework:* Full table scan, no partition filter, join explosion, SELECT wide columns—fix filters and pre-aggregate.

**Q3. Explain primary vs foreign keys in your analytics context.**  
*Framework:* Integrity in source OLTP; in warehouse, **surrogate keys** and careful joins to avoid fan-out.

**Q4. How do you handle late-arriving transactions?**  
*Framework:* Partition reprocessing, adjusted snapshots, restatement policy for finance.

**Q5. Experience with Snowflake vs Databricks?**  
*Honest framework:* Both = cloud warehouse/lakehouse patterns; cite what you queried and how semantic layers connected.

### Tie to Sonaal’s experience

- **Snowflake, Databricks, AWS Athena** on resume; Sportsbet **Databricks SQL** integrations.
- RMG/betting = **high-volume transactional data** → natural examples for facts/dimensions and regulated reporting.

### Red flags to avoid

- Confusing **database normalization** with **analytics best practice** (wide fact tables are OK).
- No awareness of **timezone** in date dimensions (critical for APAC).

---

## 8. Sports and gaming domain

### What interviewers test

- **Commercial literacy:** how operators make money and what levers exist.
- **Regulated context:** KYC, responsible gaming, market differences (AU vs IN).
- **Passion plus precision:** fan language backed by metrics.

### Key concepts

- **Sports betting:** **handle** (total stakes), **margin** (operator hold), **GGR/NGR** after bonuses/taxes; **odds** pricing and liability.
- **RMG (Junglee):** **deposit → play → withdraw** funnels; **rake**; **free-to-cash** conversion; **ARPU**, **LTV**, **churn**.
- **Flutter group:** global portfolio; **Sportsbet (AU)** vs **Junglee (IN RMG)**—different regulation, similar analytics muscle.
- **Responsible gaming (RG):** guardrail metrics, self-exclusion, spend limits—not optional in interviews.
- **Promotions/bonuses:** always clarify **net** metrics.

### Likely questions + answer frameworks

**Q1. How does a sportsbook make money?**  
*Framework:* Margin on handle, parlay mix, bonus efficiency, customer lifetime; balance acquisition vs sharp/bonus abuse.

**Q2. Key metrics you tracked at Junglee?**  
*Framework:* NGR, ARPU, churn, rev/deposit, fraud rate, free-to-cash conversion—tie to Stories #1–4.

**Q3. What’s different about analytics in AU vs India gaming?**  
*Framework:* Regulation, payment rails, sports calendar vs RMG card games; adapt KPIs and compliance.

**Q4. How would you measure a major sporting event campaign?**  
*Framework:* Incrementality (holdout or DiD), handle/new depositor mix, ROI, RG guardrails; **Sportsbet** deployment angle.

**Q5. Explain NGR vs GGR in one minute.**  
*Framework:* GGR = player losses before costs; NGR subtracts bonuses, fees, adjustments—executives usually care about **NGR**.

### Tie to Sonaal’s experience

- **Flutter Entertainment Group**; **Sportsbet Melbourne** marketing & insights; **Junglee** RMG outcomes (NGR, churn, fraud, A/B on money movement).
- Use **odds/handle/margin** language at Sportsbet; **rummy/deposit/churn** at Junglee—show breadth inside one group.

### Red flags to avoid

- **Glorifying problem gambling** or ignoring RG.
- **Confusing handle with revenue.**
- Domain buzzwords **without metric definitions.**

---

## 9. Proactive, self-driven, analytical skills

### What interviewers test

- **Ownership** beyond ticket queue: you spot problems and propose solutions.
- **Structured thinking:** hypothesis → data → recommendation.
- **Learning velocity:** AI tooling, new market (Australia), new stack.

### Key concepts

- **Consultant mindset:** clarify decision, minimum analysis, executive summary.
- **80/20 analysis:** quick SQL cut before full model.
- **Bias awareness:** confirmation bias, survivorship in gaming cohorts.
- **Self-direction:** internal apps when gap blocks team (Cursor/MCP examples).

### Likely questions + answer frameworks

**Q1. Tell me about something you did that wasn’t assigned.**  
*Use Story #6 or #8:* MCP/CRM automation or Ipsos workflow automation—impact in time saved or errors reduced.

**Q2. How do you prioritize ad-hoc requests?**  
*Framework:* Decision urgency × P&L impact × effort; negotiate scope; offer phased answer.

**Q3. Hardest analytical problem you solved.**  
*STAR:* Churn or fraud—ambiguous labels, imbalanced data, stakeholder skepticism; end with business metric.

**Q4. How do you stay current technically?**  
*Framework:* Cursor/LLM-assisted SQL, Databricks, experiment literature; **honest** learning habits.

**Q5. Describe a wrong conclusion you reached and corrected.**  
*Framework:* Show intellectual honesty; what you changed in process (validation, peer review).

### Tie to Sonaal’s experience

- **Junglee awards** (Top Rookie, Exceptional Performance, SPOT, Troubleshooter) as external validation of initiative.
- **Co-founder** background—0→1 bias.
- **IIT** quantitative foundation—brief bridge from geophysics to analytics if asked (structured problem-solving transfer).

### Red flags to avoid

- **Hero mode** (“I alone”) without cross-functional credit.
- Analysis **without recommended action.**
- Waiting for **perfect data** before informing stakeholders—note interim read instead.

---

## 10. Fast-paced, dynamic environment

### What interviewers test

- **Calm under ambiguity:** incomplete specs, shifting priorities.
- **Parallel work:** exec ask + experiment monitor + pipeline delay same day.
- **Regulated/high-stakes industry** tolerance (gaming/betting).

### Key concepts

- **Triage:** communicate trade-offs explicitly.
- **Minimum viable insight:** directional answer in hours, refined later.
- **Stakeholder sync:** short written updates beat long decks in crises.
- **Event-driven spikes:** match days, festival seasons, promo launches.

### Likely questions + answer frameworks

**Q1. Describe a week with conflicting deadlines.**  
*STAR:* Sportsbet campaign deadline + ad-hoc commercial ask—how you sequenced, delegated, or cut scope.

**Q2. How do you handle changing requirements mid-analysis?**  
*Framework:* Confirm decision still same; document scope change; time-box sunk work.

**Q3. Experience in live ops or launch windows?**  
*Framework:* MadCloud launch scale; Junglee promo periods; Sportsbet event calendars.

**Q4. How do you work across time zones (India/Australia)?**  
*Framework:* Async docs, overlap hours, clear handoffs—your Flutter mobility is proof.

**Q5. What stresses you and how do you manage it?**  
*Framework:* Honest + professional; routines (checklist, SQL templates, AI assist for speed).

### Tie to Sonaal’s experience

- **Flutter deployment** India → Melbourne; dual-market pace.
- **Startup co-founder** + **Ipsos client delivery** + **gaming promo cycles.**

### Red flags to avoid

- **Chaos romanticism** with no structure.
- **Burnout signals** or blaming org only.
- Inability to give **concrete example** of fast turnaround.

---

## 11. Communication skills

### What interviewers test

- **Executive summary first;** details on request.
- **Translating stats** to dollars and actions.
- **Cross-functional** credibility (product, marketing, legal/compliance, data eng).

### Key concepts

- **Pyramid principle:** answer → supporting points → appendix.
- **Audience map:** CMO wants ROI; PM wants feature impact; legal wants RG risk.
- **Visual + verbal:** one chart, one message.
- **Written async:** bullet status with decision needed.

### Likely questions + answer frameworks

**Q1. Tell me about presenting to a skeptical stakeholder.**  
*STAR:* Fraud or churn rollout—anticipate objections, show validation, pilot proposal.

**Q2. How do you explain a model to non-technical leaders?**  
*Framework:* Input signals → what it predicts → how we use it → what we don’t use it for; avoid algorithm name-dropping first.

**Q3. Write the first slide of a deck for experiment results.**  
*Framework:* Headline = decision (“Ship variant B in money movement”); sub = NGR lift + guardrails + next step.

**Q4. How do you say no to a request?**  
*Framework:* Acknowledge goal; offer smaller alternative or timeline; escalate trade-off to sponsor.

**Q5. Example of simplifying a complex analysis.**  
*Framework:* Metric tree or segment comparison instead of model coefficients.

### Tie to Sonaal’s experience

- **Market research at Ipsos** = client-ready narratives.
- **Senior BC title** = recommendations, not only reports.
- Practice **Sportsbet commercial/marketing** language in recent bullets.

### Red flags to avoid

- **Jargon wall** (XGBoost, MCP) without business translation.
- **Reading slides** instead of conversing.
- Overpromising **causality** from observational data.

---

## Quick reference cheat sheet (one page)

### Gaming & betting metrics

- **Handle:** total stakes; **GGR:** player losses before adjustments; **NGR:** after bonuses/promos/fees.
- **ARPU / ARPPU:** revenue per user / paying user; **LTV:** discounted lifetime value.
- **Churn:** no activity or no deposit in X days (define explicitly).
- **Free-to-cash:** free/play users converting to paying.
- **Margin:** operator win as % of handle; **Odds:** price of outcome; liability management on book.

### Experimentation

- Pre-register **primary metric** + **guardrails**; fix **duration**; check **SRM**.
- Report **effect size + CI**, not only p-value; ITT default.
- Filter **contaminated** users in SQL CTE before lift.

### SQL reminders

- Grain first; **LEFT JOIN** denominators; **`NULLIF`** for ratios; windows for cohorts.
- Timezone align **before** daily agg (IST / AEST).
- **See SQL guides in Context** for drill sets.

### Pipeline / warehouse

- Facts = events; dims = descriptors; **partition by date**.
- Pipeline debug: last run → row counts → key uniqueness → compare to legacy.
- **Airflow:** schedule + dependencies + backfill (orchestration, not transforms).

### OKR / KPI

- One **owner**, one **definition**, one **source table**.
- OKRs = quarterly outcomes; KPIs = ongoing pulse; RG = non-negotiable guardrail.

### Your proof numbers (Junglee unless noted)

- Churn **−21%** new / **−12%** existing; NGR **+4.2%**; ARPU **+2.1%**; rev/deposit **+12pp**; fraud **84%** accuracy; free-to-cash **~6%** revenue; Ipsos **−30%** marketing cost; MadCloud **1M+** downloads / **+45%** ads revenue.

### Interview day checklist

- [ ] 60-second pitch aloud ×3  
- [ ] Stories #1, #2, #4 rehearsed (STAR)  
- [ ] One SQL metric + one A/B design on whiteboard  
- [ ] Three questions for them (metric governance, experiment culture, data stack)  
- [ ] RG / compliance one-liner ready for gaming employers  

---

*Good luck this week—lead with decisions and metrics, then show the SQL that proves them.*
