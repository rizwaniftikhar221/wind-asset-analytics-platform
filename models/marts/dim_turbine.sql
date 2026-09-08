select
    turbine_id,
    turbine_name,
    wind_farm,
    manufacturer,
    model,
    rated_power_kw,
    hub_height_m,
    rotor_diameter_m,
    latitude,
    longitude,
    country,
    commercial_operations_date
from {{ ref('stg_asset_master') }}