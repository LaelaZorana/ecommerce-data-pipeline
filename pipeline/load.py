"""Load stage: register the raw Parquet files into a DuckDB warehouse.

We load into a ``raw`` schema with explicit ``CREATE TABLE AS SELECT`` so the
warehouse is materialised (self-contained, queryable with the DuckDB CLI, and
safe to ship to the dashboard) rather than relying on live file scans.
"""

from __future__ import annotations

import logging

import duckdb

from pipeline.config import Settings, get_settings

log = logging.getLogger("commerce.load")

RAW_TABLES = ("customers", "products", "orders", "order_items", "events")


def connect(settings: Settings | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a connection to the warehouse database."""
    s = settings or get_settings()
    s.ensure_dirs()
    return duckdb.connect(str(s.db_path), read_only=read_only)


def run(con: duckdb.DuckDBPyConnection | None = None, settings: Settings | None = None) -> dict[str, int]:
    """Load all raw Parquet files into ``raw.*`` tables. Returns row counts."""
    s = settings or get_settings()
    owns_con = con is None
    con = con or connect(s)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        counts: dict[str, int] = {}
        for name in RAW_TABLES:
            path = s.raw_dir / f"{name}.parquet"
            if not path.exists():
                raise FileNotFoundError(
                    f"raw table {name!r} not found at {path} - run the ingest stage first"
                )
            con.execute(f"CREATE OR REPLACE TABLE raw.{name} AS SELECT * FROM read_parquet(?);", [str(path)])
            counts[name] = con.execute(f"SELECT count(*) FROM raw.{name};").fetchone()[0]
        log.info("loaded raw tables into DuckDB: %s", counts)
        return counts
    finally:
        if owns_con:
            con.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
