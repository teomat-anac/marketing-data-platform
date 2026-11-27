-- One row per GA4 event: flattened, typed and renamed. No business rules here (D5).
--
-- Only the columns the project uses are read: BigQuery bills by columns scanned, and the
-- `_TABLE_SUFFIX` filter skips the daily tables outside the window. The window is wider than
-- the data range (D39); int_ga4__sessions then keeps sessions by the day they started:
--   - from `attribution_lookback_days` before it: a Direct session can inherit the channel
--     of an earlier visit, and a session that started the day before is grouped whole;
--   - to one day after it: sessions starting on the last day keep their events after midnight.
-- With the GA4 sample, no table exists before 2020-11-01, so the earlier days cost nothing.
--
-- Every event in the sample has a ga_session_id (E9). An event without one would get a
-- NULL session_key; the tests on int_ga4__sessions then fail the build rather than guess.
--
-- No data tests on this view: each would scan the GA4 sample (about 1.6 GB). The tests sit
-- on the intermediate tables built from it.

select
    parse_date('%Y%m%d', event_date) as event_date,
    timestamp_micros(event_timestamp) as event_at,
    event_name,
    user_pseudo_id,
    (select value.int_value from unnest(event_params) where key = 'ga_session_id') as ga_session_id,
    (select value.int_value from unnest(event_params) where key = 'ga_session_number') as ga_session_number,
    -- ga_session_id alone is not unique across users (E9)
    concat(
        user_pseudo_id, '-',
        cast((select value.int_value from unnest(event_params) where key = 'ga_session_id') as string)
    ) as session_key,
    -- The source of this visit, on about a third of the events (E1)
    (select value.string_value from unnest(event_params) where key = 'source') as source,
    (select value.string_value from unnest(event_params) where key = 'medium') as medium,
    -- The user's first acquisition (first touch), not this visit's source
    traffic_source.source as first_user_source,
    traffic_source.medium as first_user_medium,
    -- '(not set)' and '' are GA4's placeholders for a missing ID
    nullif(nullif(ecommerce.transaction_id, '(not set)'), '') as transaction_id,
    -- Without tax, before refunds (D17); FLOAT64 in the export
    ecommerce.purchase_revenue_in_usd as purchase_revenue_usd
from {{ source('ga4', 'events') }}
where _table_suffix between '{{ ga4_table_suffix(var("start_date"), days=0 - (attribution_lookback_days() | int)) }}'
    and '{{ ga4_table_suffix(var("end_date"), days=1) }}'
