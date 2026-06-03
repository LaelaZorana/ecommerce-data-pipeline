"""Orchestration: run the full pipeline ingest -> load -> transform -> quality.

This is a plain, dependency-free DAG runner. Each stage is a function returning
a small summary; the flow threads a single DuckDB connection through load,
transform, and quality so they operate on the same warehouse transaction-side.

If `prefect` is installed, ``pipeline.orchestrate`` exposes the same DAG as a
Prefect flow for schedulable/observable runs -- but it is entirely optional and
the project runs end to end without it.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from pipeline import ingest, load, quality, transform
from pipeline.config import Settings, get_settings
from pipeline.load import connect

log = logging.getLogger("commerce.flow")


@dataclass
class RunSummary:
    raw_counts: dict[str, int] = field(default_factory=dict)
    loaded_counts: dict[str, int] = field(default_factory=dict)
    marts: list[str] = field(default_factory=list)
    quality_passed: int = 0
    quality_failed: int = 0
    seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render(self) -> str:
        lines = [
            "=" * 60,
            "  CommercePipeline run summary",
            "=" * 60,
            f"  raw rows written : {sum(self.raw_counts.values()):,}",
        ]
        for name, n in self.raw_counts.items():
            lines.append(f"      - {name:<12} {n:>10,}")
        lines.append(f"  marts produced   : {len(self.marts)} -> {', '.join(self.marts)}")
        lines.append(
            f"  quality gates    : {self.quality_passed} passed, {self.quality_failed} failed"
        )
        lines.append(f"  elapsed          : {self.seconds:.2f}s")
        lines.append("=" * 60)
        return "\n".join(lines)


def run_pipeline(settings: Settings | None = None) -> RunSummary:
    """Execute the full pipeline. Raises on a data-quality gate failure."""
    s = settings or get_settings()
    t0 = time.perf_counter()
    summary = RunSummary()

    log.info("[1/4] ingest: generating synthetic dataset (seed=%d)", s.seed)
    summary.raw_counts = ingest.run(s)

    con = connect(s)
    try:
        log.info("[2/4] load: registering raw files into DuckDB")
        summary.loaded_counts = load.run(con, s)

        log.info("[3/4] transform: building staging + mart models")
        summary.marts = transform.run(con, s)

        log.info("[4/4] quality: enforcing data-quality gates")
        results = quality.run(con, s, raise_on_fail=False)
        summary.quality_passed = sum(1 for r in results if r.passed)
        summary.quality_failed = sum(1 for r in results if not r.passed)
        failed = [r for r in results if not r.passed]
    finally:
        con.close()

    summary.seconds = time.perf_counter() - t0

    if failed:
        names = ", ".join(f"{r.name} ({r.failing_rows} rows)" for r in failed)
        raise quality.DataQualityError(
            f"pipeline halted: {len(failed)} data-quality gate(s) failed: {names}"
        )
    return summary
