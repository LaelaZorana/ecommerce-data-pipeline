-- Mart: monthly cohort retention.
-- A customer's cohort is their signup month. For each cohort we measure how many
-- customers placed a completed order N months later (month_number = 0,1,2,...).
CREATE OR REPLACE TABLE marts.customer_cohort_retention AS
WITH cohorts AS (
    SELECT customer_id, signup_month AS cohort_month
    FROM staging.stg_customers
),
-- Distinct active months per customer (from completed orders).
activity AS (
    SELECT DISTINCT customer_id, order_month AS activity_month
    FROM marts.int_order_revenue
    WHERE is_completed
),
cohort_size AS (
    SELECT cohort_month, count(*) AS cohort_customers
    FROM cohorts
    GROUP BY cohort_month
),
retained AS (
    SELECT
        c.cohort_month,
        -- whole months between signup and activity
        (date_diff('month', c.cohort_month, a.activity_month)) AS month_number,
        count(DISTINCT c.customer_id) AS active_customers
    FROM cohorts c
    JOIN activity a USING (customer_id)
    WHERE a.activity_month >= c.cohort_month
    GROUP BY c.cohort_month, month_number
)
SELECT
    r.cohort_month,
    r.month_number,
    s.cohort_customers,
    r.active_customers,
    CAST(r.active_customers AS DOUBLE) / NULLIF(s.cohort_customers, 0) AS retention_rate
FROM retained r
JOIN cohort_size s USING (cohort_month)
ORDER BY r.cohort_month, r.month_number;
