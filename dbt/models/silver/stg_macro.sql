with src as (
    select
        as_of_date::date as as_of_date,
        series_id,
        value::double as value,
        ingest_date::date as ingest_date
    from {{ source('bronze', 'macro') }}
)

select
    as_of_date,
    series_id,
    value
from src
qualify row_number() over (
    partition by series_id, as_of_date
    order by ingest_date desc
) = 1
