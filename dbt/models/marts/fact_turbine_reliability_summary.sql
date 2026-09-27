with daily as (

    select *
    from {{ ref('fact_turbine_daily_reliability') }}

),

outages as (

    select
        o.turbine_id,
        o.outage_start_utc,
        o.outage_end_utc,
        a.commercial_operations_date

    from {{ ref('int_forced_outage_intervals') }} o

    inner join {{ ref('stg_asset_master') }} a
        on o.turbine_id = a.turbine_id

    where o.outage_end_utc > a.commercial_operations_date

),

outage_summary as (

    select
        turbine_id,

        count(*) as completed_outage_count,

        avg(
            datediff(
                'second',
                greatest(
                    outage_start_utc,
                    commercial_operations_date::timestamp_ntz
                ),
                outage_end_utc
            ) / 3600.0
        ) as mttr_hours

    from outages

    group by turbine_id

),

daily_summary as (

    select
        turbine_id,

        sum(eligible_hours) as eligible_hours,

        sum(forced_outage_hours) as forced_outage_hours,

        sum(outage_starts) as outage_starts

    from daily

    group by turbine_id

)

select
    d.turbine_id,

    d.eligible_hours,
    d.forced_outage_hours,
    d.outage_starts,

    o.completed_outage_count,
    o.mttr_hours,

    1 - (
        d.forced_outage_hours
        / nullif(d.eligible_hours, 0)
    ) as forced_outage_availability,

    (
        d.eligible_hours - d.forced_outage_hours
    ) / nullif(o.completed_outage_count, 0)
        as mtbf_hours

from daily_summary d

left join outage_summary o
    on d.turbine_id = o.turbine_id