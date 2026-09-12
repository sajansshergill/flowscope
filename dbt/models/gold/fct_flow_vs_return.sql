select
    f.as_of_date,
    f.ticker,
    f.sector,
    f.theme,
    f.net_flow,
    p.daily_return,
    p.close
from {{ ref('fct_etf_daily_flows') }} as f
left join {{ ref('stg_prices') }} as p
    on f.ticker = p.ticker
    and f.as_of_date = p.as_of_date
