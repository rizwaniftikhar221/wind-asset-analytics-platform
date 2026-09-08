with scada as (

    select *
    from {{ ref('stg_scada') }}

),

assets as (

    select *
    from {{ ref('stg_asset_master') }}

),

enriched as (

    select
        s.turbine_id,
        s.timestamp_utc,

        a.turbine_name,
        a.wind_farm,
        a.rated_power_kw,
        a.commercial_operations_date,

        s.wind_speed_ms,
        s.power_kw,
        s.energy_export_kwh,
        s.potential_power_kw,
        s.data_availability,

        case
            when cast(s.timestamp_utc as date)
                 >= a.commercial_operations_date
            then true
            else false
        end as is_commercial_operation

    from scada s

    left join assets a
        on s.turbine_id = a.turbine_id

)

select *
from enriched