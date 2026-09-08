with source as (

    select *
    from {{ source('raw', 'scada') }}

),

renamed as (

    select
        turbine_id,
        timestamp as timestamp_utc,
        wind_speed_ms,
        density_adjusted_wind_speed_ms,
        wind_direction_deg,
        nacelle_position_deg,
        power_kw,
        energy_export_kwh,
        potential_power_kw,
        rotor_speed_rpm,
        gearbox_speed_rpm,
        gear_oil_temperature_c,
        generator_bearing_front_temperature_c,
        nacelle_temperature_c,
        data_availability,
        source_file,
        ingested_at

    from source

)

select *
from renamed