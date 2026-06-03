-- Intermediate: one row per order with rolled-up revenue/profit from its items.
-- Shared by several marts, so we materialise it as a table.
CREATE OR REPLACE TABLE marts.int_order_revenue AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_date,
    o.order_month,
    o.status,
    o.is_completed,
    COALESCE(i.n_items, 0)            AS n_items,
    COALESCE(i.gross_revenue, 0)      AS gross_revenue,
    COALESCE(i.gross_profit, 0)       AS gross_profit
FROM staging.stg_orders o
LEFT JOIN (
    SELECT
        order_id,
        sum(quantity)          AS n_items,
        sum(line_revenue)      AS gross_revenue,
        sum(line_gross_profit) AS gross_profit
    FROM staging.stg_order_items
    GROUP BY order_id
) i USING (order_id);
