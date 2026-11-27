-- One row per order (D17, data-sources.md §5):
--   1. With an ID: one order per (transaction_id, user), keeping the first purchase event.
--      This removes duplicate events, and keeps colliding IDs of different users apart.
--   2. Without an ID: one order per purchase event, unless its session already has a
--      purchase with an ID (then the event is a duplicate of that order).
--   3. An order whose amount wasn't recorded counts, with revenue 0.
-- Money is NUMERIC rounded to cents (D22). Ties on time are broken by the other columns,
-- so a rebuild always keeps the same event (FR-5).

with purchases as (
    select
        session_key,
        user_pseudo_id,
        event_at,
        transaction_id,
        round(cast(purchase_revenue_usd as numeric), 2) as revenue
    from {{ ref('stg_ga4__events') }}
    where event_name = 'purchase'
),

with_id as (
    select
        concat(user_pseudo_id, ':', transaction_id) as order_key,
        session_key,
        user_pseudo_id,
        transaction_id,
        event_at as ordered_at,
        revenue
    from purchases
    where transaction_id is not null
    qualify row_number() over (
        partition by transaction_id, user_pseudo_id
        order by event_at, session_key, revenue
    ) = 1
),

sessions_with_id as (
    select distinct session_key
    from purchases
    where transaction_id is not null
),

without_id as (
    select
        -- No ID to key on: the session, the event time and a counter for same-time events
        concat(
            p.session_key, ':', cast(unix_micros(p.event_at) as string), ':',
            cast(row_number() over (
                partition by p.session_key, p.event_at order by p.revenue
            ) as string)
        ) as order_key,
        p.session_key,
        p.user_pseudo_id,
        cast(null as string) as transaction_id,
        p.event_at as ordered_at,
        p.revenue
    from purchases as p
    left join sessions_with_id as s using (session_key)
    where p.transaction_id is null and s.session_key is null
),

orders as (
    select * from with_id
    union all
    select * from without_id
)

select
    order_key,
    session_key,
    user_pseudo_id,
    transaction_id,
    ordered_at,
    ifnull(revenue, 0) as revenue,
    revenue is null or revenue = 0 as is_revenue_missing
from orders
