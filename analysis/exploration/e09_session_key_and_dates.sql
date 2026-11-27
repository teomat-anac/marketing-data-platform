-- E9: is the session key sound, and which date does a session belong to?
-- Answers: staging rules (session key, session date, order date).
WITH ev AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    event_timestamp,
    event_name
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    ARRAY_AGG(event_date ORDER BY event_timestamp LIMIT 1)[OFFSET(0)] AS start_date,
    COUNT(DISTINCT event_date) AS dates
  FROM ev
  WHERE ga_session_id IS NOT NULL
  GROUP BY 1, 2
)
SELECT
  (SELECT COUNT(*) FROM ev)                                   AS events,
  (SELECT COUNTIF(ga_session_id IS NULL) FROM ev)             AS events_without_session_id,
  (SELECT COUNTIF(ga_session_id IS NULL AND event_name = 'purchase') FROM ev) AS purchases_without_session_id,
  (SELECT COUNT(*) FROM sessions)                             AS sessions,
  (SELECT COUNT(DISTINCT ga_session_id) FROM sessions)        AS distinct_ga_session_ids,
  (SELECT COUNTIF(dates > 1) FROM sessions)                   AS sessions_over_midnight,
  (SELECT COUNT(*) FROM ev JOIN sessions s USING (user_pseudo_id, ga_session_id)
    WHERE ev.event_name = 'purchase' AND ev.event_date != s.start_date) AS purchases_not_on_session_start_date;
