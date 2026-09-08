with source as (

    select *
    from {{ source('raw', 'weather') }}

),

renamed as (

    select
        timestamp as timestamp_utc,
        temperature_2m_c,
        surface_pressure_hpa,
        wind_speed_100m_ms,
        wind_direction_100m_deg,
        latitude,
        longitude,
        elevation_m,
        source as weather_source,
        ingested_at

    from source

)

select *
from renamed