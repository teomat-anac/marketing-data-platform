-- E15: which session sources do the purchase sessions have?
-- Answers: Q2 (do self-referrals or payment pages take credit for sales?).
-- Session source = first non-null source/medium in the session (GA4 convention).
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    event_timestamp,
    event_name,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') AS source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium,
    ecommerce.transaction_id,
    ecommerce.purchase_revenue_in_usd
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    ARRAY_AGG(IF(COALESCE(source, medium) IS NULL, NULL, STRUCT(source, medium))
              IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS visit,
    COUNT(DISTINCT IF(event_name = 'purchase', transaction_id, NULL)) AS orders,
    SUM(IF(event_name = 'purchase', purchase_revenue_in_usd, 0))      AS revenue
  FROM events
  GROUP BY 1, 2
)
SELECT
  visit.source,
  visit.medium,
  COUNT(*)              AS purchase_sessions,
  SUM(orders)           AS orders,
  ROUND(SUM(revenue))   AS revenue_usd
FROM sessions
WHERE orders > 0
GROUP BY 1, 2
ORDER BY revenue_usd DESC
LIMIT 25;
