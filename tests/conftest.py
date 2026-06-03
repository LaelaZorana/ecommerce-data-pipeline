"""Shared fixtures.

We build the marts two ways:

* ``fixture_con`` -- a hand-written, tiny dataset (a few rows) loaded into an
  in-memory DuckDB and run through the real staging+mart SQL. Because the inputs
  are known, the expected aggregates are known, so transform correctness can be
  asserted exactly.
* ``generated_settings`` -- a small *seeded* end-to-end run into a temp dir,
  used to assert pipeline-level invariants (reconciliation, gates passing).
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from pipeline import transform
from pipeline.config import Settings


@pytest.fixture()
def fixture_con() -> duckdb.DuckDBPyConnection:
    """In-memory warehouse seeded with a tiny, fully-known dataset."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA raw;")
    con.execute("CREATE SCHEMA staging;")
    con.execute("CREATE SCHEMA marts;")

    customers = pd.DataFrame(
        {
            "customer_id": [1, 2, 3],
            "signup_date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-10"]).date,
            "channel": ["organic", "Paid_Search", "email"],
            "country": ["us", "GB", "DE"],
        }
    )
    products = pd.DataFrame(
        {
            "product_id": [10, 20],
            "product_name": ["Widget", "Gadget"],
            "category": ["Home", "Electronics"],
            "unit_price": [100.00, 50.00],
            "unit_cost": [60.00, 20.00],
        }
    )
    # 3 orders: two completed (cust 1 in Jan, cust 1 in Feb), one refunded (cust 2).
    orders = pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "customer_id": [1, 1, 2],
            "order_ts": pd.to_datetime(["2024-01-10 09:00", "2024-02-15 12:00", "2024-01-25 15:00"]),
            "status": ["completed", "completed", "refunded"],
        }
    )
    # order 1: 2x Widget (200 rev) ; order 2: 1x Gadget (50 rev) ; order 3: 1x Widget (refunded)
    order_items = pd.DataFrame(
        {
            "order_item_id": [1, 2, 3],
            "order_id": [1, 2, 3],
            "product_id": [10, 20, 10],
            "quantity": [2, 1, 1],
            "unit_price": [100.00, 50.00, 100.00],
        }
    )
    # Funnel: one full purchase chain for order 1, one session abandoned at cart.
    events = pd.DataFrame(
        {
            "event_id": [1, 2, 3, 4, 5, 6],
            "session_id": [1, 1, 1, 1, 99, 99],
            "customer_id": [1, 1, 1, 1, 3, 3],
            "event_type": ["view", "add_to_cart", "checkout", "purchase", "view", "add_to_cart"],
            "event_ts": pd.to_datetime(
                [
                    "2024-01-10 08:30",
                    "2024-01-10 08:35",
                    "2024-01-10 08:40",
                    "2024-01-10 08:45",
                    "2024-03-01 10:00",
                    "2024-03-01 10:05",
                ]
            ),
        }
    )

    for name, df in {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "events": events,
    }.items():
        con.register(f"_{name}", df)
        con.execute(f"CREATE TABLE raw.{name} AS SELECT * FROM _{name};")
        con.unregister(f"_{name}")

    # Build all models against this fixture using the real SQL.
    settings = Settings()  # sql_dir resolves to the repo's pipeline/sql
    transform.run(con=con, settings=settings)
    yield con
    con.close()


@pytest.fixture()
def generated_settings(tmp_path) -> Settings:
    """Settings pointing at a temp dir, with a small deterministic dataset."""
    return Settings(
        raw_dir=tmp_path / "raw",
        warehouse_dir=tmp_path / "warehouse",
        seed=7,
        n_customers=300,
        n_orders=1500,
        n_products=40,
    )
