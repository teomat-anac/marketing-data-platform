-- E6b: purchase events without a usable transaction_id, and purchase events with zero revenue.
-- Answers: Q3/Q4. "Real twin" = a purchase with a real transaction_id by the same user,
-- with the same revenue, within 10 minutes (a likely duplicate of the same order).
WITH p AS (
  SELECT
    user_pseudo_id,
    event_timestamp,
    ecommerce.transaction_id          AS tid,
    ecommerce.purchase_revenue_in_usd AS revenue,
    (SELECT SUM(item_revenue_in_usd) FROM UNNEST(items)) AS items_revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
),
real_tid AS (
  SELECT user_pseudo_id, event_timestamp, revenue
  FROM p
  WHERE tid IS NOT NULL AND tid != '(not set)'
),
flagged AS (
  SELECT
    p.*,
    CASE WHEN p.tid IS NULL THEN 'null'
         WHEN p.tid = '(not set)' THEN '(not set)'
         ELSE 'real' END AS tid_status,
    EXISTS (
      SELECT 1 FROM real_tid r
      WHERE r.user_pseudo_id = p.user_pseudo_id
        AND r.revenue = p.revenue
        AND r.event_timestamp != p.event_timestamp
        AND ABS(r.event_timestamp - p.event_timestamp) <= 600 * 1000000
    ) AS has_real_twin
  FROM p
)
SELECT
  tid_status,
  revenue = 0                       AS zero_revenue,
  COUNT(*)                          AS events,
  COUNT(DISTINCT user_pseudo_id)    AS users,
  ROUND(SUM(revenue))               AS revenue,
  ROUND(SUM(items_revenue))         AS items_revenue,
  COUNTIF(has_real_twin)            AS with_real_twin
FROM flagged
GROUP BY 1, 2
ORDER BY 1, 2;
