-- E12: alternative source check. Universal Analytics (UA) sample, same shop, Aug 2016 - Aug 2017.
-- One row per SESSION, channel already assigned by GA (channelGrouping). Revenue is in micros.
-- Answers: Q1 (would another source give more paid channels?). Cost: ~30 MB.
SELECT
  channelGrouping,
  COUNT(*)                                              AS sessions,
  SUM(totals.transactions)                              AS transactions,
  ROUND(SUM(totals.totalTransactionRevenue) / 1e6)      AS revenue_usd,
  COUNT(DISTINCT trafficSource.campaign)                AS campaigns,
  MIN(date) AS first_day, MAX(date) AS last_day
FROM `bigquery-public-data.google_analytics_sample.ga_sessions_*`
GROUP BY channelGrouping
ORDER BY sessions DESC;
