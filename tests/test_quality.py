"""Data-quality gate: passes on clean data, catches injected bad rows."""

from __future__ import annotations

import pytest

from pipeline import quality
from pipeline.quality import Check, DataQualityError


def test_all_checks_pass_on_clean_fixture(fixture_con):
    results = quality.run(con=fixture_con, raise_on_fail=False)
    failed = [r for r in results if not r.passed]
    assert failed == [], f"unexpected failures: {[r.name for r in failed]}"


def test_injected_duplicate_pk_is_caught(fixture_con):
    # Duplicate an order_id -> the unique check must fail with >0 rows.
    fixture_con.execute(
        "INSERT INTO raw.orders SELECT * FROM raw.orders WHERE order_id = 1;"
    )
    check = Check("orders.pk_unique", "raw.orders", "unique", column="order_id")
    result = check.run(fixture_con)
    assert not result.passed
    assert result.failing_rows >= 2  # both rows of the dup group count


def test_injected_orphan_fk_is_caught(fixture_con):
    # An order_item referencing a non-existent product violates referential integrity.
    fixture_con.execute(
        "INSERT INTO raw.order_items VALUES (999, 1, 7777, 1, 10.0);"
    )
    check = Check(
        "order_items.product_fk",
        "raw.order_items",
        "relationship",
        column="product_id",
        to_relation="raw.products",
        to_column="product_id",
    )
    result = check.run(fixture_con)
    assert not result.passed
    assert result.failing_rows == 1


def test_injected_out_of_range_value_is_caught(fixture_con):
    fixture_con.execute(
        "INSERT INTO raw.order_items VALUES (998, 1, 10, -5, 10.0);"  # negative quantity
    )
    check = Check("order_items.qty_range", "raw.order_items", "accepted_range", column="quantity", min=1, max=100)
    result = check.run(fixture_con)
    assert not result.passed
    assert result.failing_rows == 1


def test_injected_null_is_caught(fixture_con):
    fixture_con.execute("INSERT INTO raw.customers VALUES (NULL, NULL, 'organic', 'US');")
    check = Check("customers.id_not_null", "raw.customers", "not_null", column="customer_id")
    result = check.run(fixture_con)
    assert not result.passed
    assert result.failing_rows == 1


def test_injected_bad_status_is_caught(fixture_con):
    fixture_con.execute(
        "INSERT INTO raw.orders VALUES (500, 1, TIMESTAMP '2024-06-01 10:00', 'returned');"
    )
    check = Check(
        "orders.status_values",
        "raw.orders",
        "accepted_values",
        column="status",
        values=["completed", "refunded", "cancelled"],
    )
    result = check.run(fixture_con)
    assert not result.passed
    assert result.failing_rows == 1


def test_run_raises_on_failure(fixture_con):
    bad = [Check("force.fail", "raw.customers", "expression", expression="customer_id < 0")]
    with pytest.raises(DataQualityError) as exc:
        quality.run(con=fixture_con, checks=bad, raise_on_fail=True)
    assert "force.fail" in str(exc.value)


def test_default_suite_has_all_check_kinds():
    kinds = {c.kind for c in quality.default_checks()}
    assert {"not_null", "unique", "accepted_range", "accepted_values", "relationship", "expression"} <= kinds
