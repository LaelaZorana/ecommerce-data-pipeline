-- Staging: order line items with computed line revenue and cost.
CREATE OR REPLACE VIEW staging.stg_order_items AS
SELECT
    oi.order_item_id,
    oi.order_id,
    oi.product_id,
    oi.quantity,
    CAST(oi.unit_price AS DECIMAL(10, 2))                          AS unit_price,
    CAST(oi.unit_price * oi.quantity AS DECIMAL(12, 2))            AS line_revenue,
    CAST(p.unit_cost * oi.quantity AS DECIMAL(12, 2))             AS line_cost,
    CAST((oi.unit_price - p.unit_cost) * oi.quantity AS DECIMAL(12, 2)) AS line_gross_profit
FROM raw.order_items oi
JOIN staging.stg_products p USING (product_id);
