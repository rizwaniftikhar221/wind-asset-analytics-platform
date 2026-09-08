with source as (

    select *
    from {{ source('raw', 'turbine_events') }}

),

renamed as (

    select
        turbine_id,
        event_start as event_start_utc,
        event_end as event_end_utc,
        duration as source_duration,
        duration_seconds,
        duration_hours,
        status,
        event_code,
        message,
        comment,
        service_contract_category,
        iec_category,
        source_file,
        ingested_at

    from source

)

select *
from renamed