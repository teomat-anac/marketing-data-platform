-- One row per day × channel × campaign of ad cost, typed. For a real ad platform this is
-- the one model to change: e.g. Google Ads reports cost in micros (cost_micros / 1e6).
select
    date,
    channel,
    campaign,
    impressions,
    clicks,
    cast(spend as numeric) as spend,
    loaded_at
from {{ source('ads', 'ad_spend') }}
