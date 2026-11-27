-- The funnel's first step is every session: on each day × channel, `visit` in
-- mart_funnel_daily equals `sessions` in mart_channel_daily, so the two marts agree.
-- Days on which `visit` is listed as a tracking gap have no count by design: skipped.
select
    funnel.date,
    funnel.channel,
    funnel.sessions as funnel_visits,
    kpi.sessions as kpi_sessions
from {{ ref('mart_funnel_daily') }} as funnel
inner join {{ ref('mart_channel_daily') }} as kpi using (date, channel)
where funnel.step = 'visit'
    and funnel.is_tracked
    and funnel.sessions is distinct from kpi.sessions
