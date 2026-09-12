import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.models.subject import Subject
from app.models.document import Document
from app.models.extracted_image import ExtractedImage
from app.models.task_job import TaskJob
from app.schemas.responses import DocumentUploadResponse
from app.core.config import settings
from app.utils.file_utils import save_upload_file, get_file_size

router = APIRouter()

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload a PDF document for a specific subject."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
    # Verify subject exists
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Save file
    saved_filename, file_path = save_upload_file(file, settings.UPLOAD_DIR)
    file_size = get_file_size(file_path)
    
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB")

    # Create document record
    document = Document(
        subject_id=subject_id,
        filename=saved_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size_bytes=file_size,
        status="uploaded"
    )
    db.add(document)
    await db.flush() # To get the document id

    # Create task job record
    task_id = str(uuid.uuid4())
    task_job = TaskJob(
        id=task_id,
        job_type="pdf_parsing",
        status="pending",
        result_id=document.id
    )
    db.add(task_job)
    await db.commit()
    await db.refresh(document)

    # Trigger Celery task
    from app.workers.tasks import parse_pdf_task
    parse_pdf_task.delay(document.id, task_id)

    return DocumentUploadResponse(
        document_id=document.id,
        task_id=task_id,
        filename=document.original_filename,
        status="uploaded",
        message="File uploaded successfully. Parsing started in background."
    )


@router.get("/{document_id}/images/{image_id}")
async def get_document_image(
    document_id: int,
    image_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Serve an extracted textbook image for picture-match questions."""
    result = await db.execute(
        select(ExtractedImage).where(
            ExtractedImage.id == image_id,
            ExtractedImage.document_id == document_id,
        )
    )
    image = result.scalars().first()
    if not image or not image.image_path or not os.path.isfile(image.image_path):
        raise HTTPException(status_code=404, detail="Image not found")

    ext = os.path.splitext(image.image_path)[1].lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")
    return FileResponse(image.image_path, media_type=media)
