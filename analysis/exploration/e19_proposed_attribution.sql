-- E19: sessions, orders and revenue per channel under the PROPOSED rule:
--   1. A session's own source = its first non-null source/medium, ignoring self-referrals.
--   2. A user's first session with no own source takes traffic_source (the user's first touch).
--   3. Direct-like sessions (direct, no source) inherit the user's latest earlier non-direct
--      channel within 90 days (last non-direct click); otherwise they stay Direct.
-- own_source_sessions = sessions whose own source is that channel (for Paid Search: ad clicks
-- that became visits, which is what the cost generator follows).
-- Answers: Q2. Channel buckets are preliminary (Q5).
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
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id')     AS ga_session_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS ga_session_number,
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
    MIN(event_timestamp)   AS start_ts,
    MIN(ga_session_number) AS session_number,
    ARRAY_AGG(
      IF(COALESCE(source, medium) IS NULL OR IFNULL(source, '') LIKE '%googlemerchandisestore.com%',
         NULL, STRUCT(source, medium))
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
    CASE
      WHEN visit IS NOT NULL THEN bucket(visit.source, visit.medium)
      WHEN session_number = 1
       AND bucket(ft_source, ft_medium) NOT IN ('Self-referral', 'No source') THEN bucket(ft_source, ft_medium)
      ELSE 'Direct'
    END AS own_channel
  FROM sessions
),
carried AS (
  SELECT *,
    LAST_VALUE(IF(own_channel = 'Direct', NULL, STRUCT(own_channel AS channel, start_ts AS ts)) IGNORE NULLS)
      OVER (PARTITION BY user_pseudo_id ORDER BY start_ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_non_direct
  FROM own
),
final AS (
  SELECT *,
    CASE
      WHEN own_channel != 'Direct' THEN own_channel
      WHEN prev_non_direct IS NOT NULL
       AND start_ts - prev_non_direct.ts <= 90 * 24 * 3600 * 1000000 THEN prev_non_direct.channel
      ELSE 'Direct'
    END AS channel
  FROM carried
)
SELECT
  channel,
  COUNT(*)                          AS sessions,
  COUNTIF(own_channel = channel)    AS own_source_sessions,
  ROUND(COUNTIF(own_channel = channel) / 92, 1) AS own_sessions_per_day,
  SUM(orders)                       AS orders,
  ROUND(SUM(revenue))               AS revenue_usd
FROM final
GROUP BY channel
ORDER BY revenue_usd DESC;
