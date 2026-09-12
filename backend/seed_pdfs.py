"""
Bootstrap SQLite with Class 1 Semester 1 textbook PDFs.
Runs the full ingestion pipeline (OCR + image extraction + VLM) synchronously.
"""
import argparse
import asyncio
import os
import sys
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session, init_db
from app.models.document import Document
from app.models.generated_test import GeneratedTest
from app.models.question import Question
from app.models.subject import Subject
from app.models.task_job import TaskJob
from app.services.pdf_ingestion import process_pdf_async

PDF_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "test pdf",
    "original books",
    "class 1 sem 1",
)

SUBJECTS_MAPPING: dict[str, dict] = {
    "Future Final English 1-S-1 Pages 36_optimize.pdf": {
        "name": "English",
        "display_name": "English",
        "icon": "Languages",
        "description": "Class 1 Semester 1 English",
    },
    "Future  Maths-1-S-1 Pages 72_optimize.pdf": {
        "name": "Mathematics",
        "display_name": "Mathematics",
        "icon": "Calculator",
        "description": "Class 1 Semester 1 Mathematics",
    },
    "Future  Computer-1 S-1 Pages 40_optimize.pdf": {
        "name": "Computer",
        "display_name": "Computer",
        "icon": "Monitor",
        "description": "Class 1 Semester 1 Computer",
    },
    "Future  GK-1-S-1 Pages 24_optimize.pdf": {
        "name": "GK",
        "display_name": "General Knowledge",
        "icon": "BookOpen",
        "description": "Class 1 Semester 1 General Knowledge",
    },
    "Future Final EVS1-S-1 Pages 40_optimize.pdf": {
        "name": "EVS",
        "display_name": "EVS",
        "icon": "Leaf",
        "description": "Class 1 Semester 1 EVS",
    },
}

DEACTIVATE_SUBJECTS = ("Science", "SST")


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

    # Keep one document per subject — remove duplicates
    dupes = await db.execute(
        select(Document).where(
            Document.subject_id == subject.id,
            Document.id != document.id,
        )
    )
    for old in dupes.scalars().all():
        await db.delete(old)

    await db.commit()
    await db.refresh(document)
    return document


async def clear_document_data(db: AsyncSession, document_id: int) -> None:
    await db.execute(delete(Question).where(Question.document_id == document_id))
    await db.execute(
        delete(GeneratedTest).where(GeneratedTest.document_id == document_id)
    )
    await db.commit()


async def parse_document(db: AsyncSession, document: Document) -> None:
    task_id = str(uuid.uuid4())
    task_job = TaskJob(
        id=task_id,
        job_type="pdf_parsing",
        status="pending",
        result_id=document.id,
    )
    db.add(task_job)
    await db.commit()

    print(f"Starting ingestion for {document.original_filename} (doc_id={document.id})")
    await process_pdf_async(document.id, task_id)
    print(f"Finished parsing: {document.original_filename}")


def matches_filter(pdf_filename: str, meta: dict, only: str | None) -> bool:
    if not only:
        return True
    needle = only.strip().lower()
    return (
        pdf_filename.lower() == needle
        or meta["name"].lower() == needle
        or meta["display_name"].lower() == needle
    )


async def deactivate_unused_subjects(db: AsyncSession) -> None:
    result = await db.execute(
        select(Subject).where(Subject.name.in_(DEACTIVATE_SUBJECTS))
    )
    for subject in result.scalars().all():
        subject.is_active = False
        print(f"Deactivated subject: {subject.name}")
    await db.commit()


async def seed_database(force: bool = False, only: str | None = None) -> None:
    print("Initializing Database...")
    await init_db()

    pdf_dir = os.path.normpath(PDF_DIRECTORY)
    print(f"Scanning directory: {pdf_dir}")
    if force:
        print("Force mode: re-ingesting all PDFs and clearing stale data.")
    if only:
        print(f"Processing only: {only}")

    async with async_session() as db:
        if force and not only:
            await deactivate_unused_subjects(db)

        for pdf_filename, meta in SUBJECTS_MAPPING.items():
            if not matches_filter(pdf_filename, meta, only):
                continue

            file_path = os.path.join(pdf_dir, pdf_filename)
            if not os.path.isfile(file_path):
                print(f"WARNING: PDF not found: {file_path}")
                continue

            subject = await get_or_create_subject(db, meta)
            document = await get_or_update_document(db, subject, pdf_filename, file_path)

            should_parse = force or only is not None
            if not should_parse and document.status == "parsed":
                print(f"Already parsed: {pdf_filename} (use --force to re-process)")
                continue

            if should_parse:
                label = "Force re-ingesting" if force else "Re-ingesting"
                print(f"{label}: {pdf_filename}")
                await clear_document_data(db, document.id)
                await parse_document(db, document)

        await db.commit()

    print("\nSeeding complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Class 1 Sem 1 textbook PDFs")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest all mapped PDFs and clear stale question/test data",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Process one PDF by filename, subject name, or display name",
    )
    args = parser.parse_args()
    asyncio.run(seed_database(force=args.force, only=args.only))


if __name__ == "__main__":
    main()
