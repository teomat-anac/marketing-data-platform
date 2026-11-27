-- E4: source/medium/campaign of each VISIT, from event_params (session level).
-- Answers: Q1, Q2, Q5. Compare with E3 (first touch).
-- Session key = user_pseudo_id + ga_session_id. A session takes the first
-- non-null source/medium/campaign among its events, by timestamp.
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    event_timestamp,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source')   AS source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium')   AS medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'campaign') AS campaign
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    ARRAY_AGG(
      IF(COALESCE(source, medium, campaign) IS NULL, NULL, STRUCT(source, medium, campaign))
      IGNORE NULLS ORDER BY event_timestamp LIMIT 1
    )[SAFE_OFFSET(0)]               AS visit,
    COUNT(DISTINCT medium)          AS distinct_mediums
  FROM events
  GROUP BY 1, 2
)
SELECT
  visit.source,
  visit.medium,
  visit.campaign,
  COUNT(*)                          AS sessions,
  COUNTIF(distinct_mediums > 1)     AS sessions_with_medium_change
FROM sessions
GROUP BY 1, 2, 3
ORDER BY sessions DESC
LIMIT 40;
