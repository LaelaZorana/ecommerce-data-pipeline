"""Command-line entry point for the pipeline.

Examples
--------
    python -m pipeline run          # full pipeline ingest -> load -> transform -> quality
    python -m pipeline ingest       # just regenerate raw data
    python -m pipeline transform    # rebuild marts from the existing warehouse
    python -m pipeline quality      # re-run the data-quality gate
"""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline import ingest, load, quality, transform
from pipeline.config import get_settings
from pipeline.flow import run_pipeline
from pipeline.load import connect


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(message)s",
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="commerce-pipeline", description=__doc__)
    parser.add_argument(
        "stage",
        choices=["run", "ingest", "load", "transform", "quality"],
        help="pipeline stage to execute ('run' = full pipeline)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress progress logs")
    args = parser.parse_args(argv)

    _configure_logging(verbose=not args.quiet)
    s = get_settings()

    try:
        if args.stage == "run":
            summary = run_pipeline(s)
            print(summary.render())
            return 0

        if args.stage == "ingest":
            counts = ingest.run(s)
            print(f"ingest complete: {sum(counts.values()):,} rows across {len(counts)} tables")
            return 0

        con = connect(s)
        try:
            if args.stage == "load":
                counts = load.run(con, s)
                print(f"load complete: {counts}")
            elif args.stage == "transform":
                marts = transform.run(con, s)
                print(f"transform complete: built marts {marts}")
            elif args.stage == "quality":
                results = quality.run(con, s)
                print(f"quality complete: {len(results)} checks passed")
        finally:
            con.close()
        return 0

    except quality.DataQualityError as exc:
        print(f"DATA QUALITY GATE FAILED: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
