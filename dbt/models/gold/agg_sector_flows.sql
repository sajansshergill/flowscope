select
    as_of_date,
    sector,
    sum(net_flow) as net_flow,
    count(distinct ticker) as etf_count
from {{ ref('fct_etf_daily_flows') }}
group by 1, 2
