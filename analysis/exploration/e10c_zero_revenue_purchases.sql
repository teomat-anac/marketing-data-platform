-- E10c: are the purchase events without ID and without revenue duplicates of real orders,
-- or real purchases whose ID and revenue were not recorded?
-- Checks, per week: does the same session also have a purchase with an ID or revenue (a twin)?
-- Did the session go through checkout (begin_checkout / add_payment_info)?
WITH ev AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    DATE_TRUNC(PARSE_DATE('%Y%m%d', event_date), WEEK(MONDAY)) AS week,
    event_name,
    ecommerce.transaction_id          AS tid,
    ecommerce.purchase_revenue_in_usd AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name IN ('purchase', 'begin_checkout', 'add_payment_info')
),
zero AS (
  SELECT * FROM ev
  WHERE event_name = 'purchase'
    AND IFNULL(tid, '(not set)') = '(not set)'
    AND IFNULL(revenue, 0) = 0
)
SELECT
  week,
  COUNT(*) AS zero_revenue_events,
  COUNTIF(EXISTS (
    SELECT 1 FROM ev o
    WHERE o.user_pseudo_id = z.user_pseudo_id AND o.ga_session_id = z.ga_session_id
      AND o.event_name = 'purchase'
      AND ((o.tid IS NOT NULL AND o.tid != '(not set)') OR o.revenue > 0)
  )) AS with_twin_in_session,
  COUNTIF(EXISTS (
    SELECT 1 FROM ev o
    WHERE o.user_pseudo_id = z.user_pseudo_id AND o.ga_session_id = z.ga_session_id
      AND o.event_name IN ('begin_checkout', 'add_payment_info')
  )) AS session_went_through_checkout
FROM zero z
GROUP BY week
ORDER BY week;
