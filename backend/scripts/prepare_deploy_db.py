"""
Copy local SQLite DB and rewrite file paths for Linux container (/app/...).
Run once before Docker build / Render deploy:

  python backend/scripts/prepare_deploy_db.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC_DB = REPO / "backend" / "test_generator.db"
OUT_DB = REPO / "backend" / "test_generator.db.deploy"
CONTAINER_ROOT = Path("/app")


def to_container_path(raw: str) -> str:
    if not raw:
        return raw
    p = raw.replace("\\", "/")
    lower = p.lower()
    marker = "test pdf/"
    idx = lower.find(marker)
    if idx >= 0:
        return str(CONTAINER_ROOT / p[idx:]).replace("\\", "/")
    if p.startswith("/app/"):
        return p
    return p


def main() -> None:
    if not SRC_DB.is_file():
        raise SystemExit(f"Missing {SRC_DB}. Run seed_pdfs.py locally first.")

    shutil.copy2(SRC_DB, OUT_DB)
    conn = sqlite3.connect(OUT_DB)
    try:
        for table, column in (
            ("documents", "file_path"),
            ("extracted_images", "image_path"),
        ):
            rows = conn.execute(f"SELECT id, {column} FROM {table}").fetchall()
            for row_id, path in rows:
                if not path:
                    continue
                fixed = to_container_path(path)
                if fixed != path:
                    conn.execute(
                        f"UPDATE {table} SET {column} = ? WHERE id = ?",
                        (fixed, row_id),
                    )
        conn.commit()
    finally:
        conn.close()

    print(f"Wrote {OUT_DB} ({OUT_DB.stat().st_size // 1024} KB)")
    print("Commit test_generator.db.deploy + test pdf/ for cloud deploy.")


if __name__ == "__main__":
    main()
