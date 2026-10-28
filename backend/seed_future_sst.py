"""
Seed Class 6 and Class 7 Social Science (Future Books) PDFs into SQLite.
Same ingestion path as semester books: OCR + chunks + images.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session, init_db
from app.models.document import Document
from app.models.subject import Subject
from app.models.task_job import TaskJob
from app.services.pdf_ingestion import process_pdf_async

ROOT = os.path.dirname(os.path.dirname(__file__))
PDF_DIRECTORY = os.path.join(ROOT, "test pdf", "original books", "future books sst")

SUBJECTS_MAPPING = {
    "sst-book-6-part-1.pdf": {
        "name": "SST-6",
        "display_name": "Social Science",
        "icon": "BookOpen",
        "description": "Class 6 Social Science Part 1",
    },
    "sst-book-7-part-1.pdf": {
        "name": "SST-7",
        "display_name": "Social Science",
        "icon": "BookOpen",
        "description": "Class 7 Social Science Part 1",
    },
}

SOURCE_FILES = {
    "sst-book-6-part-1.pdf": r"C:\Users\singh\Downloads\sst book-6 part 1.pdf",
    "sst-book-7-part-1.pdf": r"C:\Users\singh\Downloads\sst book-7 part 1.pdf",
}


def ensure_pdfs() -> None:
    os.makedirs(PDF_DIRECTORY, exist_ok=True)
    for dest_name, source in SOURCE_FILES.items():
        dest = os.path.join(PDF_DIRECTORY, dest_name)
        if os.path.isfile(dest) and os.path.getsize(dest) > 1000:
            print(f"PDF ready: {dest_name}")
            continue
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Missing source PDF: {source}")
        shutil.copy2(source, dest)
        print(f"Copied {source} -> {dest}")


async def get_or_create_subject(db: AsyncSession, meta: dict) -> Subject:
    result = await db.execute(select(Subject).where(Subject.name == meta["name"]))
    subject = result.scalars().first()
    if subject:
        subject.display_name = meta["display_name"]
        subject.icon = meta.get("icon")
        subject.description = meta.get("description")
        subject.is_active = True
        print(f"Subject already exists: {subject.name}")
    else:
        subject = Subject(
            name=meta["name"],
            display_name=meta["display_name"],
            icon=meta.get("icon"),
            description=meta.get("description"),
            is_active=True,
        )
        db.add(subject)
        await db.flush()
        print(f"Created subject: {subject.name}")
    return subject


async def get_or_update_document(
    db: AsyncSession, subject: Subject, pdf_filename: str, file_path: str
) -> Document:
    file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else None
    result = await db.execute(
        select(Document).where(
            Document.subject_id == subject.id,
            Document.filename == pdf_filename,
        )
    )
    document = result.scalars().first()
    if document:
        document.file_path = file_path
        document.original_filename = pdf_filename
        document.file_size_bytes = file_size
        document.status = "uploaded"
    else:
        document = Document(
            subject_id=subject.id,
            filename=pdf_filename,
            original_filename=pdf_filename,
            file_path=file_path,
            file_size_bytes=file_size,
            status="uploaded",
        )
        db.add(document)
        await db.flush()

    dupes = await db.execute(
        select(Document).where(
            Document.subject_id == subject.id,
            Document.id != document.id,
        )
    )
    for extra in dupes.scalars().all():
        await db.delete(extra)
    return document


async def seed(force: bool = False) -> None:
    ensure_pdfs()
    await init_db()
    async with async_session() as db:
        for pdf_filename, meta in SUBJECTS_MAPPING.items():
            file_path = os.path.join(PDF_DIRECTORY, pdf_filename)
            if not os.path.isfile(file_path):
                print(f"SKIP missing {pdf_filename}")
                continue
            subject = await get_or_create_subject(db, meta)
            document = await get_or_update_document(db, subject, pdf_filename, file_path)
            await db.commit()

            if document.status == "parsed" and not force:
                print(f"Already parsed: {subject.name} (use --force to re-ingest)")
                continue

            task_id = str(uuid.uuid4())
            db.add(
                TaskJob(
                    id=task_id,
                    job_type="pdf_parsing",
                    status="pending",
                    result_id=document.id,
                )
            )
            await db.commit()
            print(f"Ingesting {subject.name} from {pdf_filename}…")
            await process_pdf_async(document.id, task_id)
            await db.refresh(document)
            print(f"Done: {subject.name} status={document.status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Future Books SST Class 6–7 PDFs")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if already processed")
    args = parser.parse_args()
    asyncio.run(seed(force=args.force))


if __name__ == "__main__":
    # Ensure backend package imports resolve when run as a script.
    sys.path.insert(0, os.path.dirname(__file__))
    main()
