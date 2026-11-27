-- E13: UA sample, paid channels by campaign: are real campaign names available?
-- Answers: Q1 (alternative source check).
SELECT
  channelGrouping,
  trafficSource.campaign,
  COUNT(*)                                         AS sessions,
  SUM(totals.transactions)                         AS transactions,
  ROUND(SUM(totals.totalTransactionRevenue) / 1e6) AS revenue_usd,
  COUNT(DISTINCT date)                             AS days_active
FROM `bigquery-public-data.google_analytics_sample.ga_sessions_*`
WHERE channelGrouping IN ('Paid Search', 'Display', 'Affiliates')
GROUP BY 1, 2
ORDER BY 1, sessions DESC
LIMIT 40;
