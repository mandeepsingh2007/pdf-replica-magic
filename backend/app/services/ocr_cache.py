"""Disk cache for per-page textbook OCR (Gemini or EasyOCR).

Cache key = SHA-256 of the PDF bytes + page number, so edits to a different
edition never reuse stale text.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

CACHE_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "ocr_cache"


def pdf_fingerprint(pdf_path: str | Path) -> str:
    return hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()


def cache_dir(fingerprint: str, engine: str) -> Path:
    return CACHE_ROOT / fingerprint[:16] / engine


def read_cached_page(fingerprint: str, engine: str, page: int) -> str | None:
    path = cache_dir(fingerprint, engine) / f"page_{page:04d}.txt"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def write_cached_page(fingerprint: str, engine: str, page: int, text: str) -> None:
    if not text or not text.strip():
        return
    folder = cache_dir(fingerprint, engine)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"page_{page:04d}.txt").write_text(text.strip() + "\n", encoding="utf-8")


def cached_page_count(fingerprint: str, engine: str) -> int:
    folder = cache_dir(fingerprint, engine)
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.glob("page_*.txt") if p.stat().st_size > 0)
