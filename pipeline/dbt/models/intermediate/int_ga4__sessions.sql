-- One row per session that started inside the data range, with its channel (D16), its
-- orders and revenue (D17) and the funnel steps it reached (D12).
--
-- Attribution, last non-direct click on sessions (D16, data-sources.md §5):
--   1. The session's own source = its first source/medium, ignoring self-referrals.
--   2. A user's first session with no source of its own takes traffic_source (first touch).
--   3. The channel rules seed turns that source into `own_channel` (D19).
--   4. A Direct session inherits the user's latest earlier non-direct channel, if that
--      session started at most `attribution_lookback_days` before; otherwise it stays Direct.
-- `own_channel` is what brought the visit (the cost generator follows it); `channel` is the
-- attributed channel the marts use.
--
-- The events cover the lookback window before the data range and one day after it (D39). A
-- session belongs to the day it started, so sessions outside the range are dropped only
-- after their events are grouped and the attribution has seen them.

with events as (
    select * from {{ ref('stg_ga4__events') }}
),

sessions as (
    select
        session_key,
        any_value(user_pseudo_id) as user_pseudo_id,
        min(event_at) as started_at,
        array_agg(event_date order by event_at, event_name limit 1)[offset(0)] as session_date,
        min(ga_session_number) as session_number,
        -- The first event that carries a source and isn't a self-referral
        array_agg(
            if(
                coalesce(source, medium) is null or {{ is_self_referral('source') }},
                null,
                struct(source, medium)
            )
            ignore nulls order by event_at, source, medium limit 1
        )[safe_offset(0)] as visit_source,
        array_agg(
            struct(first_user_source as source, first_user_medium as medium)
            order by event_at, event_name limit 1
        )[offset(0)] as first_user,
        logical_or(event_name = 'view_item') as reached_view_item,
        logical_or(event_name = 'add_to_cart') as reached_add_to_cart,
        logical_or(event_name = 'begin_checkout') as reached_begin_checkout
    from events
    group by session_key
),

own_source as (
    select
        *,
        case
            when visit_source is not null then visit_source.source
            when session_number = 1 and not {{ is_self_referral('first_user.source') }}
                then first_user.source
        end as own_source,
        case
            when visit_source is not null then visit_source.medium
            when session_number = 1 and not {{ is_self_referral('first_user.source') }}
                then first_user.medium
        end as own_medium
    from sessions
),

-- The first matching rule wins, ignoring case as GA4 does ("Channel definitions aren't case
-- sensitive"): `(?i)` makes RE2 match `CPC` like `cpc`. A session that matches no rule keeps
-- a NULL channel, and the not_null test fails: no session is ever dropped (FR-3).
own_channel as (
    select
        s.session_key,
        array_agg(r.channel order by r.rule_order limit 1)[offset(0)] as own_channel
    from own_source as s
    inner join {{ ref('channel_rules') }} as r
        on regexp_contains(ifnull(s.own_source, ''), concat('(?i)', r.source_pattern))
        and regexp_contains(ifnull(s.own_medium, ''), concat('(?i)', r.medium_pattern))
    group by s.session_key
),

with_previous as (
    select
        s.*,
        c.own_channel,
        last_value(
            if(c.own_channel = 'Direct', null, struct(c.own_channel as channel, s.started_at))
            ignore nulls
        ) over (
            partition by s.user_pseudo_id
            order by s.started_at, s.session_key
            rows between unbounded preceding and 1 preceding
        ) as previous_non_direct
    from own_source as s
    left join own_channel as c using (session_key)
),

session_orders as (
    select
        session_key,
        count(*) as orders,
        sum(revenue) as revenue
    from {{ ref('int_ga4__orders') }}
    group by session_key
)

select
    s.session_key,
    s.user_pseudo_id,
    s.session_number,
    s.session_date,
    s.started_at,
    s.own_source,
    s.own_medium,
    s.own_channel,
    case
        when s.own_channel != 'Direct' then s.own_channel
        when s.previous_non_direct is not null
            and s.started_at <= timestamp_add(
                s.previous_non_direct.started_at,
                interval {{ attribution_lookback_days() }} day
            )
            then s.previous_non_direct.channel
        else s.own_channel
    end as channel,
    ifnull(o.orders, 0) as orders,
    ifnull(o.revenue, 0) as revenue,
    s.reached_view_item,
    s.reached_add_to_cart,
    s.reached_begin_checkout,
    ifnull(o.orders, 0) > 0 as reached_purchase
from with_previous as s
left join session_orders as o using (session_key)
where s.session_date between date '{{ var("start_date") }}' and date '{{ var("end_date") }}'
