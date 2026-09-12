from app.core.config import settings
import google.generativeai as genai
import json
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

if settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

_llm_concurrency = max(1, int(os.getenv("LLM_MAX_CONCURRENT", "2")))
llm_semaphore = asyncio.Semaphore(_llm_concurrency)


def truncate_context(context: str, max_chars: int | None = None) -> str:
    limit = max_chars or settings.MAX_LLM_CONTEXT_CHARS
    if len(context) <= limit:
        return context
    return context[:limit] + "\n\n[...excerpt truncated for length...]"


def build_textbook_prompt(
    prompt: str,
    context: str,
    subject_name: str,
    chapter_scope: str | None = None,
) -> str:
    excerpt = truncate_context(context)
    scope_block = ""
    if chapter_scope:
        scope_block = f"""
CHAPTER SCOPE (mandatory):
Generate questions ONLY from these selected chapters — ignore all other material:
{chapter_scope}
"""
    return f"""You are an exam paper setter for {subject_name}.
Use ONLY the textbook excerpt below. Do NOT invent facts.
Do NOT ask about retrieval systems, databases, AI, or the word "context".
Every question must be answerable from the excerpt alone.
{scope_block}
TEXTBOOK EXCERPT:
{excerpt}

TASK:
{prompt}"""


async def generate_structured_output(
    prompt: str,
    schema_class,
    context: str,
    subject_name: str = "the subject",
    chapter_scope: str | None = None,
) -> dict:
    """
    Calls the LLM (Gemini) with structured JSON output matching the Pydantic schema.
    """
    full_prompt = build_textbook_prompt(prompt, context, subject_name, chapter_scope)

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not found. Returning mocked response.")
        return {"mocked": True, "schema": schema_class.__name__}

    try:
        model = genai.GenerativeModel(settings.LLM_MODEL)
        async with llm_semaphore:
            response = await asyncio.wait_for(
                model.generate_content_async(
                    full_prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=schema_class,
                    ),
                ),
                timeout=settings.LLM_CALL_TIMEOUT_SEC,
            )
        return json.loads(response.text)
    except asyncio.TimeoutError:
        logger.error("LLM generation timed out after %ss", settings.LLM_CALL_TIMEOUT_SEC)
        return {"error": "timeout", "schema": schema_class.__name__}
    except Exception as e:
        logger.error("LLM generation error: %s", e)
        return {"error": str(e), "schema": schema_class.__name__}


async def evaluate_question_quality(
    question_data: dict, context: str, subject_name: str = "the subject"
) -> float:
    """
    Optional LLM judge — kept for spot checks; prefer heuristic scoring in the hot path.
    """
    if not settings.GEMINI_API_KEY:
        return 0.95

    try:
        model = genai.GenerativeModel(settings.LLM_MODEL)
        prompt = (
            f"Evaluate whether this exam question is grounded in the textbook excerpt for {subject_name}.\n"
            f"Penalize heavily if the question is about retrieval systems, databases, AI, or meta-infrastructure.\n"
            f"Penalize if the answer cannot be found in the excerpt.\n\n"
            f"TEXTBOOK EXCERPT:\n{truncate_context(context, 6000)}\n\n"
            f"Question Data: {json.dumps(question_data)}\n\n"
            f"Return ONLY a float number between 0.0 and 1.0 representing the score. No other text."
        )
        async with llm_semaphore:
            response = await asyncio.wait_for(
                model.generate_content_async(prompt),
                timeout=60,
            )
        score_text = response.text.strip()
        try:
            return float(score_text)
        except ValueError:
            return 0.8
    except Exception as e:
        logger.warning("LLM evaluation error: %s", e)
        return 0.8


async def evaluate_student_answer(
    question_data: dict,
    user_answer: str,
    context: str,
    subject_name: str = "the subject",
    max_marks: int = 3,
) -> dict:
    """
    Grade a subjective answer against the textbook excerpt.
    Returns marks_awarded, feedback, and correct_answer grounded in the PDF.
    """
    if not user_answer or not user_answer.strip():
        return {
            "marks_awarded": 0,
            "feedback": "No answer provided.",
            "correct_answer": question_data.get("ideal_answer", ""),
        }

    ideal = question_data.get("ideal_answer", "")
    rubric = question_data.get("grading_rubric", [])
    question_text = question_data.get("question", "")

    if not settings.GEMINI_API_KEY:
        user_lower = user_answer.lower()
        rubric_hits = sum(1 for pt in rubric if pt.lower() in user_lower)
        ratio = rubric_hits / max(len(rubric), 1)
        marks = round(max_marks * ratio)
        return {
            "marks_awarded": marks,
            "feedback": "Graded using keyword match (no API key).",
            "correct_answer": ideal,
        }

    rubric_text = "\n".join(f"- {pt}" for pt in rubric) if rubric else "Cover all key points from the textbook."

    prompt = f"""You are grading a Class 1 {subject_name} exam answer.
Use the textbook excerpt below. Also use the IDEAL ANSWER and RUBRIC as grading guides.

QUESTION: {question_text}

IDEAL ANSWER (reference): {ideal}

GRADING RUBRIC:
{rubric_text}

STUDENT ANSWER: {user_answer}

Grade fairly. Award 0 to {max_marks} marks.
- Full marks ({max_marks}) if the student covers the key ideas, even with different wording.
- Partial marks (1 to {max_marks - 1}) if some key points are correct but incomplete.
- Zero only if the answer is wrong or unrelated.
- Do NOT penalize for informal language or Hinglish if facts are correct.

Return ONLY valid JSON:
{{
  "marks_awarded": <integer 0 to {max_marks}>,
  "feedback": "<brief explanation for the student>",
  "correct_answer": "<ideal answer phrased from the textbook excerpt>"
}}"""

    excerpt = context[:8000] if len(context) > 8000 else context
    full_prompt = f"""You are an exam grader for {subject_name}.
Use ONLY the textbook excerpt below.

TEXTBOOK EXCERPT:
{excerpt}

TASK:
{prompt}"""

    try:
        model = genai.GenerativeModel(settings.LLM_MODEL)
        async with llm_semaphore:
            response = await asyncio.wait_for(
                model.generate_content_async(
                    full_prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                    ),
                ),
                timeout=90,
            )
        result = json.loads(response.text)
        marks = int(result.get("marks_awarded", 0))
        marks = max(0, min(marks, max_marks))
        return {
            "marks_awarded": marks,
            "feedback": result.get("feedback", ""),
            "correct_answer": result.get("correct_answer", ideal),
        }
    except Exception as e:
        logger.warning("Student answer evaluation error: %s", e)
        user_lower = user_answer.lower()
        rubric_hits = sum(1 for pt in rubric if pt.lower() in user_lower)
        ratio = rubric_hits / max(len(rubric), 1)
        marks = round(max_marks * ratio) if ratio >= 0.5 else 0
        return {
            "marks_awarded": marks,
            "feedback": f"Auto-graded using rubric keywords. {e}",
            "correct_answer": ideal,
        }
