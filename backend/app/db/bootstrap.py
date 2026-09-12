"""Ensure Render/container SQLite has the seeded Class 1 DB (not an empty file)."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Real deploy bundle is ~600KB+; empty schema-only files are much smaller.
_MIN_SEED_BYTES = 50_000


def _sqlite_path(database_url: str) -> Path | None:
    if "sqlite" not in database_url.lower():
        return None
    if ":///" in database_url:
        raw = database_url.split(":///")[-1]
    else:
        raw = database_url.split("://")[-1]
    return Path(raw) if raw.startswith("/") else Path(raw)


def _seed_candidates() -> list[Path]:
    backend = Path(__file__).resolve().parents[2]
    return [backend / "test_generator.db", backend / "test_generator.db.deploy"]


def ensure_sqlite_seed(database_url: str) -> bool:
    """Copy baked-in seed DB if target is missing or too small. Returns True if copied."""
    target = _sqlite_path(database_url)
    if not target:
        return False

    seed = next((p for p in _seed_candidates() if p.is_file()), None)
    if not seed:
        logger.warning("SQLite seed missing (commit backend/test_generator.db.deploy)")
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size >= _MIN_SEED_BYTES:
        return False

    shutil.copy2(seed, target)
    logger.info("Seeded SQLite %s from %s (%s bytes)", target, seed, target.stat().st_size)
    return True
