"""Central configuration for the pipeline.

Paths are resolved relative to the project root so the pipeline behaves the
same whether it is invoked from the repo root, a Makefile target, or CI.
Everything is overridable via environment variables, which keeps the code
container- and cloud-friendly without introducing a config framework.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# pipeline/config.py -> project root is two levels up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_path(var: str, default: Path) -> Path:
    raw = os.environ.get(var)
    return Path(raw).expanduser().resolve() if raw else default


@dataclass(frozen=True)
class Settings:
    """Immutable run configuration."""

    project_root: Path = PROJECT_ROOT
    raw_dir: Path = field(default_factory=lambda: _env_path("CP_RAW_DIR", PROJECT_ROOT / "data" / "raw"))
    warehouse_dir: Path = field(
        default_factory=lambda: _env_path("CP_WAREHOUSE_DIR", PROJECT_ROOT / "data" / "warehouse")
    )
    sql_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "pipeline" / "sql")

    # Synthetic-data knobs (deterministic given the seed).
    seed: int = int(os.environ.get("CP_SEED", "42"))
    n_customers: int = int(os.environ.get("CP_N_CUSTOMERS", "2000"))
    n_orders: int = int(os.environ.get("CP_N_ORDERS", "12000"))
    n_products: int = int(os.environ.get("CP_N_PRODUCTS", "120"))
    start_date: str = os.environ.get("CP_START_DATE", "2024-01-01")
    end_date: str = os.environ.get("CP_END_DATE", "2024-12-31")

    @property
    def db_path(self) -> Path:
        return self.warehouse_dir / "commerce.duckdb"

    def ensure_dirs(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.warehouse_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings (cached)."""
    return Settings()
