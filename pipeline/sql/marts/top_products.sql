-- Mart: product leaderboard by revenue, with category and units.
-- Built from completed orders only so it reflects realised sales.
CREATE OR REPLACE TABLE marts.top_products AS
WITH completed_items AS (
    SELECT oi.*
    FROM staging.stg_order_items oi
    JOIN marts.int_order_revenue o USING (order_id)
    WHERE o.is_completed
)
SELECT
    p.product_id,
    p.product_name,
    p.category,
    sum(ci.quantity)                              AS units_sold,
    count(DISTINCT ci.order_id)                   AS orders,
    CAST(sum(ci.line_revenue)      AS DECIMAL(14, 2)) AS revenue,
    CAST(sum(ci.line_gross_profit) AS DECIMAL(14, 2)) AS gross_profit,
    CAST(sum(ci.line_gross_profit) / NULLIF(sum(ci.line_revenue), 0) AS DECIMAL(6, 4)) AS margin_pct,
    row_number() OVER (ORDER BY sum(ci.line_revenue) DESC) AS revenue_rank
FROM completed_items ci
JOIN staging.stg_products p USING (product_id)
GROUP BY p.product_id, p.product_name, p.category
ORDER BY revenue DESC;
