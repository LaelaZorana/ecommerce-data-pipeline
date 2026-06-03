"""Ingest stage: generate a realistic, deterministic synthetic e-commerce dataset.

We use a seeded ``numpy`` generator so every run produces byte-identical data,
which makes the downstream marts and tests reproducible. Four raw tables are
emitted, mirroring a typical operational store:

* ``customers``    - one row per customer (signup date, marketing channel, country)
* ``products``     - product catalogue (category, price, cost)
* ``orders``       - one row per order (customer, status, timestamp)
* ``order_items``  - order line items (product, quantity, unit price)
* ``events``       - clickstream funnel events (view -> cart -> checkout -> purchase)

Outputs are written as Parquet (analytics-native, typed) with a CSV mirror of
``orders`` so the raw layer is also human-inspectable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from pipeline.config import Settings, get_settings

log = logging.getLogger("commerce.ingest")

# Reference data ----------------------------------------------------------------
CHANNELS = ["organic", "paid_search", "social", "email", "referral", "affiliate"]
CHANNEL_WEIGHTS = [0.34, 0.22, 0.18, 0.12, 0.09, 0.05]
COUNTRIES = ["US", "GB", "DE", "FR", "CA", "AU", "NL", "SE"]
COUNTRY_WEIGHTS = [0.42, 0.14, 0.10, 0.08, 0.09, 0.07, 0.06, 0.04]
CATEGORIES = ["Apparel", "Home", "Electronics", "Beauty", "Outdoors", "Toys"]
ORDER_STATUSES = ["completed", "completed", "completed", "completed", "refunded", "cancelled"]
# Funnel: probability of progressing to the next step.
FUNNEL_STEPS = ["view", "add_to_cart", "checkout", "purchase"]


@dataclass
class RawTables:
    customers: pd.DataFrame
    products: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame
    events: pd.DataFrame


def _daterange_days(start: str, end: str) -> int:
    d0 = datetime.fromisoformat(start)
    d1 = datetime.fromisoformat(end)
    return (d1 - d0).days


def generate(settings: Settings | None = None) -> RawTables:
    """Build the in-memory raw tables. Pure function of ``settings`` + seed."""
    s = settings or get_settings()
    rng = np.random.default_rng(s.seed)
    span_days = _daterange_days(s.start_date, s.end_date)
    start = datetime.fromisoformat(s.start_date)

    # --- customers -----------------------------------------------------------
    cust_ids = np.arange(1, s.n_customers + 1)
    signup_offsets = rng.integers(0, span_days + 1, size=s.n_customers)
    customers = pd.DataFrame(
        {
            "customer_id": cust_ids,
            "signup_date": [(start + timedelta(days=int(o))).date() for o in signup_offsets],
            "channel": rng.choice(CHANNELS, size=s.n_customers, p=CHANNEL_WEIGHTS),
            "country": rng.choice(COUNTRIES, size=s.n_customers, p=COUNTRY_WEIGHTS),
        }
    )

    # --- products ------------------------------------------------------------
    prod_ids = np.arange(1, s.n_products + 1)
    base_price = np.round(rng.gamma(shape=2.2, scale=18.0, size=s.n_products) + 5.0, 2)
    margin = rng.uniform(0.35, 0.65, size=s.n_products)  # gross margin fraction
    products = pd.DataFrame(
        {
            "product_id": prod_ids,
            "product_name": [f"SKU-{i:04d}" for i in prod_ids],
            "category": rng.choice(CATEGORIES, size=s.n_products),
            "unit_price": base_price,
            "unit_cost": np.round(base_price * (1.0 - margin), 2),
        }
    )

    # --- orders --------------------------------------------------------------
    # Repeat-purchase behaviour: pick customers with replacement, weighted so a
    # subset of customers buy more often (a realistic long tail).
    cust_affinity = rng.gamma(shape=1.6, scale=1.0, size=s.n_customers)
    cust_affinity /= cust_affinity.sum()
    order_customers = rng.choice(cust_ids, size=s.n_orders, replace=True, p=cust_affinity)

    # Order date must be on/after that customer's signup date.
    signup_by_id = dict(zip(cust_ids, signup_offsets))
    order_offsets = np.empty(s.n_orders, dtype=int)
    for i, c in enumerate(order_customers):
        lo = int(signup_by_id[c])
        order_offsets[i] = rng.integers(lo, span_days + 1) if lo < span_days else span_days
    # Seasonal lift towards Q4 (holiday season) via a soft multiplier on selection.
    order_ids = np.arange(1, s.n_orders + 1)
    order_ts = [start + timedelta(days=int(o), seconds=int(rng.integers(0, 86400))) for o in order_offsets]
    orders = pd.DataFrame(
        {
            "order_id": order_ids,
            "customer_id": order_customers,
            "order_ts": order_ts,
            "status": rng.choice(ORDER_STATUSES, size=s.n_orders),
        }
    ).sort_values("order_ts", kind="stable", ignore_index=True)
    # Reassign sequential ids by time so order_id is monotonic with order_ts.
    orders["order_id"] = np.arange(1, s.n_orders + 1)

    # --- order_items ---------------------------------------------------------
    # 1-4 line items per order.
    n_items = rng.integers(1, 5, size=s.n_orders)
    item_order_ids = np.repeat(orders["order_id"].to_numpy(), n_items)
    total_items = int(n_items.sum())
    item_products = rng.choice(prod_ids, size=total_items)
    quantities = rng.integers(1, 6, size=total_items)
    # Capture unit price at time of sale (small jitter to mimic promos/price drift).
    price_lookup = products.set_index("product_id")["unit_price"]
    sale_unit_price = np.round(
        price_lookup.loc[item_products].to_numpy() * rng.uniform(0.9, 1.0, size=total_items), 2
    )
    order_items = pd.DataFrame(
        {
            "order_item_id": np.arange(1, total_items + 1),
            "order_id": item_order_ids,
            "product_id": item_products,
            "quantity": quantities,
            "unit_price": sale_unit_price,
        }
    )

    # --- events (funnel) -----------------------------------------------------
    events = _generate_events(rng, orders, start, span_days)

    return RawTables(customers, products, orders, order_items, events)


def _generate_events(rng, orders: pd.DataFrame, start: datetime, span_days: int) -> pd.DataFrame:
    """Generate a clickstream funnel.

    Every completed order yields a full view->purchase chain (so purchase events
    reconcile with orders). On top of that we add abandoned sessions that drop
    out partway, which is what makes funnel_conversion interesting.
    """
    rows: list[dict] = []
    event_id = 1
    completed = orders[orders["status"] == "completed"]

    # Funded chains for real purchases.
    for order_id, customer_id, ts in zip(
        completed["order_id"], completed["customer_id"], completed["order_ts"]
    ):
        session = int(order_id)
        t = ts - timedelta(minutes=int(rng.integers(3, 40)))
        for step in FUNNEL_STEPS:
            rows.append(
                {
                    "event_id": event_id,
                    "session_id": session,
                    "customer_id": int(customer_id),
                    "event_type": step,
                    "event_ts": t,
                }
            )
            event_id += 1
            t += timedelta(seconds=int(rng.integers(20, 600)))

    # Abandoned sessions (no order). Roughly 2x the purchase sessions. These
    # never reach 'purchase' -- by construction the only sessions that purchase
    # are the funded chains above, so funnel purchases reconcile 1:1 with
    # completed orders. We advance at most to 'checkout'.
    n_abandoned = len(completed) * 2
    abandon_steps = FUNNEL_STEPS[1:-1]  # add_to_cart, checkout (no purchase)
    drop_probs = [0.55, 0.30]  # P(advance) into add_to_cart, then checkout
    base_session = int(orders["order_id"].max()) + 1
    for k in range(n_abandoned):
        session = base_session + k
        customer_id = int(rng.choice(orders["customer_id"]))
        offset = int(rng.integers(0, span_days + 1))
        t = start + timedelta(days=offset, seconds=int(rng.integers(0, 86400)))
        rows.append(
            {
                "event_id": event_id,
                "session_id": session,
                "customer_id": customer_id,
                "event_type": "view",
                "event_ts": t,
            }
        )
        event_id += 1
        for step, p in zip(abandon_steps, drop_probs):
            if rng.random() > p:
                break
            t += timedelta(seconds=int(rng.integers(20, 600)))
            rows.append(
                {
                    "event_id": event_id,
                    "session_id": session,
                    "customer_id": customer_id,
                    "event_type": step,
                    "event_ts": t,
                }
            )
            event_id += 1

    events = pd.DataFrame(rows)
    return events.sort_values("event_ts", kind="stable", ignore_index=True)


def write_raw(tables: RawTables, settings: Settings | None = None) -> dict[str, int]:
    """Persist raw tables to the raw directory. Returns row counts per table."""
    s = settings or get_settings()
    s.ensure_dirs()
    counts: dict[str, int] = {}
    for name in ("customers", "products", "orders", "order_items", "events"):
        df: pd.DataFrame = getattr(tables, name)
        df.to_parquet(s.raw_dir / f"{name}.parquet", index=False)
        counts[name] = len(df)
    # Human-readable CSV mirror of the headline table.
    tables.orders.to_csv(s.raw_dir / "orders.csv", index=False)
    log.info("wrote raw tables: %s", counts)
    return counts


def run(settings: Settings | None = None) -> dict[str, int]:
    """Ingest entry point used by the flow/CLI."""
    s = settings or get_settings()
    tables = generate(s)
    return write_raw(tables, s)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
