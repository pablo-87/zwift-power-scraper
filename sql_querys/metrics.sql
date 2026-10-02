WITH rider_max_date AS (
    SELECT MAX(event_date::date) AS latest_event
    FROM rider_events
    WHERE zwid = 1714370
)
SELECT 
    e.zwid,
    MAX(e.w300) AS zmap_proxy,
    ROUND(
        ( ((MAX(e.w1200) * 1200.0) - (MAX(e.w300) * 300.0)) / 900.0 )::numeric, 
        1
    ) AS zftp_proxy
FROM 
    rider_events e
CROSS JOIN 
    rider_max_date m
WHERE 
    e.zwid = 1714370 
    AND e.event_date::date >= m.latest_event - INTERVAL '90 days'
GROUP BY 
    e.zwid