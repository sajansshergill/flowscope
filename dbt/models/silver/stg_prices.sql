with src as (
    select
        as_of_date::date as as_of_date,
        upper(ticker) as ticker,
        open::double as open,
        high::double as high,
        low::double as low,
        close::double as close,
        volume::bigint as volume,
        source,
        ingest_date::date as ingest_date
    from {{ source('bronze', 'prices') }}
)

select
    as_of_date,
    ticker,
    open,
    high,
    low,
    close,
    volume,
    close / nullif(
        lag(close) over (partition by ticker order by as_of_date),
        0
    ) - 1 as daily_return,
    source
from src
qualify row_number() over (
    partition by ticker, as_of_date
    order by ingest_date desc
) = 1
