-- Mart: daily revenue and order KPIs from completed orders.
-- Refunded/cancelled orders are excluded from revenue but counted separately.
CREATE OR REPLACE TABLE marts.daily_revenue AS
WITH completed AS (
    SELECT * FROM marts.int_order_revenue WHERE is_completed
),
by_day AS (
    SELECT
        order_date,
        count(*)                          AS orders,
        count(DISTINCT customer_id)       AS customers,
        sum(n_items)                      AS units_sold,
        CAST(sum(gross_revenue) AS DECIMAL(14, 2)) AS revenue,
        CAST(sum(gross_profit)  AS DECIMAL(14, 2)) AS gross_profit
    FROM completed
    GROUP BY order_date
)
SELECT
    order_date,
    orders,
    customers,
    units_sold,
    revenue,
    gross_profit,
    CAST(revenue / NULLIF(orders, 0) AS DECIMAL(12, 2)) AS avg_order_value,
    CAST(gross_profit / NULLIF(revenue, 0) AS DECIMAL(6, 4)) AS margin_pct
FROM by_day
ORDER BY order_date;
