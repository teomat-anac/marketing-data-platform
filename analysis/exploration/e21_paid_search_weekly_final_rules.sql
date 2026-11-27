-- E21: Paid Search per week under all the exploration's rules (see E20): own-source sessions
-- (visits ads actually brought: what the cost generator follows) and attributed orders and revenue.
-- Answers: generator ranges (clicks per day, CPC calibration).
-- Candidate channel rule (Q5), applied to a session's own source. First match wins.
CREATE TEMP FUNCTION channel_of(source STRING, medium STRING) AS (
  CASE
    WHEN source IS NULL AND medium IS NULL                                   THEN 'Direct'
    WHEN source = '(direct)' AND IFNULL(medium, '(none)') IN ('(none)', '(not set)') THEN 'Direct'
    WHEN medium = 'cpc'                                                      THEN 'Paid Search'
    WHEN medium = 'organic'                                                  THEN 'Organic Search'
    WHEN REGEXP_CONTAINS(IFNULL(source, ''),
      r'^(l\.|m\.|lm\.|www\.)?(facebook|instagram|linkedin|twitter|reddit|pinterest|quora|tiktok|messenger)\.com$|^t\.co$|^lnkd\.in$')
                                                                             THEN 'Organic Social'
    WHEN REGEXP_CONTAINS(IFNULL(source, ''), r'^(m\.|www\.)?youtube\.com$')   THEN 'Organic Video'
    WHEN medium = 'referral'                                                 THEN 'Referral'
    WHEN medium = 'email'                                                    THEN 'Email'
    WHEN medium = 'affiliate'                                                THEN 'Affiliates'
    ELSE 'Unassigned'
  END
);
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id')     AS ga_session_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS ga_session_number,
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    event_timestamp,
    event_name,
    traffic_source.source AS ft_source,
    traffic_source.medium AS ft_medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') AS source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium,
    ecommerce.transaction_id          AS tid,
    ecommerce.purchase_revenue_in_usd AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210124'   -- data ends on 24 Jan (last week's purchase tracking is broken, E10b/E10c)
),
-- Orders (D17, revised): one per (transaction_id, user); a purchase without an ID is an order
-- unless its session already has a purchase with an ID (then it's a duplicate). Missing revenue = 0.
purchases AS (
  SELECT user_pseudo_id, ga_session_id, event_timestamp, tid, revenue FROM events WHERE event_name = 'purchase'
),
id_orders AS (
  SELECT user_pseudo_id, ga_session_id, IFNULL(revenue, 0) AS revenue FROM purchases
  WHERE tid IS NOT NULL AND tid != '(not set)'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY tid, user_pseudo_id ORDER BY event_timestamp) = 1
),
id_sessions AS (
  SELECT DISTINCT user_pseudo_id, ga_session_id FROM purchases WHERE tid IS NOT NULL AND tid != '(not set)'
),
no_id_orders AS (
  SELECT p.user_pseudo_id, p.ga_session_id, IFNULL(p.revenue, 0) AS revenue
  FROM purchases p
  LEFT JOIN id_sessions s USING (user_pseudo_id, ga_session_id)
  WHERE (p.tid IS NULL OR p.tid = '(not set)') AND s.user_pseudo_id IS NULL
),
session_orders AS (
  SELECT user_pseudo_id, ga_session_id,
         COUNT(*) AS orders, COUNTIF(revenue = 0) AS orders_without_revenue, SUM(revenue) AS revenue
  FROM (SELECT * FROM id_orders UNION ALL SELECT * FROM no_id_orders)
  GROUP BY 1, 2
),
-- Sessions and attribution (D16)
sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    MIN(event_timestamp) AS start_ts,
    ARRAY_AGG(event_date ORDER BY event_timestamp LIMIT 1)[OFFSET(0)] AS session_date,
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
own AS (
  SELECT *,
    CASE
      WHEN visit IS NOT NULL THEN channel_of(visit.source, visit.medium)
      WHEN session_number = 1 AND IFNULL(ft_source, '') NOT LIKE '%googlemerchandisestore.com%'
        THEN channel_of(ft_source, ft_medium)
      ELSE 'Direct'
    END AS own_channel
  FROM sessions
),
carried AS (
  SELECT *,
    LAST_VALUE(IF(own_channel = 'Direct', NULL, STRUCT(own_channel AS channel, start_ts AS ts)) IGNORE NULLS)
      OVER (PARTITION BY user_pseudo_id ORDER BY start_ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_non_direct
  FROM own
),
final AS (
  SELECT c.*,
    CASE
      WHEN own_channel != 'Direct' THEN own_channel
      WHEN prev_non_direct IS NOT NULL
       AND start_ts - prev_non_direct.ts <= 90 * 24 * 3600 * 1000000 THEN prev_non_direct.channel
      ELSE 'Direct'
    END AS channel,
    IFNULL(o.orders, 0)                 AS orders,
    IFNULL(o.orders_without_revenue, 0) AS orders_without_revenue,
    IFNULL(o.revenue, 0)                AS revenue
  FROM carried c
  LEFT JOIN session_orders o USING (user_pseudo_id, ga_session_id)
)
, daily AS (
  SELECT
    session_date,
    COUNTIF(own_channel = 'Paid Search')                   AS own_sessions,
    SUM(IF(channel = 'Paid Search', orders, 0))            AS orders,
    SUM(IF(channel = 'Paid Search', revenue, 0))           AS revenue
  FROM final
  GROUP BY session_date
)
SELECT
  DATE_TRUNC(session_date, WEEK(MONDAY)) AS week,
  COUNT(*)                   AS days,
  SUM(own_sessions)          AS own_sessions,
  MIN(own_sessions)          AS min_per_day,
  ROUND(AVG(own_sessions), 1) AS avg_per_day,
  MAX(own_sessions)          AS max_per_day,
  SUM(orders)                AS orders,
  ROUND(SUM(revenue))        AS revenue_usd
FROM daily
GROUP BY week
ORDER BY week;
