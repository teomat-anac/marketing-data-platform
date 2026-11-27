-- E10b: purchase events per week by transaction_id status and revenue.
-- Answers: why the last week of January has few orders under D17 (E8b): fewer purchases,
-- or purchases recorded without ID and revenue? Also: do zero-revenue events carry items?
SELECT
  DATE_TRUNC(PARSE_DATE('%Y%m%d', event_date), WEEK(MONDAY)) AS week,
  COUNT(*)                                                     AS purchase_events,
  COUNTIF(ecommerce.transaction_id IS NOT NULL
          AND ecommerce.transaction_id != '(not set)')         AS with_id,
  COUNTIF(IFNULL(ecommerce.transaction_id, '(not set)') = '(not set)'
          AND ecommerce.purchase_revenue_in_usd > 0)           AS no_id_with_revenue,
  COUNTIF(IFNULL(ecommerce.transaction_id, '(not set)') = '(not set)'
          AND IFNULL(ecommerce.purchase_revenue_in_usd, 0) = 0) AS no_id_zero_revenue,
  COUNTIF(IFNULL(ecommerce.purchase_revenue_in_usd, 0) = 0
          AND ARRAY_LENGTH(items) > 0)                         AS zero_revenue_with_items,
  ROUND(SUM(IF(IFNULL(ecommerce.purchase_revenue_in_usd, 0) = 0,
               (SELECT SUM(price_in_usd * quantity) FROM UNNEST(items)), 0)))
                                                               AS zero_revenue_items_value
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE event_name = 'purchase'
GROUP BY week
ORDER BY week;
