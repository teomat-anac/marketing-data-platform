-- E3: traffic_source = how each user FIRST arrived (user-level, first touch).
-- Answers: Q1, Q5 (which sources/mediums/campaigns exist at all).
SELECT
  traffic_source.source,
  traffic_source.medium,
  traffic_source.name             AS campaign,
  COUNT(DISTINCT user_pseudo_id)  AS users
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
GROUP BY 1, 2, 3
ORDER BY users DESC
LIMIT 40;
