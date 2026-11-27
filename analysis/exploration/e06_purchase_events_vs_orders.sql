-- E6: purchase events vs unique orders (transaction_id).
-- Answers: Q4 (how to count purchases; what the duplicates look like).
WITH p AS (
  SELECT
    event_date,
    event_timestamp,
    user_pseudo_id,
    ecommerce.transaction_id          AS tid,
    ecommerce.purchase_revenue_in_usd AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
),
totals AS (
  SELECT
    COUNT(*)                          AS purchase_events,
    COUNTIF(tid IS NULL)              AS tid_null,
    COUNTIF(tid = '(not set)')        AS tid_not_set,
    COUNT(DISTINCT tid)               AS distinct_tids,
    ROUND(SUM(revenue))               AS revenue_all_events,
    ROUND(SUM(IF(tid = '(not set)', revenue, 0))) AS revenue_not_set
  FROM p
),
dups AS (
  SELECT
    tid,
    COUNT(*)                          AS events,
    COUNT(DISTINCT user_pseudo_id)    AS users,
    COUNT(DISTINCT event_date)        AS days,
    COUNT(DISTINCT revenue)           AS revenue_values,
    (MAX(event_timestamp) - MIN(event_timestamp)) / 1e6 AS span_seconds,
    SUM(revenue) - MAX(revenue)       AS extra_revenue
  FROM p
  WHERE tid IS NOT NULL AND tid != '(not set)'
  GROUP BY tid
  HAVING COUNT(*) > 1
)
SELECT
  t.*,
  (SELECT COUNT(*) FROM dups)                         AS duplicated_tids,
  (SELECT SUM(events) FROM dups)                      AS events_of_duplicated_tids,
  (SELECT COUNTIF(users = 1) FROM dups)               AS dup_same_user,
  (SELECT COUNTIF(days = 1) FROM dups)                AS dup_same_day,
  (SELECT COUNTIF(revenue_values = 1) FROM dups)      AS dup_same_revenue,
  (SELECT APPROX_QUANTILES(span_seconds, 4) FROM dups) AS dup_span_seconds_quartiles,
  (SELECT ROUND(SUM(extra_revenue)) FROM dups)        AS dup_extra_revenue
FROM totals t;
