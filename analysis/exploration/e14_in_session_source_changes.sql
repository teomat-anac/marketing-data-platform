-- E14: when a session has more than one source/medium, what replaces what?
-- Answers: Q2 (which value should represent the session: first or a later one?).
-- Shows the first and second distinct source/medium seen in a session, by time.
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    event_timestamp,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') AS source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
touches AS (
  SELECT user_pseudo_id, ga_session_id, source, medium, MIN(event_timestamp) AS first_seen
  FROM events
  WHERE COALESCE(source, medium) IS NOT NULL
  GROUP BY 1, 2, 3, 4
),
ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY user_pseudo_id, ga_session_id
                       ORDER BY first_seen, source, medium) AS rn
  FROM touches
)
SELECT
  a.source AS first_source,  a.medium AS first_medium,
  b.source AS second_source, b.medium AS second_medium,
  COUNT(*) AS sessions
FROM ranked a
JOIN ranked b USING (user_pseudo_id, ga_session_id)
WHERE a.rn = 1 AND b.rn = 2
GROUP BY 1, 2, 3, 4
ORDER BY sessions DESC
LIMIT 25;
