-- E8b: orders and revenue per week, and the top days, under the proposed order rule (see E8a).
-- Answers: sanity check (Black Friday / Christmas peaks), Q3/Q4.
WITH p AS (
  SELECT
    user_pseudo_id,
    event_timestamp,
    PARSE_DATE('%Y%m%d', event_date)  AS order_date,
    ecommerce.transaction_id          AS tid,
    ecommerce.purchase_revenue_in_usd AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
),
orders AS (
  SELECT order_date, revenue FROM p
  WHERE tid IS NOT NULL AND tid != '(not set)'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY tid, user_pseudo_id ORDER BY event_timestamp) = 1
  UNION ALL
  SELECT order_date, revenue FROM p
  WHERE (tid IS NULL OR tid = '(not set)') AND revenue > 0
),
weekly AS (
  SELECT 'week' AS kind, DATE_TRUNC(order_date, WEEK(MONDAY)) AS period_start,
         COUNT(*) AS orders, ROUND(SUM(revenue)) AS revenue_usd
  FROM orders GROUP BY 2
),
top_days AS (
  SELECT 'top_day' AS kind, order_date AS period_start,
         COUNT(*) AS orders, ROUND(SUM(revenue)) AS revenue_usd
  FROM orders GROUP BY 2
  ORDER BY revenue_usd DESC LIMIT 5
)
SELECT * FROM weekly
UNION ALL
SELECT * FROM top_days
ORDER BY kind DESC, period_start;
