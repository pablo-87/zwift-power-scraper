WITH daily_max AS (
    SELECT 
        zwid,
        event_date::date AS clean_date, 
        -- Get the highest power numbers for that specific calendar day
        MAX(w300) AS daily_w300,
        MAX(w1200) AS daily_w1200
    FROM 
        rider_events
    WHERE 
        zwid = 1714370 -- Replace with your specific rider ID
    GROUP BY 
        zwid, 
        event_date::date
),
rolling_metrics AS (
    SELECT 
        clean_date,
        -- Calculate the rolling 90-day peak leading up to each calendar date
        MAX(daily_w300) OVER (
            ORDER BY clean_date 
            RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
        ) AS max_w300_90d,
        
        MAX(daily_w1200) OVER (
            ORDER BY clean_date 
            RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
        ) AS max_w1200_90d
    FROM 
        daily_max
)
SELECT 
    clean_date AS event_date,
    max_w300_90d AS zmap_proxy,
    -- Apply the Critical Power formula and cast for rounding
    ROUND(
        ( ((max_w1200_90d * 1200.0) - (max_w300_90d * 300.0)) / 900.0 )::numeric, 
        1
    ) AS zftp_proxy
FROM 
    rolling_metrics
ORDER BY 
    event_date DESC