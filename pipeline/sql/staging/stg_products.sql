-- Staging: products with a derived unit gross margin.
CREATE OR REPLACE VIEW staging.stg_products AS
SELECT
    product_id,
    product_name,
    category,
    CAST(unit_price AS DECIMAL(10, 2)) AS unit_price,
    CAST(unit_cost AS DECIMAL(10, 2))  AS unit_cost,
    CAST(unit_price - unit_cost AS DECIMAL(10, 2)) AS unit_margin
FROM raw.products;
