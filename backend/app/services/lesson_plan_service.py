"""Generate one lesson plan from the selected class, subject, and chapter."""

from __future__ import annotations

import asyncio
import json
import logging
import re

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.subject import Subject
from app.services.chapter_service import extract_chapters, filter_chunks_by_chapters
from app.services.gemini_client import generate_gemini_content
from app.services.lesson_plan_docx import build_lesson_plan_pdf
from app.services.llm_service import (
    _groq_client,
    _groq_model_name,
    _parse_json_text,
    llm_semaphore,
    truncate_context,
)

_SUBJECTS = (
    {"key": "computer", "label": "Computer", "api_name": "Computer"},
    {"key": "gk", "label": "General Knowledge", "api_name": "GK"},
    {"key": "mathematics", "label": "Mathematics", "api_name": "Mathematics"},
    {"key": "english", "label": "English", "api_name": "English"},
    {"key": "evs", "label": "Environmental Studies", "api_name": "EVS"},
)

logger = logging.getLogger(__name__)


def _subject_by_key(key: str) -> dict | None:
    return next((item for item in _SUBJECTS if item["key"] == key), None)


async def _complete_json(prompt: str, schema_model) -> dict:
    schema = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
    provider = (settings.LLM_PROVIDER or "groq").strip().lower()
    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is missing.")
        client = _groq_client()
        async with llm_semaphore:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=_groq_model_name(),
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": "Return ONLY valid JSON matching this schema:\n" + schema,
                        },
                        {"role": "user", "content": prompt},
                    ],
                ),
                timeout=settings.LLM_CALL_TIMEOUT_SEC,
            )
        return _parse_json_text(response.choices[0].message.content or "{}")
    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing.")
        full = "Return ONLY valid JSON matching this schema:\n" + schema + "\n\n" + prompt
        async with llm_semaphore:
            response = await asyncio.wait_for(
                generate_gemini_content(full, config={"response_mime_type": "application/json"}),
                timeout=settings.LLM_CALL_TIMEOUT_SEC,
            )
        return _parse_json_text(response.text or "{}")
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")


class LevelBody(BaseModel):
    objective: str = Field(description="Rest of the objective after the given verb. One sentence from the chapter.")
    activity: list[str] = Field(min_length=2, max_length=3)
    student_task: list[str] = Field(min_length=2, max_length=3)
    assessment: list[str] = Field(min_length=1, max_length=2)


class LessonPlanOut(BaseModel):
    remembering: LevelBody
    understanding: LevelBody
    applying: LevelBody
    analyzing: LevelBody
    evaluating: LevelBody
    creating: LevelBody
    assessment: list[str] = Field(min_length=3, max_length=3)
    homework: list[str] = Field(min_length=2, max_length=2)
    conclusion: str
    conclusion_phrases: list[str] = Field(min_length=2, max_length=3)


def _prompt(class_level: int, subject: str, chapter: str, context: str) -> str:
    return f"""Write the classroom content for a Class {class_level} {subject} lesson plan.
Chapter: {chapter}

The printed headings are already fixed. Return only the content that sits under them.
Use ONLY names, events, words, and facts from this chapter. Do not invent a different story.
Each line is one short classroom sentence a teacher can say or a child can do.
Duration of the lesson is 45 minutes. Do not change the six Bloom headings.

Objectives, one sentence each, written so they follow these opening verbs:
- remembering starts after Identify
- understanding starts after Explain
- applying starts after Use
- analyzing starts after Differentiate
- evaluating starts after Express
- creating starts after Create

Each Bloom block needs activity lines, student task lines, and assessment lines from this chapter.
assessment is three short checks for the whole lesson.
homework is two tasks a child can do at home from this chapter.
conclusion is two sentences about what this chapter taught.
conclusion_phrases are two or three short phrases copied exactly from the conclusion, to be shown in bold.

CHAPTER TEXT:
{context}
"""


async def generate_lesson_plan(
    db: AsyncSession,
    *,
    class_level: int,
    subject_key: str,
    chapter_id: str,
) -> tuple[bytes, str]:
    subject_meta = _subject_by_key(subject_key)
    if subject_meta is None:
        raise ValueError("Unknown subject.")

    rows = (
        await db.execute(
            select(Subject).where(Subject.name == subject_meta["api_name"], Subject.is_active == True)
        )
    ).scalars().all()
    subject = next(
        (row for row in rows if f"class {class_level}" in (row.description or "").lower()),
        None,
    )
    if subject is None:
        raise LookupError(
            f"No Class {class_level} {subject_meta['label']} textbook is uploaded, "
            "so a lesson plan cannot be made."
        )

    document = (
        await db.execute(
            select(Document).where(Document.subject_id == subject.id).order_by(Document.id.desc())
        )
    ).scalars().first()
    if document is None:
        raise LookupError("No textbook PDF is stored for this subject.")

    chunks = (
        await db.execute(
            select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.page_number, Chunk.chunk_index)
        )
    ).scalars().all()
    chapters = extract_chapters(chunks, subject_name=subject.name)
    selected = next((chapter for chapter in chapters if chapter.id == chapter_id), None)
    if selected is None:
        raise ValueError("That chapter was not found. Refresh the list.")

    scoped = filter_chunks_by_chapters(chunks, [chapter_id], subject_name=subject.name)
    if not scoped:
        raise LookupError("That chapter has no textbook text.")
    context = truncate_context(
        "\n\n".join(f"[PDF PAGE {chunk.page_number}]\n{chunk.content}" for chunk in scoped if chunk.content)
    )
    prompt = _prompt(class_level, subject_meta["label"], selected.title, context)
    rejection = ""
    last_error = "Could not build this lesson plan from the chapter."
    data = None
    for _attempt in range(2):
        raw = await _complete_json(prompt + rejection, LessonPlanOut)
        try:
            data = LessonPlanOut.model_validate(raw).model_dump()
            break
        except Exception as exc:
            rejection = f"\n\nRejected: {exc}. Return the full JSON again."
            last_error = str(exc)
            logger.warning("Lesson plan JSON rejected: %s", exc)
    if data is None:
        raise RuntimeError(last_error)

    pdf = build_lesson_plan_pdf(
        class_level=class_level,
        subject=subject_meta["label"],
        chapter=selected.title,
        plan=data,
    )
    safe_chapter = re.sub(r"[^A-Za-z0-9]+", "-", selected.title).strip("-") or "Chapter"
    filename = f"Class{class_level}-{subject_meta['label'].replace(' ', '')}-{safe_chapter}-Lesson-Plan.pdf"
    return pdf, filename
