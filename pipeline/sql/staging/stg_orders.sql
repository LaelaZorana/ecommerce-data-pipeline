-- Staging: orders with split date/time parts for downstream rollups.
CREATE OR REPLACE VIEW staging.stg_orders AS
SELECT
    order_id,
    customer_id,
    CAST(order_ts AS TIMESTAMP)            AS order_ts,
    CAST(order_ts AS DATE)                 AS order_date,
    date_trunc('month', CAST(order_ts AS DATE)) AS order_month,
    lower(status)                          AS status,
    (lower(status) = 'completed')          AS is_completed
FROM raw.orders;
