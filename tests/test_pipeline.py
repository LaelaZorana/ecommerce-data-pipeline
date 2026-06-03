"""End-to-end pipeline: determinism, reconciliation, and gate enforcement."""

from __future__ import annotations

import duckdb
import pytest

from pipeline import ingest, quality
from pipeline.flow import run_pipeline
from pipeline.quality import DataQualityError


def test_pipeline_runs_end_to_end(generated_settings):
    summary = run_pipeline(generated_settings)
    assert summary.quality_failed == 0
    assert summary.quality_passed > 0
    assert set(summary.raw_counts) == {"customers", "products", "orders", "order_items", "events"}
    assert summary.raw_counts["orders"] == generated_settings.n_orders
    # All four headline marts plus the intermediate model exist.
    for mart in ("daily_revenue", "top_products", "customer_cohort_retention", "funnel_conversion"):
        assert mart in summary.marts


def test_ingest_is_deterministic(generated_settings):
    a = ingest.generate(generated_settings)
    b = ingest.generate(generated_settings)
    # Same seed -> identical frames.
    for name in ("customers", "products", "orders", "order_items", "events"):
        assert getattr(a, name).equals(getattr(b, name)), f"{name} not deterministic"


def test_funnel_purchases_reconcile_with_completed_orders(generated_settings):
    run_pipeline(generated_settings)
    con = duckdb.connect(str(generated_settings.db_path), read_only=True)
    try:
        completed = con.execute("SELECT count(*) FROM raw.orders WHERE status='completed'").fetchone()[0]
        purchases = con.execute(
            "SELECT sessions FROM marts.funnel_conversion WHERE step_name='purchase'"
        ).fetchone()[0]
        assert completed == purchases
    finally:
        con.close()


def test_revenue_reconciles_with_line_items(generated_settings):
    run_pipeline(generated_settings)
    con = duckdb.connect(str(generated_settings.db_path), read_only=True)
    try:
        mart_total = con.execute("SELECT sum(revenue) FROM marts.daily_revenue").fetchone()[0]
        direct = con.execute(
            "SELECT sum(oi.unit_price * oi.quantity) "
            "FROM raw.order_items oi JOIN raw.orders o USING(order_id) "
            "WHERE o.status = 'completed'"
        ).fetchone()[0]
        assert abs(float(mart_total) - float(direct)) < 1e-6
    finally:
        con.close()


def test_pipeline_fails_closed_on_bad_data(generated_settings, monkeypatch):
    """If a quality gate fails, the whole pipeline must raise (fail closed)."""
    real_run = quality.run

    def _inject_failure(*args, **kwargs):
        con = kwargs.get("con") or (args[0] if args else None)
        if con is not None:
            # Corrupt referential integrity after the marts are built.
            con.execute("INSERT INTO raw.order_items VALUES (10_000_000, 1, 424242, 1, 1.0);")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(quality, "run", _inject_failure)
    with pytest.raises(DataQualityError):
        run_pipeline(generated_settings)
