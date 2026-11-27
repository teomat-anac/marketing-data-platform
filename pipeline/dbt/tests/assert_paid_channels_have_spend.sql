-- Every paid channel in the seed has some ad cost in the data range. Without it, ROAS and
-- CPA would be empty everywhere: e.g. the generator wasn't run, or wrote other days.
select channels.channel
from {{ ref('channels') }} as channels
left join {{ ref('mart_channel_daily') }} as mart using (channel)
where channels.is_paid
group by channels.channel
having ifnull(sum(mart.spend), 0) = 0
