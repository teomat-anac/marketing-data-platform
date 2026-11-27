-- mart_channel_daily carries all the ad cost of the data range: none dropped (e.g. a channel
-- missing from the seed) and none counted twice. Sums of no rows are read as 0, so an empty
-- side is compared as 0 instead of passing as NULL.
with mart as (
    select
        ifnull(sum(clicks), 0) as clicks,
        ifnull(sum(impressions), 0) as impressions,
        ifnull(sum(spend), 0) as spend
    from {{ ref('mart_channel_daily') }}
),

ads as (
    select
        ifnull(sum(clicks), 0) as clicks,
        ifnull(sum(impressions), 0) as impressions,
        ifnull(sum(spend), 0) as spend
    from {{ ref('stg_ads__spend') }}
    where date between date '{{ var("start_date") }}' and date '{{ var("end_date") }}'
)

select mart.*, ads.clicks as expected_clicks, ads.impressions as expected_impressions,
    ads.spend as expected_spend
from mart
cross join ads
where mart.clicks is distinct from ads.clicks
    or mart.impressions is distinct from ads.impressions
    or mart.spend is distinct from ads.spend
