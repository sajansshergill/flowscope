-- Clean, dedupe, type issuer landings and compute shares-outstanding deltas.

with src as (
    select
        as_of_date::date as as_of_date,
        upper(ticker) as ticker,
        shares_outstanding::double as shares_outstanding,
        nav::double as nav,
        source,
        ingest_date::date as ingest_date
    from {{ source('bronze', 'issuer_daily') }}
),

latest as (
    select *
    from src
    qualify row_number() over (
        partition by ticker, as_of_date
        order by ingest_date desc
    ) = 1
)

select
    as_of_date,
    ticker,
    shares_outstanding,
    nav,
    shares_outstanding - lag(shares_outstanding) over (
        partition by ticker
        order by as_of_date
    ) as shares_delta,
    source
from latest
