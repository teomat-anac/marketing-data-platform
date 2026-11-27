-- E2: how many events of each kind, over the whole period?
-- Answers: which funnel steps exist (US-3), overall volumes.
SELECT
  event_name,
  COUNT(*)                        AS events,
  COUNT(DISTINCT user_pseudo_id)  AS users,
  COUNT(DISTINCT event_date)      AS days_present
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
GROUP BY event_name
ORDER BY events DESC;
