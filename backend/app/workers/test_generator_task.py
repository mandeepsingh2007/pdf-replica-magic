import asyncio
import gc
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
from app.core.config import min_context_chars_for_generation, settings

logger = logging.getLogger(__name__)


def should_expand_stacked_images() -> bool:
    """PIL/numpy panel splitting can OOM Render's 512MB web instance — skip there by default."""
    if os.getenv("SKIP_IMAGE_EXPAND") == "1":
        return False
    if os.getenv("SKIP_IMAGE_EXPAND") == "0":
        return True
    if os.getenv("RENDER"):
        return False
    return True


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

        panels = await asyncio.to_thread(split_illustration_file, path)
        if len(panels) < 2:
            expanded.append(img)
            continue

        logger.info("Split stacked illustration %s into %d panels", path, len(panels))
        for panel_path in panels:
            gc.collect()
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
    sub_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = sub_result.scalars().first()
    sub_name = subject.name if subject else None
    return filter_chunks_by_chapters(chunks, chapter_ids, subject_name=sub_name)


async def generate_test_async(request_data: dict, task_id: str):
    """
    Over-generates questions across all types, evaluates them, and saves to DB pool.
    """
    print(f"=== generate_test_async running {task_id} ===", flush=True)
    from app.services.llm_service import reset_llm_errors
    reset_llm_errors()
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

            await update_task_progress(
                db, task_id, 12, f"Loaded {len(chunks)} textbook page(s)"
            )

            total_chars = sum(len(c.content or "") for c in chunks)
            min_chars = min_context_chars_for_generation(chapter_ids)

            if total_chars < min_chars:
                raise Exception(
                    f"Insufficient textbook content ({total_chars} chars, need {min_chars}). "
                    "Try more chapters, or re-seed with --ocr for this book."
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
            chapter_ranges: list[tuple[int, int]] | None = None
            if chapter_ids:
                all_chunks_result = await db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == document_id)
                    .order_by(Chunk.page_number, Chunk.chunk_index)
                )
                all_chunks = all_chunks_result.scalars().all()
                chapters_list = extract_chapters(
                    all_chunks,
                    subject_name=subject.name if subject else None,
                )
                selected_chs = [c for c in chapters_list if c.id in chapter_ids]
                if selected_chs:
                    chapter_scope = "\n".join(
                        f"- {ch.title} (pages {ch.start_page}–{ch.end_page or ch.start_page})"
                        for ch in selected_chs
                    )
                    chapter_ranges = [
                        (ch.start_page, ch.end_page or ch.start_page) for ch in selected_chs
                    ]
                    filtered_images = []
                    for img in image_metadata:
                        p = img.get("page_number")
                        if p and any(
                            ch.start_page <= p <= (ch.end_page or ch.start_page)
                            for ch in selected_chs
                        ):
                            filtered_images.append(img)
                    image_metadata = filtered_images
            image_metadata.sort(
                key=lambda x: (x.get("page_number") or 0, x.get("id") or 0)
            )
            need_picture_match = bool(include_types and "picture_match" in include_types)
            # Expanding stacked crops is slow (PIL per image) and holds the DB.
            # Skip when Picture Match is not selected, or when figures are already
            # discrete disk crops (Hindi images_N / *_fig* / panels).
            already_discrete = False
            for img in image_metadata:
                p = (img.get("image_path") or "").replace("\\", "/")
                base = os.path.basename(p)
                if "images_" in p or "_fig" in base or is_panel_path(p):
                    already_discrete = True
                    break

            if (
                document_id
                and need_picture_match
                and should_expand_stacked_images()
                and not already_discrete
            ):
                await update_task_progress(
                    db, task_id, 15, f"Preparing textbook images ({len(image_metadata)})"
                )
                image_metadata = await expand_stacked_images(db, document_id, image_metadata)
            elif document_id and need_picture_match and already_discrete:
                logger.info(
                    "Skipping stacked-image expand — figures already discrete (%d)",
                    len(image_metadata),
                )
            elif document_id and not need_picture_match:
                logger.info("Skipping stacked-image expand — picture_match not selected")
            elif document_id and os.getenv("RENDER"):
                logger.info(
                    "Skipping stacked-image expand on Render (set SKIP_IMAGE_EXPAND=0 to force)"
                )
            if os.getenv("LOW_MEMORY") == "1" and len(image_metadata) > 24:
                image_metadata = image_metadata[:24]
                logger.info(
                    "LOW_MEMORY: using first %d images for picture-match",
                    len(image_metadata),
                )
            logger.info(
                "Chapter scope: %s | %d images for picture-match",
                chapter_scope or "all chapters",
                len(image_metadata),
            )

            await update_task_progress(db, task_id, 20, "Preparing selected textbook chapters")

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
                chapter_ranges=chapter_ranges,
            )

            await update_task_progress(db, task_id, 80, "Evaluating and saving high-quality questions")

            saved_count = 0
            job_questions = []
            for q in generated_questions:
                if q["score"] >= 0.5:
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
                    job_questions.append(q_record)
                    saved_count += 1

            await db.commit()

            if saved_count == 0:
                n_gen = len(generated_questions)
                if n_gen == 0:
                    from app.services.llm_service import recent_llm_error_summary

                    detail = recent_llm_error_summary()
                    provider = (settings.LLM_PROVIDER or "groq").upper()
                    raise Exception(
                        "No questions were generated. "
                        + (
                            f"LLM error ({provider}): {detail}"
                            if detail
                            else f"Check {provider}_API_KEY in backend .env and uvicorn logs."
                        )
                    )
                scores = [float(q.get("score") or 0) for q in generated_questions]
                types_seen = sorted({q.get("type") for q in generated_questions if q.get("type")})
                raise Exception(
                    f"Generated {n_gen} question(s) ({', '.join(types_seen) or 'unknown'}) but none passed "
                    f"quality checks (scores {min(scores):.2f}–{max(scores):.2f}, need ≥0.50). "
                    "Check backend logs; Hindi books use seed_hindi_text_and_images.py, not seed_pdfs.py."
                )

            if include_types and "picture_match" in include_types:
                pm_need = quota_for_type("picture_match", questions_per_type)
                pm_questions = [q for q in generated_questions if q["type"] == "picture_match"]
                pm_ok = [
                    pm
                    for pm in pm_questions
                    if len((pm.get("data") or {}).get("pictures") or []) >= MATCH_PAIRS_PER_QUESTION
                    and len((pm.get("data") or {}).get("labels") or []) >= MATCH_PAIRS_PER_QUESTION
                ]
                if len(pm_ok) < pm_need:
                    # Soft-skip: drop from assembly so other formats still form the paper.
                    logger.warning(
                        "Picture Match unavailable for selection "
                        "(%d/%d usable); assembling without it.",
                        len(pm_ok),
                        pm_need,
                    )
                    include_types = [t for t in include_types if t != "picture_match"]

            await update_task_progress(db, task_id, 85, "Assembling 50-mark test (5 questions per format)")

            # Never assemble from another job's questions for the same document.
            question_pool = job_questions

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

            def _usable_count(q_type: str) -> int:
                if q_type == "picture_match":
                    return sum(
                        1
                        for q in candidate_list
                        if q["type"] == q_type
                        and len((q.get("data") or {}).get("pictures") or [])
                        >= MATCH_PAIRS_PER_QUESTION
                        and len((q.get("data") or {}).get("labels") or [])
                        >= MATCH_PAIRS_PER_QUESTION
                    )
                return sum(1 for q in candidate_list if q["type"] == q_type)

            # Soft-skip ONLY match formats (need labeled images). Other formats:
            # refill already tried; if still short but >0, assemble with what we have.
            MATCH_SOFT = frozenset({"picture_match", "word_match"})
            assemble_types = []
            missing_hard = []
            for q_type in dict.fromkeys(include_types):
                need = quota_for_type(q_type, questions_per_type)
                have = _usable_count(q_type)
                if have >= need:
                    assemble_types.append(q_type)
                elif q_type in MATCH_SOFT:
                    logger.warning(
                        "Skipping format %s at assemble (%d/%d questions)",
                        q_type,
                        have,
                        need,
                    )
                elif have > 0:
                    logger.warning(
                        "Partial format %s at assemble (%d/%d) — using available questions",
                        q_type,
                        have,
                        need,
                    )
                    assemble_types.append(q_type)
                else:
                    missing_hard.append(f"{q_type} ({have}/{need})")

            if missing_hard:
                raise Exception(
                    "Could not generate enough questions for: "
                    + ", ".join(missing_hard)
                    + ". Try again, or select fewer formats."
                )

            # Exclude incomplete picture-match stubs so they cannot be selected.
            assemble_pool = [
                q
                for q in candidate_list
                if q["type"] != "picture_match"
                or (
                    len((q.get("data") or {}).get("pictures") or [])
                    >= MATCH_PAIRS_PER_QUESTION
                    and len((q.get("data") or {}).get("labels") or [])
                    >= MATCH_PAIRS_PER_QUESTION
                )
            ]

            selected_questions = assemble_fixed_per_type(
                assemble_pool,
                assemble_types,
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
                assembly_metadata=json.dumps({"chapter_ids": chapter_ids or [], "chapter_scope": chapter_scope}),
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
