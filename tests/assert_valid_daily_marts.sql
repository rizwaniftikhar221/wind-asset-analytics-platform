with invalid_performance as (

    select turbine_id, performance_date
    from {{ ref('fact_turbine_daily_performance') }}
    group by turbine_id, performance_date
    having count(*) > 1

),

invalid_reliability as (

    select turbine_id, performance_date
    from {{ ref('fact_turbine_daily_reliability') }}
    group by turbine_id, performance_date
    having count(*) > 1

),

invalid_hours as (

    select turbine_id, performance_date
    from {{ ref('fact_turbine_daily_reliability') }}
    where forced_outage_hours < 0
       or forced_outage_hours > eligible_hours

)

select * from invalid_performance
union all
select * from invalid_reliability
union all
select * from invalid_hours