-- mart_channel_daily adds up to int_ga4__sessions: no session, order or revenue is lost or
-- counted twice when sessions are grouped by day and channel (FR-3, FR-5). Sums of no rows
-- are read as 0, so an empty side is compared as 0 instead of passing as NULL.
with mart as (
    select
        ifnull(sum(sessions), 0) as sessions,
        ifnull(sum(orders), 0) as orders,
        ifnull(sum(revenue), 0) as revenue
    from {{ ref('mart_channel_daily') }}
),

sessions as (
    select count(*) as sessions, ifnull(sum(orders), 0) as orders, ifnull(sum(revenue), 0) as revenue
    from {{ ref('int_ga4__sessions') }}
)

select mart.*, sessions.sessions as expected_sessions, sessions.orders as expected_orders,
    sessions.revenue as expected_revenue
from mart
cross join sessions
where mart.sessions is distinct from sessions.sessions
    or mart.orders is distinct from sessions.orders
    or mart.revenue is distinct from sessions.revenue
