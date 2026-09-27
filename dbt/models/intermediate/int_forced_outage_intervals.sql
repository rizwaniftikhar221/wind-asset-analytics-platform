with events as (

    select
        turbine_id,
        event_start_utc,
        event_end_utc

    from {{ ref('stg_turbine_events') }}

    where iec_category = 'Forced outage'
      and event_start_utc is not null
      and event_end_utc is not null
      and event_end_utc > event_start_utc

),

ordered_events as (

    select
        *,
        max(event_end_utc) over (
            partition by turbine_id
            order by event_start_utc, event_end_utc
            rows between unbounded preceding and 1 preceding
        ) as previous_max_end

    from events

),

marked_events as (

    select
        *,
        case
            when previous_max_end is null
              or event_start_utc > previous_max_end
            then 1
            else 0
        end as new_outage

    from ordered_events

),

grouped_events as (

    select
        *,
        sum(new_outage) over (
            partition by turbine_id
            order by event_start_utc, event_end_utc
            rows between unbounded preceding and current row
        ) as outage_group

    from marked_events

),

merged_intervals as (

    select
        turbine_id,
        outage_group,
        min(event_start_utc) as outage_start_utc,
        max(event_end_utc) as outage_end_utc,
        count(*) as source_event_count

    from grouped_events

    group by
        turbine_id,
        outage_group

)

select
    turbine_id,
    outage_group,
    outage_start_utc,
    outage_end_utc,

    datediff(
        'second',
        outage_start_utc,
        outage_end_utc
    ) / 3600.0 as outage_hours,

    source_event_count

from merged_intervals