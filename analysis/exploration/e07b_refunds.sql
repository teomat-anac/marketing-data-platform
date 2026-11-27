-- E7b: are refunds recorded anywhere? (No 'refund' event exists, see E2.)
-- Answers: Q3 (refund handling).
SELECT
  event_name,
  COUNT(*)                                     AS events,
  COUNTIF(ecommerce.refund_value_in_usd IS NOT NULL) AS with_refund_value,
  ROUND(SUM(ecommerce.refund_value_in_usd))    AS refund_value_usd,
  COUNTIF(EXISTS(SELECT 1 FROM UNNEST(items) WHERE item_refund_in_usd IS NOT NULL)) AS with_item_refund
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE ecommerce.refund_value_in_usd IS NOT NULL
   OR EXISTS(SELECT 1 FROM UNNEST(items) WHERE item_refund_in_usd IS NOT NULL)
GROUP BY event_name;
