import asyncio
import json
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.workers.celery_app import celery_app
from app.db.database import async_session
from app.models.task_job import TaskJob
from app.models.question import Question
from app.models.subject import Subject
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.generated_test import GeneratedTest
from app.models.extracted_image import ExtractedImage
from app.services.question_generator import generate_all_types, VALID_QUESTION_TYPES, quota_for_type, MATCH_PAIRS_PER_QUESTION
from app.services.optimizer import assemble_fixed_per_type, structure_final_test_json
from app.services.chapter_service import extract_chapters, filter_chunks_by_chapters
from app.services.image_quality import is_panel_path, original_stem_from_panel, split_illustration_file
from app.core.config import settings

logger = logging.getLogger(__name__)


async def expand_stacked_images(
    db: AsyncSession, document_id: int, images: list[dict]
) -> list[dict]:
    """Split two-panel crops into separate DB images so picture-match gets one scene each."""
    paths = {img.get("image_path") for img in images if img.get("image_path")}
    split_originals = {
        original_stem_from_panel(p)
        for p in paths
        if p and is_panel_path(p)
    }

    expanded: list[dict] = []
    for img in images:
        path = img.get("image_path")
        if not path or not os.path.isfile(path):
            continue
        if path in split_originals:
            continue
        if is_panel_path(path):
            expanded.append(img)
            continue

        panels = split_illustration_file(path)
        if len(panels) < 2:
            expanded.append(img)
            continue

        logger.info("Split stacked illustration %s into %d panels", path, len(panels))
        for panel_path in panels:
            result = await db.execute(
                select(ExtractedImage).where(ExtractedImage.image_path == panel_path)
            )
            rec = result.scalars().first()
            if not rec:
                rec = ExtractedImage(
                    document_id=document_id,
                    image_path=panel_path,
                    page_number=img.get("page_number"),
                    bbox_x=img.get("bbox_x"),
                    bbox_y=img.get("bbox_y"),
                    bbox_width=img.get("bbox_width"),
                    bbox_height=None,
                    vlm_description="",
                    caption="",
                )
                db.add(rec)
                await db.flush()
            expanded.append(
                {
                    "id": rec.id,
                    "description": rec.vlm_description or "",
                    "caption": rec.caption or "",
                    "image_path": panel_path,
                    "page_number": rec.page_number or img.get("page_number"),
                    "bbox_width": rec.bbox_width,
                    "bbox_height": rec.bbox_height,
                }
            )

    await db.commit()
    return expanded


async def update_task_progress(db: AsyncSession, task_id: str, progress: int, current_step: str, status: str = "processing"):
    result = await db.execute(select(TaskJob).where(TaskJob.id == task_id))
    task = result.scalars().first()
    if task:
        task.progress = progress
        task.current_step = current_step
        task.status = status
        await db.commit()


async def fetch_textbook_chunks(
    db: AsyncSession,
    document_id: int | None,
    subject_id: int,
    chapter_ids: list[str] | None = None,
) -> list:
    if document_id:
        result = await db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.page_number, Chunk.chunk_index)
        )
    else:
        result = await db.execute(
            select(Chunk)
            .join(Document)
            .where(Document.subject_id == subject_id)
            .order_by(Chunk.page_number, Chunk.chunk_index)
        )
    chunks = result.scalars().all()
    return filter_chunks_by_chapters(chunks, chapter_ids)


async def generate_test_async(request_data: dict, task_id: str):
    """
    Over-generates questions across all types, evaluates them, and saves to DB pool.
    """
    async with async_session() as db:
        try:
            await update_task_progress(db, task_id, 10, "Fetching textbook content for generation")

            document_id = request_data.get("document_id")
            subject_id = request_data.get("subject_id")
            total_marks = int(request_data.get("total_marks", 50))
            include_types = request_data.get("include_types")
            chapter_ids = request_data.get("chapter_ids")
            questions_per_type = max(1, min(5, int(request_data.get("questions_per_type", 5))))

            if include_types:
                include_types = [t for t in include_types if t in VALID_QUESTION_TYPES]
                if not include_types:
                    raise Exception("No valid question types selected.")

            subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
            subject = subject_result.scalars().first()
            subject_name = subject.display_name if subject else "the subject"

            chunks = await fetch_textbook_chunks(db, document_id, subject_id, chapter_ids)

            if not chunks:
                raise Exception(
                    "PDF not ingested for this subject. Run: python seed_pdfs.py --force"
                )

            context = "\n\n".join([c.content for c in chunks])

            if len(context) < settings.MIN_CONTEXT_CHARS:
                raise Exception(
                    f"Insufficient textbook content ({len(context)} chars). "
                    "PDF may not have been OCR'd correctly. Run: python seed_pdfs.py --force"
                )

            img_result = await db.execute(
                select(ExtractedImage).where(ExtractedImage.document_id == document_id)
            )
            image_metadata = [
                {
                    "id": img.id,
                    "description": img.vlm_description or img.caption or "",
                    "caption": img.caption or "",
                    "image_path": img.image_path,
                    "page_number": img.page_number,
                    "bbox_width": img.bbox_width,
                    "bbox_height": img.bbox_height,
                }
                for img in img_result.scalars().all()
            ]

            chapter_scope = None
            if chapter_ids:
                all_chunks_result = await db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == document_id)
                    .order_by(Chunk.page_number, Chunk.chunk_index)
                )
                all_chunks = all_chunks_result.scalars().all()
                chapters_list = extract_chapters(all_chunks)
                selected_chs = [c for c in chapters_list if c.id in chapter_ids]
                if selected_chs:
                    chapter_scope = "\n".join(
                        f"- {ch.title} (pages {ch.start_page}–{ch.end_page or ch.start_page})"
                        for ch in selected_chs
                    )
                    filtered_images = []
                    for img in image_metadata:
                        p = img.get("page_number")
                        if p and any(
                            ch.start_page <= p <= (ch.end_page or ch.start_page)
                            for ch in selected_chs
                        ):
                            filtered_images.append(img)
                    image_metadata = filtered_images
            if document_id:
                image_metadata = await expand_stacked_images(db, document_id, image_metadata)
            logger.info(
                "Chapter scope: %s | %d images for picture-match",
                chapter_scope or "all chapters",
                len(image_metadata),
            )

            await update_task_progress(db, task_id, 20, "Clearing stale questions for fresh generation")
            await db.execute(delete(Question).where(Question.document_id == document_id))
            await db.commit()

            async def on_generation_progress(pct: int, step: str):
                await update_task_progress(db, task_id, pct, step)

            await update_task_progress(db, task_id, 30, "Generating questions from textbook (this takes 2-4 min)")

            generated_questions = await generate_all_types(
                chunks,
                image_metadata,
                subject_name,
                on_progress=on_generation_progress,
                include_types=include_types,
                questions_per_type=questions_per_type,
                chapter_scope=chapter_scope,
            )

            await update_task_progress(db, task_id, 80, "Evaluating and saving high-quality questions")

            saved_count = 0
            for q in generated_questions:
                if q["score"] >= 0.7:
                    q_record = Question(
                        document_id=document_id,
                        subject_id=subject_id,
                        question_type=q["type"],
                        question_data=json.dumps(q["data"]),
                        mark_value=q["marks"],
                        difficulty="medium",
                        quality_score=q["score"]
                    )
                    db.add(q_record)
                    saved_count += 1

            await db.commit()

            if saved_count == 0:
                raise Exception(
                    "No PDF-grounded questions passed quality checks. "
                    "Re-ingest the PDF with: python seed_pdfs.py --force"
                )

            if include_types and "picture_match" in include_types:
                pm_need = quota_for_type("picture_match", questions_per_type)
                pm_questions = [q for q in generated_questions if q["type"] == "picture_match"]
                for pm in pm_questions:
                    data = pm.get("data", {})
                    if (
                        len(data.get("pictures", [])) < MATCH_PAIRS_PER_QUESTION
                        or len(data.get("labels", [])) < MATCH_PAIRS_PER_QUESTION
                    ):
                        raise Exception(
                            f"Picture-match incomplete (need {MATCH_PAIRS_PER_QUESTION} pictures + labels)."
                        )
                if len(pm_questions) < pm_need:
                    from app.services.question_generator import filter_quality_images

                    strict_n = len(filter_quality_images(image_metadata, tier="strict"))
                    relaxed_n = len(filter_quality_images(image_metadata, tier="relaxed"))
                    raise Exception(
                        f"Could not build Match the Following (pictures). "
                        f"Need {MATCH_PAIRS_PER_QUESTION} illustration images in selected chapters "
                        f"(found {relaxed_n} usable). Select one more chapter."
                    )

            await update_task_progress(db, task_id, 85, "Assembling 50-mark test (5 questions per format)")

            result = await db.execute(select(Question).where(Question.document_id == document_id))
            question_pool = result.scalars().all()

            candidate_list = [
                {
                    "id": q.id,
                    "type": q.question_type,
                    "marks": q.mark_value,
                    "score": q.quality_score,
                    "data": json.loads(q.question_data) if q.question_data else {}
                }
                for q in question_pool
            ]

            if not include_types:
                include_types = list({q["type"] for q in candidate_list})

            selected_questions = assemble_fixed_per_type(
                candidate_list,
                include_types,
                questions_per_type=questions_per_type,
                total_marks=total_marks,
            )

            if not selected_questions:
                raise Exception(
                    f"Could not assemble test: need {questions_per_type} questions per selected format. "
                    "Try selecting fewer formats or re-generate."
                )

            await update_task_progress(db, task_id, 95, "Saving finalized test paper to database")

            test_json = structure_final_test_json(
                selected_questions, questions_per_type=questions_per_type
            )
            selected_ids = [q["id"] for q in selected_questions]

            chapter_label = ""
            if chapter_ids:
                chapter_label = f" ({len(chapter_ids)} chapter(s))"

            final_test = GeneratedTest(
                subject_id=subject_id,
                document_id=document_id,
                title=f"Generated Test - {subject_name}{chapter_label}",
                total_marks=sum(q["marks"] for q in selected_questions),
                total_questions=len(selected_questions),
                test_data=json.dumps(test_json),
                question_ids=json.dumps(selected_ids),
                status="completed"
            )
            db.add(final_test)
            await db.commit()

            result_db = await db.execute(select(TaskJob).where(TaskJob.id == task_id))
            task_update = result_db.scalars().first()
            task_update.result_id = final_test.id
            await db.commit()

            await update_task_progress(db, task_id, 100, "Test paper successfully generated and assembled!", status="completed")

        except Exception as e:
            await update_task_progress(db, task_id, 0, f"Error: {str(e)}", status="failed")


@celery_app.task(name="generate_questions_task")
def generate_questions_task(request_data: dict, task_id: str):
    asyncio.run(generate_test_async(request_data, task_id))
