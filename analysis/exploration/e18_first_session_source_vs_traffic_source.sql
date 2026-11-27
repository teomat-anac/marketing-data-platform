-- E18: on a user's FIRST session, does the session's own source agree with traffic_source
-- (the user's first-touch source)? If it does, traffic_source can fill in first sessions
-- that have no source of their own.
-- Answers: Q2/Q5 (can the 94k sessions without a source be recovered?).
-- Self-referrals (the shop's own domains) are ignored as sources.
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
    traffic_source.source AS ft_source,
    traffic_source.medium AS ft_medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') AS source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    MIN(ga_session_number) AS session_number,
    ARRAY_AGG(
      IF(COALESCE(source, medium) IS NULL OR IFNULL(source, '') LIKE '%googlemerchandisestore.com%',
         NULL, STRUCT(source, medium))
      IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS visit,
    ANY_VALUE(ft_source) AS ft_source,
    ANY_VALUE(ft_medium) AS ft_medium
  FROM events
  GROUP BY 1, 2
),
compared AS (
  SELECT
    bucket(visit.source, visit.medium) AS session_channel,
    bucket(ft_source, ft_medium)       AS first_touch_channel
  FROM sessions
  WHERE session_number = 1 AND visit IS NOT NULL
)
SELECT
  session_channel,
  COUNT(*)                                                         AS first_sessions,
  ROUND(COUNTIF(session_channel = first_touch_channel) / COUNT(*), 3) AS share_agreeing,
  APPROX_TOP_COUNT(first_touch_channel, 3)                         AS top_first_touch
FROM compared
GROUP BY session_channel
ORDER BY first_sessions DESC;
