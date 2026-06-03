-- Staging: funnel events normalised to an ordinal step index.
CREATE OR REPLACE VIEW staging.stg_events AS
SELECT
    event_id,
    session_id,
    customer_id,
    lower(event_type) AS event_type,
    CASE lower(event_type)
        WHEN 'view'        THEN 1
        WHEN 'add_to_cart' THEN 2
        WHEN 'checkout'    THEN 3
        WHEN 'purchase'    THEN 4
        ELSE 0
    END               AS funnel_step,
    CAST(event_ts AS TIMESTAMP) AS event_ts
FROM raw.events;
