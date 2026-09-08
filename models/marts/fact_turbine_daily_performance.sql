with scada as (

    select *
    from {{ ref('int_scada_enriched') }}

),

daily as (

    select
        turbine_id,
        cast(timestamp_utc as date) as performance_date,

        max(turbine_name) as turbine_name,
        max(wind_farm) as wind_farm,
        max(rated_power_kw) as rated_power_kw,

        -- Count the intervals that belong to this day.
        count(*) as total_intervals,

        count_if(
            is_commercial_operation
        ) as commercial_intervals,

        count_if(
            is_commercial_operation
            and data_availability = 1
            and power_kw is not null
        ) as valid_power_intervals,

        -- Use recorded export energy as the actual production measure.
        sum(
            case
                when is_commercial_operation
                     and data_availability = 1
                     and energy_export_kwh is not null
                then energy_export_kwh
                else 0
            end
        ) as actual_energy_kwh,

        -- Estimate energy from average power for reconciliation.
        sum(
            case
                when is_commercial_operation
                     and data_availability = 1
                     and power_kw is not null
                then power_kw / 6.0
                else 0
            end
        ) as calculated_energy_kwh,

        -- Convert the default power curve estimate into interval energy.
        sum(
            case
                when is_commercial_operation
                     and data_availability = 1
                     and potential_power_kw is not null
                then potential_power_kw / 6.0
                else 0
            end
        ) as expected_energy_kwh,

        -- Average wind speed only across eligible, available intervals.
        avg(
            case
                when is_commercial_operation
                     and data_availability = 1
                then wind_speed_ms
            end
        ) as avg_wind_speed_ms

    from scada

    group by
        turbine_id,
        cast(timestamp_utc as date)

)

select
    turbine_id,
    performance_date,
    turbine_name,
    wind_farm,
    rated_power_kw,

    total_intervals,
    commercial_intervals,
    valid_power_intervals,

    commercial_intervals / 6.0 as eligible_hours,
    valid_power_intervals / 6.0 as valid_power_hours,

    valid_power_intervals
        / nullif(commercial_intervals, 0)
        as power_data_coverage,

    actual_energy_kwh,
    actual_energy_kwh / 1000.0 as actual_energy_mwh,

    calculated_energy_kwh,
    calculated_energy_kwh / 1000.0 as calculated_energy_mwh,

    expected_energy_kwh,
    expected_energy_kwh / 1000.0 as expected_energy_mwh,

    actual_energy_kwh - expected_energy_kwh
        as energy_variance_kwh,

    (actual_energy_kwh - expected_energy_kwh) / 1000.0
        as energy_variance_mwh,

    (actual_energy_kwh - expected_energy_kwh)
        / nullif(expected_energy_kwh, 0)
        as energy_variance_pct,

    avg_wind_speed_ms,

    actual_energy_kwh
        / nullif(
            rated_power_kw * commercial_intervals / 6.0,
            0
        ) as capacity_factor

from daily