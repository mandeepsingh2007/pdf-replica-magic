import os

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import async_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.extracted_image import ExtractedImage
from app.models.task_job import TaskJob
from app.services.chunking import generate_embeddings, layout_aware_chunking
from app.services.pdf_parser import extract_pdf_data
from app.services.vlm_service import analyze_image_with_vlm


async def update_task_progress(
    db: AsyncSession,
    task_id: str,
    progress: int,
    current_step: str,
    status: str = "processing",
) -> None:
    """Update task status in DB."""
    result = await db.execute(select(TaskJob).where(TaskJob.id == task_id))
    task = result.scalars().first()
    if task:
        task.progress = progress
        task.current_step = current_step
        task.status = status
        await db.commit()


async def process_pdf_async(document_id: int, task_id: str) -> None:
    """Extract text, images, and chunks from a textbook PDF."""
    async with async_session() as db:
        try:
            await update_task_progress(db, task_id, 10, "Fetching document from database")

            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalars().first()

            if not document:
                raise Exception(f"Document {document_id} not found")

            document.status = "parsing"
            await db.commit()

            file_path = document.file_path
            image_out_dir = os.path.join(os.path.dirname(file_path), f"images_{document.id}")

            await db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            await db.execute(delete(ExtractedImage).where(ExtractedImage.document_id == document.id))
            await db.commit()

            await update_task_progress(db, task_id, 30, "Extracting text and images from PDF")
            text_blocks, images = extract_pdf_data(file_path, image_out_dir)

            await update_task_progress(
                db, task_id, 50, f"Analyzing {len(images)} extracted images with AI"
            )
            for img_data in images:
                vlm_desc = await analyze_image_with_vlm(img_data["image_path"])

                img_record = ExtractedImage(
                    document_id=document.id,
                    image_path=img_data["image_path"],
                    page_number=img_data["page"],
                    bbox_x=img_data["bbox_x"],
                    bbox_y=img_data["bbox_y"],
                    bbox_width=img_data["bbox_width"],
                    bbox_height=img_data["bbox_height"],
                    vlm_description=vlm_desc,
                )
                db.add(img_record)

            await update_task_progress(db, task_id, 70, "Chunking document text into semantic blocks")
            chunks = layout_aware_chunking(text_blocks)

            await update_task_progress(db, task_id, 85, "Generating embeddings for textbook chunks")
            chunks_with_embeddings = generate_embeddings(chunks)

            await update_task_progress(db, task_id, 95, "Saving textbook chunks")

            for idx, chunk_data in enumerate(chunks_with_embeddings):
                chunk_record = Chunk(
                    document_id=document.id,
                    content=chunk_data["content"],
                    chunk_index=idx,
                    chunk_type=chunk_data["chunk_type"],
                    page_number=chunk_data["page_number"],
                    section_path=chunk_data["section_path"],
                    embedding=chunk_data["embedding"],
                    token_count=chunk_data["token_count"],
                )
                db.add(chunk_record)

            document.status = "parsed"
            await db.commit()

            await update_task_progress(
                db, task_id, 100, "PDF Ingestion Complete", status="completed"
            )

        except Exception as e:
            await update_task_progress(db, task_id, 0, f"Error: {str(e)}", status="failed")
