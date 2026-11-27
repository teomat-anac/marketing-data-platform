-- KPIs per day × channel (D22): additive values only; ratios are computed on request (FR-7).
-- Every day of the data range has a row for every channel in the seed, zeros included (D13).
{{ config(
    partition_by={'field': 'date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['channel'],
) }}

with days as (
    select date
    from unnest(generate_date_array(date '{{ var("start_date") }}', date '{{ var("end_date") }}')) as date
),

spine as (
    select days.date, channels.channel, channels.is_paid
    from days
    cross join {{ ref('channels') }} as channels
),

sessions as (
    select
        session_date as date,
        channel,
        count(*) as sessions,
        sum(orders) as orders,
        sum(revenue) as revenue
    from {{ ref('int_ga4__sessions') }}
    group by session_date, channel
),

ads as (
    select
        date,
        channel,
        sum(clicks) as clicks,
        sum(impressions) as impressions,
        sum(spend) as spend
    from {{ ref('stg_ads__spend') }}
    group by date, channel
)

select
    spine.date,
    spine.channel,
    spine.is_paid,
    ifnull(sessions.sessions, 0) as sessions,
    ifnull(sessions.orders, 0) as orders,
    ifnull(sessions.revenue, 0) as revenue,
    ifnull(ads.clicks, 0) as clicks,
    ifnull(ads.impressions, 0) as impressions,
    ifnull(ads.spend, 0) as spend
from spine
left join sessions using (date, channel)
left join ads using (date, channel)
