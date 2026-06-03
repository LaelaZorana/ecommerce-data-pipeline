"""CommercePipeline: a small but complete e-commerce analytics pipeline.

Stages
------
ingest    -> generate deterministic synthetic raw data (Parquet/CSV)
load      -> register raw files into a DuckDB warehouse
transform -> build staging + mart models with SQL
quality   -> enforce data-quality gates (fails the run on violation)

The stages are composed by :mod:`pipeline.flow` and exposed on the CLI.
"""

from pipeline.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
__version__ = "1.0.0"
