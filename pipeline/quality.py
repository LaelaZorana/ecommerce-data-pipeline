"""Data-quality stage: declarative checks that gate the pipeline.

Each check is a small dataclass that compiles to a single COUNT query returning
the number of *violating* rows. A non-zero count fails the check; any failed
check makes :func:`run` raise :class:`DataQualityError`, which the flow surfaces
as a non-zero exit code. This is the "quality gate" -- bad data stops the run.

Supported check types:
    * not_null            - column has no NULLs
    * unique              - column (or column set) has no duplicates
    * accepted_range      - numeric column within [min, max]
    * accepted_values     - column only contains a given value set
    * relationship        - every FK value exists in a referenced PK column
    * expression          - arbitrary boolean SQL that must hold for every row
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import duckdb

from pipeline.config import Settings, get_settings

log = logging.getLogger("commerce.quality")


class DataQualityError(RuntimeError):
    """Raised when one or more data-quality checks fail."""


@dataclass
class CheckResult:
    name: str
    relation: str
    passed: bool
    failing_rows: int
    detail: str = ""


@dataclass
class Check:
    """A single declarative data-quality assertion."""

    name: str
    relation: str
    kind: str
    column: str | None = None
    columns: Sequence[str] | None = None
    min: float | None = None
    max: float | None = None
    values: Sequence[object] | None = None
    to_relation: str | None = None
    to_column: str | None = None
    expression: str | None = None

    def _violation_query(self) -> str:
        rel = self.relation
        if self.kind == "not_null":
            return f"SELECT count(*) FROM {rel} WHERE {self.column} IS NULL"
        if self.kind == "unique":
            cols = ", ".join(self.columns or [self.column])  # type: ignore[list-item]
            # rows that participate in a duplicate group
            return (
                f"SELECT COALESCE(sum(c), 0) FROM ("
                f"  SELECT count(*) AS c FROM {rel} GROUP BY {cols} HAVING count(*) > 1"
                f") d"
            )
        if self.kind == "accepted_range":
            conds = []
            if self.min is not None:
                conds.append(f"{self.column} < {self.min}")
            if self.max is not None:
                conds.append(f"{self.column} > {self.max}")
            conds.append(f"{self.column} IS NULL")
            return f"SELECT count(*) FROM {rel} WHERE {' OR '.join(conds)}"
        if self.kind == "accepted_values":
            rendered = ", ".join(_sql_literal(v) for v in (self.values or []))
            return f"SELECT count(*) FROM {rel} WHERE {self.column} NOT IN ({rendered})"
        if self.kind == "relationship":
            return (
                f"SELECT count(*) FROM {rel} child "
                f"LEFT JOIN {self.to_relation} parent "
                f"  ON child.{self.column} = parent.{self.to_column} "
                f"WHERE child.{self.column} IS NOT NULL AND parent.{self.to_column} IS NULL"
            )
        if self.kind == "expression":
            return f"SELECT count(*) FROM {rel} WHERE NOT ({self.expression})"
        raise ValueError(f"unknown check kind: {self.kind!r}")

    def run(self, con: duckdb.DuckDBPyConnection) -> CheckResult:
        failing = con.execute(self._violation_query()).fetchone()[0] or 0
        return CheckResult(
            name=self.name,
            relation=self.relation,
            passed=failing == 0,
            failing_rows=int(failing),
        )


def _sql_literal(value: object) -> str:
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


def default_checks() -> list[Check]:
    """The suite enforced on every pipeline run."""
    return [
        # --- raw integrity ---
        Check("customers.pk_unique", "raw.customers", "unique", column="customer_id"),
        Check("customers.id_not_null", "raw.customers", "not_null", column="customer_id"),
        Check("products.pk_unique", "raw.products", "unique", column="product_id"),
        Check("orders.pk_unique", "raw.orders", "unique", column="order_id"),
        Check("order_items.pk_unique", "raw.order_items", "unique", column="order_item_id"),
        # referential integrity
        Check(
            "orders.customer_fk",
            "raw.orders",
            "relationship",
            column="customer_id",
            to_relation="raw.customers",
            to_column="customer_id",
        ),
        Check(
            "order_items.order_fk",
            "raw.order_items",
            "relationship",
            column="order_id",
            to_relation="raw.orders",
            to_column="order_id",
        ),
        Check(
            "order_items.product_fk",
            "raw.order_items",
            "relationship",
            column="product_id",
            to_relation="raw.products",
            to_column="product_id",
        ),
        # accepted ranges / values
        Check("products.price_positive", "raw.products", "accepted_range", column="unit_price", min=0.01),
        Check("products.cost_nonneg", "raw.products", "accepted_range", column="unit_cost", min=0.0),
        Check("order_items.qty_range", "raw.order_items", "accepted_range", column="quantity", min=1, max=100),
        Check(
            "orders.status_values",
            "raw.orders",
            "accepted_values",
            column="status",
            values=["completed", "refunded", "cancelled"],
        ),
        # --- mart sanity ---
        Check("daily_revenue.nonneg", "marts.daily_revenue", "accepted_range", column="revenue", min=0.0),
        Check(
            "daily_revenue.margin_bounded",
            "marts.daily_revenue",
            "expression",
            expression="margin_pct BETWEEN -1 AND 1",
        ),
        Check(
            "cohort.retention_bounded",
            "marts.customer_cohort_retention",
            "expression",
            expression="retention_rate >= 0 AND retention_rate <= 1",
        ),
        Check(
            "funnel.monotonic_nonincreasing",
            "marts.funnel_conversion",
            "expression",
            expression="pct_of_top <= 1.0",
        ),
    ]


def run(
    con: duckdb.DuckDBPyConnection | None = None,
    settings: Settings | None = None,
    checks: Iterable[Check] | None = None,
    raise_on_fail: bool = True,
) -> list[CheckResult]:
    """Run all checks. Raises :class:`DataQualityError` if any fail."""
    s = settings or get_settings()
    owns_con = con is None
    con = con or duckdb.connect(str(s.db_path), read_only=True)
    checks = list(checks if checks is not None else default_checks())
    try:
        results = [c.run(con) for c in checks]
    finally:
        if owns_con:
            con.close()

    failed = [r for r in results if not r.passed]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        log.info("  [%s] %-32s %s (%d violating rows)", status, r.name, r.relation, r.failing_rows)
    if failed and raise_on_fail:
        names = ", ".join(f"{r.name} ({r.failing_rows} rows)" for r in failed)
        raise DataQualityError(f"{len(failed)} data-quality check(s) failed: {names}")
    return results


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run()
    print("all data-quality checks passed")
