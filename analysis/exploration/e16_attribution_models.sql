-- E16: sessions, orders and revenue per channel under three attribution models.
--   session_source   : the session's own first source/medium (no carry-over)
--   last_non_direct  : like session_source, but a Direct / no-source / self-referral
--                      session inherits the user's latest earlier non-direct channel
--                      (90-day lookback, as in GA4); otherwise it stays Direct
--   first_touch      : the user's first-ever source (traffic_source), for every session
-- Answers: Q2. The channel buckets are a preliminary mapping, for comparison only (Q5).
CREATE TEMP FUNCTION bucket(source STRING, medium STRING) AS (
  CASE
    WHEN source IS NULL AND medium IS NULL               THEN 'No source'
    WHEN source LIKE '%googlemerchandisestore.com%'      THEN 'Self-referral'
    WHEN medium = 'cpc'                                  THEN 'Paid Search'
    WHEN medium = 'organic'                              THEN 'Organic Search'
    WHEN medium = 'referral'                             THEN 'Referral'
    WHEN medium = 'email'                                THEN 'Email'
    WHEN medium = 'affiliate'                            THEN 'Affiliates'
    WHEN source = '(direct)' OR medium = '(none)'        THEN 'Direct'
    ELSE 'Other / unknown'
  END
);
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
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
    MIN(event_timestamp) AS start_ts,
    ARRAY_AGG(IF(COALESCE(source, medium) IS NULL, NULL, STRUCT(source, medium))
              IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS visit,
    ANY_VALUE(ft_source) AS ft_source,
    ANY_VALUE(ft_medium) AS ft_medium,
    COUNT(DISTINCT IF(event_name = 'purchase', transaction_id, NULL)) AS orders,
    SUM(IF(event_name = 'purchase', purchase_revenue_in_usd, 0))      AS revenue
  FROM events
  GROUP BY 1, 2
),
own AS (
  SELECT *,
    bucket(visit.source, visit.medium) AS own_channel,
    bucket(visit.source, visit.medium) IN ('Direct', 'No source', 'Self-referral') AS is_direct_like
  FROM sessions
),
carried AS (
  SELECT *,
    LAST_VALUE(IF(is_direct_like, NULL, STRUCT(own_channel AS channel, start_ts AS ts)) IGNORE NULLS)
      OVER (PARTITION BY user_pseudo_id ORDER BY start_ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_non_direct
  FROM own
),
models AS (
  SELECT 'session_source' AS model, own_channel AS channel, orders, revenue FROM carried
  UNION ALL
  SELECT 'last_non_direct',
    CASE
      WHEN NOT is_direct_like THEN own_channel
      WHEN prev_non_direct IS NOT NULL
       AND start_ts - prev_non_direct.ts <= 90 * 24 * 3600 * 1000000 THEN prev_non_direct.channel
      ELSE 'Direct'
    END,
    orders, revenue
  FROM carried
  UNION ALL
  SELECT 'first_touch', bucket(ft_source, ft_medium), orders, revenue FROM carried
)
SELECT
  model,
  channel,
  COUNT(*)             AS sessions,
  SUM(orders)          AS orders,
  ROUND(SUM(revenue))  AS revenue_usd
FROM models
GROUP BY 1, 2
ORDER BY model, revenue_usd DESC;
