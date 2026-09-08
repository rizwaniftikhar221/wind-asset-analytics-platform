with outages as (

    select *
    from {{ ref('int_forced_outage_intervals') }}

),

assets as (

    select
        turbine_id,
        commercial_operations_date
    from {{ ref('stg_asset_master') }}

),

days as (

    select distinct
        performance_date
    from {{ ref('fact_turbine_daily_performance') }}

),

outage_days as (

    select
        o.turbine_id,
        d.performance_date,

        greatest(
            o.outage_start_utc,
            a.commercial_operations_date::timestamp_ntz,
            d.performance_date::timestamp_ntz
        ) as interval_start,

        least(
            o.outage_end_utc,
            dateadd(
                day,
                1,
                d.performance_date::timestamp_ntz
            )
        ) as interval_end,

        o.outage_start_utc

    from outages o

    inner join assets a
        on o.turbine_id = a.turbine_id

    inner join days d
        on d.performance_date >= cast(o.outage_start_utc as date)
       and d.performance_date <= cast(o.outage_end_utc as date)

),

daily as (

    select
        turbine_id,
        performance_date,

        sum(
            case
                when interval_end > interval_start
                then datediff(
                    'second',
                    interval_start,
                    interval_end
                ) / 3600.0
                else 0
            end
        ) as forced_outage_hours,

        count_if(
            outage_start_utc >= performance_date::timestamp_ntz
            and outage_start_utc < dateadd(
                day,
                1,
                performance_date::timestamp_ntz
            )
            and interval_end > interval_start
        ) as outage_starts

    from outage_days

    group by
        turbine_id,
        performance_date

)

select
    p.turbine_id,
    p.performance_date,

    coalesce(d.forced_outage_hours, 0)
        as forced_outage_hours,

    coalesce(d.outage_starts, 0)
        as outage_starts,

    p.eligible_hours,

    case
        when p.eligible_hours > 0
        then 1 - (
            coalesce(d.forced_outage_hours, 0)
            / p.eligible_hours
        )
        else null
    end as forced_outage_availability

from {{ ref('fact_turbine_daily_performance') }} p

left join daily d
    on p.turbine_id = d.turbine_id
   and p.performance_date = d.performance_date