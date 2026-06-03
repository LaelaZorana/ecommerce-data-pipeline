"""Transform stage: build staging views and mart tables from SQL files.

The SQL lives in ``pipeline/sql`` and is executed in a deterministic, dependency
-aware order. Keeping the transformation in plain ``.sql`` files (rather than
inline strings) means the models read like a dbt project and can be inspected or
run by hand with the DuckDB CLI.
"""

from __future__ import annotations

import logging

import duckdb

from pipeline.config import Settings, get_settings

log = logging.getLogger("commerce.transform")

# Execution order. Staging first (views over raw), then the intermediate model,
# then the marts (which may depend on the intermediate model and each other-free).
STAGING_MODELS = [
    "staging/stg_customers.sql",
    "staging/stg_products.sql",
    "staging/stg_orders.sql",
    "staging/stg_order_items.sql",
    "staging/stg_events.sql",
]
MART_MODELS = [
    "marts/int_order_revenue.sql",  # intermediate; must precede the marts below
    "marts/daily_revenue.sql",
    "marts/top_products.sql",
    "marts/customer_cohort_retention.sql",
    "marts/funnel_conversion.sql",
]


def _run_model(con: duckdb.DuckDBPyConnection, sql_dir, rel_path: str) -> None:
    path = sql_dir / rel_path
    sql = path.read_text(encoding="utf-8")
    log.info("building model %s", rel_path)
    con.execute(sql)


def run(con: duckdb.DuckDBPyConnection | None = None, settings: Settings | None = None) -> list[str]:
    """Execute all models. Returns the list of mart relation names built."""
    s = settings or get_settings()
    owns_con = con is None
    con = con or duckdb.connect(str(s.db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS staging;")
        con.execute("CREATE SCHEMA IF NOT EXISTS marts;")
        for model in STAGING_MODELS:
            _run_model(con, s.sql_dir, model)
        for model in MART_MODELS:
            _run_model(con, s.sql_dir, model)

        marts = [
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts' ORDER BY table_name;"
            ).fetchall()
        ]
        log.info("built marts: %s", marts)
        return marts
    finally:
        if owns_con:
            con.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
