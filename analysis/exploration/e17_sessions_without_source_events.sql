-- E17: what do sessions WITHOUT a source contain, compared with sessions that have one?
-- Answers: Q5 (are they real visits, to map as Direct, or artefacts?).
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    event_name,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') AS source
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    LOGICAL_OR(COALESCE(source, medium) IS NOT NULL) AS has_source,
    COUNT(*)                                          AS events,
    COUNTIF(event_name = 'page_view')                 AS page_views,
    COUNTIF(event_name = 'view_item')                 AS item_views,
    COUNTIF(event_name = 'user_engagement')           AS engagements,
    STRING_AGG(DISTINCT event_name ORDER BY event_name) AS event_set
  FROM events
  GROUP BY 1, 2
)
SELECT
  has_source,
  COUNT(*)                                   AS sessions,
  ROUND(AVG(events), 1)                      AS avg_events,
  ROUND(COUNTIF(page_views > 0) / COUNT(*), 3)  AS share_with_page_view,
  ROUND(COUNTIF(item_views > 0) / COUNT(*), 3)  AS share_with_item_view,
  ROUND(COUNTIF(engagements > 0) / COUNT(*), 3) AS share_with_engagement,
  APPROX_TOP_COUNT(event_set, 3)             AS top_event_sets
FROM sessions
GROUP BY has_source;
