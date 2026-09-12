-- Rolling sector rotation: net flow this window vs prior window.

with windows as (
    select
        as_of_date,
        sector,
        net_flow,
        sum(net_flow) over (
            partition by sector
            order by as_of_date
            rows between 20 preceding and current row
        ) as flow_20d,
        sum(net_flow) over (
            partition by sector
            order by as_of_date
            rows between 40 preceding and 21 preceding
        ) as flow_prior_20d
    from {{ ref('agg_sector_flows') }}
)

select
    as_of_date,
    sector,
    net_flow,
    flow_20d,
    flow_prior_20d,
    flow_20d - coalesce(flow_prior_20d, 0) as rotation_delta
from windows
