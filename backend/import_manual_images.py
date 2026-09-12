"""
Register manually added textbook images (PDF1_P*_IMG*.png) in extracted_images
so picture-match can use them. Safe to re-run — skips paths already in DB.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

from sqlalchemy import delete, select

sys.path.insert(0, os.path.dirname(__file__))

from app.db.database import async_session
from app.models.document import Document
from app.models.extracted_image import ExtractedImage
from app.services.vlm_service import analyze_image_with_vlm

PDF1_PAGE_RE = re.compile(r"^PDF1_P(\d+)_IMG(\d+)", re.I)
PAGE_FIG_RE = re.compile(r"^page(\d+)_fig", re.I)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def page_from_filename(name: str) -> int | None:
    m = PDF1_PAGE_RE.match(name)
    if m:
        return int(m.group(1))
    m = PAGE_FIG_RE.match(name)
    if m:
        return int(m.group(1))
    return None


def is_manual_import_name(name: str) -> bool:
    return bool(PDF1_PAGE_RE.match(name))


def image_dir_for_document(doc: Document) -> Path:
    return Path(os.path.dirname(doc.file_path)) / f"images_{doc.id}"


async def prune_missing_rows(db, document_id: int, dry_run: bool) -> int:
    result = await db.execute(
        select(ExtractedImage).where(ExtractedImage.document_id == document_id)
    )
    stale = [r for r in result.scalars().all() if not os.path.isfile(r.image_path)]
    if stale and not dry_run:
        for r in stale:
            await db.delete(r)
        await db.commit()
    return len(stale)


async def import_document(
    db,
    doc: Document,
    *,
    vlm: bool,
    dry_run: bool,
    all_orphans: bool,
) -> tuple[int, int, int]:
    """Returns (imported, skipped_existing, pruned_missing)."""
    folder = image_dir_for_document(doc)
    if not folder.is_dir():
        print(f"  skip: folder missing {folder}")
        return 0, 0, 0

    result = await db.execute(
        select(ExtractedImage).where(ExtractedImage.document_id == doc.id)
    )
    existing_paths = {os.path.normpath(r.image_path) for r in result.scalars().all()}

    candidates: list[Path] = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        norm = os.path.normpath(str(path))
        if norm in existing_paths:
            continue
        if all_orphans or is_manual_import_name(path.name):
            candidates.append(path)

    pruned = await prune_missing_rows(db, doc.id, dry_run)
    if not candidates:
        print(f"  no new files to import (pruned missing rows: {pruned})")
        return 0, len(existing_paths), pruned

    imported = 0
    for i, path in enumerate(candidates, 1):
        page = page_from_filename(path.name)
        desc = ""
        if vlm and not dry_run:
            desc = await analyze_image_with_vlm(str(path))
            await asyncio.sleep(0.3)
        elif not vlm:
            desc = f"Textbook illustration from page {page}" if page else "Textbook illustration"

        print(f"  [{i}/{len(candidates)}] {path.name} page={page}" + (" (dry-run)" if dry_run else ""))
        if dry_run:
            imported += 1
            continue

        rec = ExtractedImage(
            document_id=doc.id,
            image_path=str(path),
            page_number=page,
            bbox_x=None,
            bbox_y=None,
            bbox_width=None,
            bbox_height=None,
            vlm_description=desc or "Textbook illustration",
            caption=None,
        )
        db.add(rec)
        imported += 1

    if not dry_run and imported:
        await db.commit()
    return imported, len(existing_paths), pruned


async def main_async(args: argparse.Namespace) -> None:
    doc_ids = args.document_ids
    async with async_session() as db:
        for doc_id in doc_ids:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalars().first()
            if not doc:
                print(f"Document {doc_id} not found")
                continue
            print(f"\n=== doc {doc.id}: {doc.original_filename} ===")
            imp, existing, pruned = await import_document(
                db,
                doc,
                vlm=not args.skip_vlm,
                dry_run=args.dry_run,
                all_orphans=args.all_orphans,
            )
            print(f"  imported={imp} already_in_db={existing} pruned_missing={pruned}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import manual PDF1_P* images into extracted_images")
    parser.add_argument(
        "--document-id",
        type=int,
        action="append",
        dest="document_ids",
        help="Document id (default: 3, 4, 5 — Computer, GK, EVS)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List files only, no DB/VLM")
    parser.add_argument("--skip-vlm", action="store_true", help="Skip Gemini descriptions (faster, weaker match)")
    parser.add_argument(
        "--all-orphans",
        action="store_true",
        help="Import any file not in DB, not only PDF1_P* names",
    )
    args = parser.parse_args()
    if not args.document_ids:
        args.document_ids = [3, 4, 5]
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
