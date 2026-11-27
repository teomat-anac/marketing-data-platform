-- E6c: transaction_ids used by more than one purchase event that do NOT look like
-- the same order (different user, day or revenue).
-- Answers: Q4 (is "one transaction_id = one order" safe?).
SELECT
  ecommerce.transaction_id                         AS tid,
  COUNT(*)                                         AS events,
  COUNT(DISTINCT user_pseudo_id)                   AS users,
  COUNT(DISTINCT event_date)                       AS days,
  ARRAY_AGG(ROUND(ecommerce.purchase_revenue_in_usd, 2) ORDER BY event_timestamp) AS revenues,
  ARRAY_AGG(event_date ORDER BY event_timestamp)   AS dates
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE event_name = 'purchase'
  AND ecommerce.transaction_id IS NOT NULL
  AND ecommerce.transaction_id != '(not set)'
GROUP BY tid
HAVING COUNT(*) > 1
   AND (COUNT(DISTINCT user_pseudo_id) > 1
        OR COUNT(DISTINCT event_date) > 1
        OR COUNT(DISTINCT ecommerce.purchase_revenue_in_usd) > 1)
ORDER BY events DESC;
