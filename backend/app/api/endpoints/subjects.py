from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.database import get_db
from app.models.subject import Subject
from app.models.document import Document
from app.models.chunk import Chunk
from app.schemas.responses import SubjectResponse, ChapterResponse
from app.services.chapter_service import extract_chapters

router = APIRouter()

@router.get("", response_model=List[SubjectResponse])
async def list_subjects(db: AsyncSession = Depends(get_db)):
    """List all active subjects."""
    result = await db.execute(select(Subject).where(Subject.is_active == True))
    subjects = result.scalars().all()
    return subjects

@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single subject by ID."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id, Subject.is_active == True))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.get("/{subject_id}/chapters", response_model=List[ChapterResponse])
async def list_subject_chapters(subject_id: int, db: AsyncSession = Depends(get_db)):
    """List textbook chapters extracted from the subject PDF."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id, Subject.is_active == True))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    doc_result = await db.execute(
        select(Document)
        .where(Document.subject_id == subject_id)
        .order_by(Document.id.desc())
    )
    document = doc_result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="No textbook PDF found for this subject")

    chunk_result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document.id)
        .order_by(Chunk.page_number, Chunk.chunk_index)
    )
    chunks = chunk_result.scalars().all()
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Textbook not ingested yet. Run: python seed_pdfs.py --force",
        )

    chapters = extract_chapters(chunks)
    if not chapters:
        raise HTTPException(status_code=404, detail="No chapters found in textbook PDF")

    return [ch.to_dict() for ch in chapters]
