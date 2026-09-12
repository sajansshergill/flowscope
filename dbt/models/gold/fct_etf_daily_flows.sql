-- Daily net flows per ETF: Δ(shares outstanding) × NAV.

select
    i.as_of_date,
    i.ticker,
    u.name,
    u.issuer,
    u.sector,
    u.theme,
    i.shares_outstanding,
    i.shares_delta,
    i.nav,
    i.shares_delta * i.nav as net_flow
from {{ ref('stg_issuer_daily') }} as i
left join {{ source('bronze', 'etf_universe') }} as u
    on i.ticker = u.ticker
where i.shares_delta is not null
