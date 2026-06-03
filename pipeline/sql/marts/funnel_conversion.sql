-- Mart: funnel conversion across the view -> add_to_cart -> checkout -> purchase steps.
-- Sessions are counted at the deepest step they reached, then we report the count
-- reaching each step and the step-over-step + overall conversion rates.
CREATE OR REPLACE TABLE marts.funnel_conversion AS
WITH session_depth AS (
    SELECT session_id, max(funnel_step) AS max_step
    FROM staging.stg_events
    GROUP BY session_id
),
steps(step_name, step_index) AS (
    VALUES ('view', 1), ('add_to_cart', 2), ('checkout', 3), ('purchase', 4)
),
reached AS (
    SELECT
        s.step_name,
        s.step_index,
        count(*) FILTER (WHERE d.max_step >= s.step_index) AS sessions
    FROM steps s
    CROSS JOIN session_depth d
    GROUP BY s.step_name, s.step_index
)
SELECT
    step_name,
    step_index,
    sessions,
    CAST(sessions AS DOUBLE)
        / NULLIF(first_value(sessions) OVER (ORDER BY step_index), 0) AS pct_of_top,
    CAST(sessions AS DOUBLE)
        / NULLIF(lag(sessions) OVER (ORDER BY step_index), 0) AS step_conversion
FROM reached
ORDER BY step_index;
