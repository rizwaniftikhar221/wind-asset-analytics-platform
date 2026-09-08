with source as (

    select *
    from {{ source('raw', 'asset_master') }}

),

renamed as (

    select
        turbine_id,
        turbine_name,
        wind_farm,
        manufacturer_identity,
        manufacturer,
        model,
        rated_power_kw,
        hub_height_m,
        rotor_diameter_m,
        latitude,
        longitude,
        elevation_m,
        country,
        commercial_operations_date,
        ingested_at

    from source

)

select *
from renamed