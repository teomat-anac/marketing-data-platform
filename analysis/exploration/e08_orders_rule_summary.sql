-- E8a: unique orders and revenue under the proposed order rule.
--   Real transaction_id    -> one order per (transaction_id, user_pseudo_id), first event kept.
--                             The user is part of the key because obfuscated 6-digit IDs collide (E6c).
--   Missing transaction_id -> one order per event with revenue > 0;
--                             events with zero revenue are not orders (they have no items revenue, E6b).
-- Answers: Q3/Q4.
WITH p AS (
  SELECT
    user_pseudo_id,
    event_timestamp,
    PARSE_DATE('%Y%m%d', event_date)  AS order_date,
    ecommerce.transaction_id          AS tid,
    ecommerce.purchase_revenue_in_usd AS revenue,
    ecommerce.tax_value_in_usd        AS tax
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
),
real_orders AS (
  SELECT * FROM p
  WHERE tid IS NOT NULL AND tid != '(not set)'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY tid, user_pseudo_id ORDER BY event_timestamp) = 1
),
missing_id_orders AS (
  SELECT * FROM p
  WHERE (tid IS NULL OR tid = '(not set)') AND revenue > 0
)
SELECT
  (SELECT COUNT(*) FROM p)                                  AS purchase_events,
  (SELECT COUNT(*) FROM real_orders)                        AS orders_with_id,
  (SELECT COUNT(*) FROM missing_id_orders)                  AS orders_without_id,
  (SELECT COUNT(DISTINCT FORMAT('%s|%t|%d', user_pseudo_id, revenue,
           DIV(event_timestamp, 60 * 1000000)))
     FROM missing_id_orders)                                AS without_id_distinct_user_revenue_minute,
  (SELECT ROUND(SUM(revenue)) FROM real_orders)             AS revenue_with_id,
  (SELECT ROUND(SUM(revenue)) FROM missing_id_orders)       AS revenue_without_id,
  (SELECT ROUND(SUM(revenue)) FROM p)                       AS revenue_all_events,
  (SELECT ROUND(SUM(tax)) FROM real_orders)
    + (SELECT ROUND(SUM(tax)) FROM missing_id_orders)       AS tax_on_orders;
