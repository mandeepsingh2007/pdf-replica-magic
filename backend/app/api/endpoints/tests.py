import uuid
import json
import os
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List

from app.db.database import get_db
from app.models.generated_test import GeneratedTest
from app.models.task_job import TaskJob
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.extracted_image import ExtractedImage
from app.schemas.requests import GenerateTestRequest, SubmitTestRequest
from app.schemas.responses import (
    GeneratedTestResponse,
    TestAttemptResponse,
    GradeResultResponse,
)
from app.core.config import settings
from app.services.grading_service import (
    build_attempt_payload,
    fetch_pdf_chunks,
    grade_test,
    load_test_with_subject,
    flatten_questions,
    parse_test_data,
)
from app.services.question_generator import VALID_QUESTION_TYPES
from app.services.test_pdf_service import build_answer_key_pdf, build_test_pdf

router = APIRouter()


async def validate_document_has_content(db: AsyncSession, document_id: int) -> None:
    result = await db.execute(
        select(func.count(Chunk.id), func.coalesce(func.sum(func.length(Chunk.content)), 0))
        .where(Chunk.document_id == document_id)
    )
    chunk_count, total_chars = result.one()

    if chunk_count == 0:
        raise HTTPException(
            status_code=400,
            detail="PDF not ingested for this subject. Run: python seed_pdfs.py --force"
        )

    if total_chars < settings.MIN_CONTEXT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient textbook content ({total_chars} chars). "
                "PDF may need OCR re-processing. Run: python seed_pdfs.py --force"
            )
        )


@router.post("/generate-test")
async def generate_test(
    request: GenerateTestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger test generation."""
    if request.document_id is None:
        result = await db.execute(select(Document).where(Document.subject_id == request.subject_id))
        doc = result.scalars().first()
        if not doc:
            raise HTTPException(status_code=400, detail="No document found for this subject")
        request.document_id = doc.id

    await validate_document_has_content(db, request.document_id)

    if request.include_types is not None:
        cleaned = [t for t in request.include_types if t in VALID_QUESTION_TYPES]
        if not cleaned:
            raise HTTPException(status_code=400, detail="Select at least one valid question type.")

    task_id = str(uuid.uuid4())

    task_job = TaskJob(
        id=task_id,
        job_type="test_generation",
        status="pending",
        metadata_json=request.model_dump_json()
    )
    db.add(task_job)
    await db.commit()

    from app.workers.test_generator_task import generate_test_async

    payload = request.model_dump()
    if request.include_types is not None:
        payload["include_types"] = [t for t in request.include_types if t in VALID_QUESTION_TYPES]

    background_tasks.add_task(generate_test_async, payload, task_id)

    return {"task_id": task_id, "message": "Test generation started in background"}


@router.get("/tests", response_model=List[GeneratedTestResponse])
async def list_tests(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List generated tests."""
    # Simplified without join for now
    result = await db.execute(select(GeneratedTest).offset(skip).limit(limit))
    tests = result.scalars().all()
    
    # Manually mapping for response
    responses = []
    for test in tests:
        test_data_dict = {}
        if test.test_data:
            try:
                test_data_dict = json.loads(test.test_data) if isinstance(test.test_data, str) else test.test_data
            except Exception:
                test_data_dict = {}
                
        responses.append({
            "id": test.id,
            "title": test.title or "Untitled Test",
            "subject_name": "Unknown", # Needs join with Subject
            "total_marks": test.total_marks,
            "total_questions": test.total_questions or 0,
            "test_data": test_data_dict,
            "created_at": test.created_at,
            "status": test.status
        })
    return responses

@router.get("/test/{test_id}", response_model=GeneratedTestResponse)
async def get_test(test_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific generated test."""
    result = await db.execute(select(GeneratedTest).where(GeneratedTest.id == test_id))
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
        
    test_data_dict = {}
    if test.test_data:
        try:
            test_data_dict = json.loads(test.test_data) if isinstance(test.test_data, str) else test.test_data
        except Exception:
            test_data_dict = {}

    return {
        "id": test.id,
        "title": test.title or "Untitled Test",
        "subject_name": "Unknown", # Needs join
        "total_marks": test.total_marks,
        "total_questions": test.total_questions or 0,
        "test_data": test_data_dict,
        "created_at": test.created_at,
        "status": test.status
    }


@router.get("/test/{test_id}/attempt", response_model=TestAttemptResponse)
async def get_test_attempt(test_id: int, db: AsyncSession = Depends(get_db)):
    """Student-safe test view — questions without answer keys."""
    try:
        test, subject_name = await load_test_with_subject(db, test_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Test not found")

    return build_attempt_payload(test, subject_name)


@router.get("/test/{test_id}/pdf")
async def download_test_pdf(test_id: int, db: AsyncSession = Depends(get_db)):
    """Generate and download the test paper as a PDF."""
    try:
        test, subject_name = await load_test_with_subject(db, test_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Test not found")

    image_paths: dict[int, str] = {}
    if test.document_id:
        img_result = await db.execute(
            select(ExtractedImage).where(ExtractedImage.document_id == test.document_id)
        )
        for img in img_result.scalars().all():
            if img.image_path and os.path.isfile(img.image_path):
                image_paths[img.id] = img.image_path

    try:
        pdf_bytes = build_test_pdf(test, subject_name, image_paths=image_paths)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    filename = f"test_{test_id}_{subject_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/test/{test_id}/answer-key")
async def download_answer_key_pdf(test_id: int, db: AsyncSession = Depends(get_db)):
    """Download the answer key PDF for only the questions on this test."""
    try:
        test, subject_name = await load_test_with_subject(db, test_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Test not found")

    try:
        pdf_bytes = build_answer_key_pdf(test, subject_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer key PDF failed: {e}")

    filename = f"test_{test_id}_{subject_name.replace(' ', '_')}_answer_key.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/test/{test_id}/submit", response_model=GradeResultResponse)
async def submit_test(
    test_id: int,
    request: SubmitTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Grade student answers against the subject PDF textbook content."""
    try:
        test, subject_name = await load_test_with_subject(db, test_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Test not found")

    test_data = parse_test_data(test)
    all_questions = flatten_questions(test_data)
    required_ids = {str(q["id"]) for q in all_questions}

    if not request.answers:
        raise HTTPException(status_code=400, detail="No answers provided")

    missing = required_ids - set(request.answers.keys())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Please answer all questions. Missing: {len(missing)} question(s).",
        )

    chunks = await fetch_pdf_chunks(db, test.document_id, test.subject_id)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Textbook not available for grading. Re-ingest the PDF first.",
        )

    return await grade_test(test, request.answers, chunks, subject_name)
