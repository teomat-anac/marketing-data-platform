-- Open funnel per day × channel × step (D12): the sessions that reached each step, whether
-- or not they went through the earlier ones. A step in a known tracking gap (D20) is not
-- recorded that day: `sessions` is NULL, never 0. Every day × channel × step has a row (D13).
{{ config(
    partition_by={'field': 'date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['channel'],
) }}

with days as (
    select date
    from unnest(generate_date_array(date '{{ var("start_date") }}', date '{{ var("end_date") }}')) as date
),

steps as (
    select step, step_number
    from unnest([
        struct('visit' as step, 1 as step_number),
        ('view_item', 2),
        ('add_to_cart', 3),
        ('begin_checkout', 4),
        ('purchase', 5)
    ])
),

spine as (
    select days.date, channels.channel, steps.step, steps.step_number
    from days
    cross join {{ ref('channels') }} as channels
    cross join steps
),

counts as (
    select
        session_date as date,
        channel,
        count(*) as visit,
        countif(reached_view_item) as view_item,
        countif(reached_add_to_cart) as add_to_cart,
        countif(reached_begin_checkout) as begin_checkout,
        countif(reached_purchase) as purchase
    from {{ ref('int_ga4__sessions') }}
    group by session_date, channel
),

step_counts as (
    select date, channel, step, sessions
    from counts
    unpivot (sessions for step in (visit, view_item, add_to_cart, begin_checkout, purchase))
),

untracked as (
    select distinct gaps.step, date
    from {{ ref('tracking_gaps') }} as gaps
    cross join unnest(generate_date_array(gaps.start_date, gaps.end_date)) as date
)

select
    spine.date,
    spine.channel,
    spine.step,
    spine.step_number,
    if(untracked.step is null, ifnull(step_counts.sessions, 0), null) as sessions,
    untracked.step is null as is_tracked
from spine
left join step_counts using (date, channel, step)
left join untracked using (step, date)
