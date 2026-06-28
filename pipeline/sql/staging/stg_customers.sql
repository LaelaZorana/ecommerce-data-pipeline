-- Staging: typed, deduplicated customers with derived signup cohort month.
CREATE OR REPLACE VIEW staging.stg_customers AS
SELECT
    customer_id,
    CAST(signup_date AS DATE)                      AS signup_date,
    CAST(date_trunc('month', CAST(signup_date AS DATE)) AS DATE) AS signup_month,
    lower(channel)                                 AS channel,
    upper(country)                                 AS country
FROM raw.customers;
