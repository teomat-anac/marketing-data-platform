-- E5: sessions per day for the paid candidates (visit's own medium).
-- Answers: generator ranges; whether candidates have activity every day.
WITH events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    event_timestamp,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions AS (
  SELECT
    MIN(event_date) AS session_date,
    ARRAY_AGG(medium IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS medium
  FROM events
  GROUP BY user_pseudo_id, ga_session_id
),
spine AS (
  SELECT d AS session_date, m AS medium
  FROM UNNEST(GENERATE_DATE_ARRAY('2020-11-01', '2021-01-31')) AS d,
       UNNEST(['cpc', 'affiliate']) AS m
),
daily AS (
  SELECT spine.session_date, spine.medium, COUNT(s.medium) AS sessions
  FROM spine LEFT JOIN sessions s USING (session_date, medium)
  GROUP BY 1, 2
)
SELECT
  medium,
  COUNTIF(sessions = 0)               AS days_with_zero,
  MIN(sessions)                       AS min_per_day,
  APPROX_QUANTILES(sessions, 2)[OFFSET(1)] AS median_per_day,
  ROUND(AVG(sessions), 1)             AS avg_per_day,
  MAX(sessions)                       AS max_per_day,
  ARRAY_AGG(session_date ORDER BY sessions DESC LIMIT 1)[OFFSET(0)] AS peak_day,
  ARRAY_AGG(IF(sessions = 0, session_date, NULL) IGNORE NULLS ORDER BY session_date LIMIT 5) AS first_zero_days
FROM daily
GROUP BY medium;
