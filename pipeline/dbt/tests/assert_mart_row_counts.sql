-- Both marts are zero-filled (D13): one row per day × channel, and per day × channel × step.
-- With the default range and seed: 85 × 9 = 765 and 765 × 5 = 3,825 rows (architecture.md §2).
-- Returns a row for each mart whose count is wrong.
with expected as (
    select
        (date_diff(date '{{ var("end_date") }}', date '{{ var("start_date") }}', day) + 1)
        * (select count(*) from {{ ref('channels') }}) as day_channels
),

actual as (
    select 'mart_channel_daily' as mart, count(*) as row_count, 1 as rows_per_day_channel
    from {{ ref('mart_channel_daily') }}
    union all
    select 'mart_funnel_daily', count(*), 5
    from {{ ref('mart_funnel_daily') }}
)

select actual.mart, actual.row_count, expected.day_channels * actual.rows_per_day_channel as expected_rows
from actual
cross join expected
where actual.row_count != expected.day_channels * actual.rows_per_day_channel
