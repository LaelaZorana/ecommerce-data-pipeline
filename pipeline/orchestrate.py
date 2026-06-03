"""Optional Prefect orchestration of the same DAG exposed in :mod:`pipeline.flow`.

Prefect is **not** a hard dependency. The Makefile DAG and ``pipeline.flow`` run
the pipeline end to end without it. Install the extra to get a schedulable,
observable flow::

    pip install prefect
    python -m pipeline.orchestrate          # run the flow once
    prefect server start                    # (optional) UI for run history

Each stage is a Prefect ``@task`` so retries, logging, and the run graph come for
free; the orchestration mirrors ``flow.run_pipeline`` exactly.
"""

from __future__ import annotations

import sys

from pipeline import ingest, load, quality, transform
from pipeline.config import get_settings
from pipeline.load import connect

try:
    from prefect import flow, task
except ImportError:  # pragma: no cover - optional dependency
    print(
        "Prefect is not installed. Install it with `pip install prefect`,\n"
        "or run the dependency-free pipeline with `python -m pipeline run`.",
        file=sys.stderr,
    )
    raise SystemExit(2)


@task(name="ingest", retries=1)
def ingest_task(settings) -> dict:
    return ingest.run(settings)


@task(name="load")
def load_task(settings) -> dict:
    con = connect(settings)
    try:
        return load.run(con, settings)
    finally:
        con.close()


@task(name="transform")
def transform_task(settings) -> list:
    con = connect(settings)
    try:
        return transform.run(con, settings)
    finally:
        con.close()


@task(name="quality")
def quality_task(settings) -> int:
    # raise_on_fail=True so a failed gate fails the Prefect run.
    results = quality.run(settings=settings, raise_on_fail=True)
    return len(results)


@flow(name="commerce-pipeline")
def commerce_pipeline_flow() -> None:
    settings = get_settings()
    raw = ingest_task(settings)
    loaded = load_task(settings, wait_for=[raw])
    marts = transform_task(settings, wait_for=[loaded])
    quality_task(settings, wait_for=[marts])


if __name__ == "__main__":  # pragma: no cover
    commerce_pipeline_flow()
