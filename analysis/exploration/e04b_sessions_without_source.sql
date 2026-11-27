-- E4b: what do the sessions with no source/medium/campaign have in common?
-- Answers: whether they hide paid traffic (Q1) and how to map them (Q5).
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')     AS ga_session_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS ga_session_number,
    event_name,
    traffic_source.medium AS first_touch_medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    LOGICAL_OR(medium IS NOT NULL)            AS has_source,
    LOGICAL_OR(event_name = 'session_start')  AS has_session_start,
    MIN(ga_session_number) = 1                AS is_first_session,
    ANY_VALUE(first_touch_medium)             AS first_touch_medium,
    COUNTIF(event_name = 'purchase')          AS purchase_events
  FROM events
  GROUP BY 1, 2
)
SELECT
  has_source,
  has_session_start,
  is_first_session,
  first_touch_medium,
  COUNT(*)                      AS sessions,
  COUNTIF(purchase_events > 0)  AS sessions_with_purchase
FROM sessions
GROUP BY 1, 2, 3, 4
ORDER BY has_source, sessions DESC;
