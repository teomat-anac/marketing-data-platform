-- E11: sessions, orders and revenue per channel, under last click (the visit's
-- own medium) vs first touch (the user's first medium, traffic_source).
-- Answers: Q1 (do paid candidates have sales?), Q2 (how much attribution matters).
-- Orders = distinct transaction_id on purchase events (rough; E6 refines it).
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    event_timestamp,
    event_name,
    traffic_source.source AS ft_source,
    traffic_source.medium AS ft_medium,
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
    ARRAY_AGG(IF(medium IS NULL, NULL, STRUCT(source, medium))
              IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS visit,
    ANY_VALUE(ft_source) AS ft_source,
    ANY_VALUE(ft_medium) AS ft_medium,
    ARRAY_AGG(DISTINCT IF(event_name = 'purchase', transaction_id, NULL) IGNORE NULLS) AS orders,
    SUM(IF(event_name = 'purchase', purchase_revenue_in_usd, 0)) AS revenue
  FROM events
  GROUP BY 1, 2
),
bucketed AS (
  SELECT
    CASE
      WHEN visit.medium = 'cpc' THEN 'cpc'
      WHEN visit.medium = 'affiliate' THEN 'affiliate'
      WHEN visit.source LIKE '%doubleclick%' THEN 'doubleclick'
      ELSE COALESCE(visit.medium, '(no source)')
    END AS last_click_medium,
    CASE
      WHEN ft_medium = 'cpc' THEN 'cpc'
      WHEN ft_medium = 'affiliate' THEN 'affiliate'
      WHEN ft_source LIKE '%doubleclick%' THEN 'doubleclick'
      ELSE ft_medium
    END AS first_touch_medium,
    ARRAY_LENGTH(orders) AS orders,
    revenue
  FROM sessions
)
SELECT 'last_click' AS model, last_click_medium AS medium,
       COUNT(*) AS sessions, SUM(orders) AS orders, ROUND(SUM(revenue)) AS revenue_usd
FROM bucketed GROUP BY 1, 2
UNION ALL
SELECT 'first_touch', first_touch_medium,
       COUNT(*), SUM(orders), ROUND(SUM(revenue))
FROM bucketed GROUP BY 1, 2
ORDER BY model, sessions DESC;
