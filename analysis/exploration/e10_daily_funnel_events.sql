-- E10: funnel events per day, to find tracking gaps (e.g. add_to_cart missing on 18 days)
-- and to explain the low last week of January.
-- Answers: funnel rules (D12) and data-quality flags.
SELECT
  PARSE_DATE('%Y%m%d', event_date)     AS day,
  COUNTIF(event_name = 'session_start')  AS session_start,
  COUNTIF(event_name = 'page_view')      AS page_view,
  COUNTIF(event_name = 'view_item')      AS view_item,
  COUNTIF(event_name = 'add_to_cart')    AS add_to_cart,
  COUNTIF(event_name = 'begin_checkout') AS begin_checkout,
  COUNTIF(event_name = 'add_payment_info') AS add_payment_info,
  COUNTIF(event_name = 'purchase')       AS purchase
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
GROUP BY day
ORDER BY day;
