import json
import random
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.generated_test import GeneratedTest
from app.models.subject import Subject
from app.services.llm_service import evaluate_student_answer

AR_OPTION_LABELS = {
    "A": "Both A and R are true and R is the correct explanation of A",
    "B": "Both A and R are true but R is not the correct explanation of A",
    "C": "A is true but R is false",
    "D": "A is false but R is true",
}

SECTION_KEYS = [
    ("section_A_MCQs", "A"),
    ("section_B_AssertionReason", "B"),
    ("section_C_Objective", "C"),
    ("section_D_MatchFollowing", "D"),
    ("section_D_Subjective", "D"),  # legacy tests
]

STOPWORDS = frozenset({
    "that", "this", "with", "from", "they", "have", "been", "were", "what",
    "when", "which", "their", "there", "about", "would", "could", "should",
    "following", "correct", "option", "answer", "question", "statement",
})


@dataclass
class PdfChunk:
    content: str
    page_number: int | None


@dataclass
class TextbookReference:
    excerpt: str
    page_number: int | None


def parse_test_data(test: GeneratedTest) -> dict:
    if isinstance(test.test_data, str):
        return json.loads(test.test_data)
    return test.test_data or {}


def flatten_questions(test_data: dict) -> list[dict]:
    questions = []
    for section_key, section_label in SECTION_KEYS:
        for q in test_data.get(section_key, []):
            q_copy = dict(q)
            q_copy["section"] = section_label
            questions.append(q_copy)
    return questions


def stable_shuffle(options: list[str], seed: int) -> list[str]:
    rng = random.Random(seed)
    shuffled = list(options)
    rng.shuffle(shuffled)
    return shuffled


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_question_data(data: Any) -> dict:
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {}
    return data or {}


def _shuffled_match_items(texts: list[str], seed: int) -> list[dict]:
    items = [{"key": chr(ord("a") + i), "text": text} for i, text in enumerate(texts)]
    return stable_shuffle(items, seed=seed)


def compute_expected_match_keys(
    q_type: str, q_data: dict, question_id: int | None
) -> dict[str, str]:
    """Answer keys after the right column is shuffled for display."""
    seed = question_id or 0

    if q_type == "picture_match":
        labels = q_data.get("labels", [])[:5]
        by_figure = q_data.get("correct_label_by_figure") or {
            str(i + 1): labels[i] for i in range(len(labels))
        }
        shuffled = _shuffled_match_items(labels, seed)
        text_to_key = {item["text"]: item["key"] for item in shuffled}
        return {
            fig: text_to_key[text]
            for fig, text in by_figure.items()
            if text in text_to_key
        }

    if q_type == "word_match":
        col_a = q_data.get("column_a", [])[:5]
        col_b = q_data.get("column_b", [])[:5]
        text_map = q_data.get("correct_mapping", {})
        shuffled = _shuffled_match_items(col_b, seed)
        text_to_key = {item["text"]: item["key"] for item in shuffled}
        result: dict[str, str] = {}
        for i, a_item in enumerate(col_a):
            correct_text = text_map.get(a_item)
            if correct_text is None and i < len(col_b):
                correct_text = col_b[i]
            if correct_text in text_to_key:
                result[str(i + 1)] = text_to_key[correct_text]
        return result

    return q_data.get("correct_mapping_keys", {})


def _build_match_display(q_data: dict, q_type: str, q_id: int) -> dict:
    """Student-safe match question with shuffled right column / labels."""
    if q_type == "word_match":
        col_a = q_data.get("column_a", [])[:5]
        col_b = q_data.get("column_b", [])[:5]
        b_items = [{"key": chr(ord("a") + i), "text": text} for i, text in enumerate(col_b)]
        b_items = stable_shuffle(b_items, seed=q_id or 0)
        return {
            "column_a": [{"key": str(i + 1), "text": text} for i, text in enumerate(col_a)],
            "column_b": b_items,
        }

    pictures = q_data.get("pictures", [])[:5]
    labels = q_data.get("labels", [])[:5]
    label_items = [{"key": chr(ord("a") + i), "text": text} for i, text in enumerate(labels)]
    label_items = stable_shuffle(label_items, seed=q_id or 0)
    return {
        "pictures": [
            {
                "key": str(i + 1),
                "image_id": pic.get("image_id"),
                "caption": pic.get("caption", f"Figure {i + 1}"),
            }
            for i, pic in enumerate(pictures)
        ],
        "labels": label_items,
    }


def parse_user_mapping(user_answer: Any) -> dict[str, str]:
    if user_answer is None:
        return {}
    if isinstance(user_answer, dict):
        return {str(k): str(v) for k, v in user_answer.items()}
    if isinstance(user_answer, str) and user_answer.strip():
        try:
            parsed = json.loads(user_answer)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            pass
    return {}


def strip_answer_keys(question: dict) -> dict:
    """Build student-safe question payload without answer keys."""
    q_data = parse_question_data(question.get("data"))
    q_type = question.get("type")
    q_id = question.get("id")
    base = {
        "id": q_id,
        "type": q_type,
        "marks": question.get("marks", 1),
        "section": question.get("section", ""),
    }

    if q_type == "mcq":
        options = stable_shuffle(
            [q_data.get("correct_answer", "")] + list(q_data.get("distractors", [])),
            seed=q_id or 0,
        )
        base["display"] = {
            "question_text": q_data.get("question_text", ""),
            "options": [o for o in options if o],
        }
    elif q_type == "assertion_reason":
        base["display"] = {
            "assertion": q_data.get("assertion", ""),
            "reason": q_data.get("reason", ""),
            "options": [{"code": k, "label": v} for k, v in AR_OPTION_LABELS.items()],
        }
    elif q_type == "true_false":
        base["display"] = {"statement": q_data.get("statement", "")}
    elif q_type == "fill_blank":
        base["display"] = {"sentence_with_blank": q_data.get("sentence_with_blank", "")}
    elif q_type in ("word_match", "picture_match"):
        base["display"] = _build_match_display(q_data, q_type, q_id or 0)
    elif q_type in ("short_answer", "long_answer"):
        base["display"] = {"question": q_data.get("question", "")}
    else:
        base["display"] = q_data

    return base


def build_attempt_payload(test: GeneratedTest, subject_name: str) -> dict:
    test_data = parse_test_data(test)
    student_sections: dict[str, list] = {}

    for section_key, _ in SECTION_KEYS:
        student_sections[section_key] = [
            strip_answer_keys(q) for q in test_data.get(section_key, [])
        ]

    all_q = flatten_questions(test_data)
    return {
        "id": test.id,
        "title": test.title or "Untitled Test",
        "subject_name": subject_name,
        "document_id": test.document_id,
        "total_marks": test.total_marks,
        "total_questions": test.total_questions or len(all_q),
        "test_data": student_sections,
    }


async def fetch_pdf_chunks(db: AsyncSession, document_id: int | None, subject_id: int) -> list[PdfChunk]:
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
    return [
        PdfChunk(content=c.content, page_number=c.page_number)
        for c in result.scalars().all()
    ]


def _keywords_for_question(q_type: str, q_data: dict, correct_answer: str) -> list[str]:
    parts: list[str] = []
    if q_type == "mcq":
        parts.append(q_data.get("question_text", ""))
    elif q_type == "assertion_reason":
        parts.extend([q_data.get("assertion", ""), q_data.get("reason", "")])
    elif q_type == "true_false":
        parts.append(q_data.get("statement", ""))
    elif q_type == "fill_blank":
        parts.extend([q_data.get("sentence_with_blank", ""), q_data.get("correct_word", "")])
    elif q_type in ("word_match", "picture_match"):
        parts.extend(q_data.get("column_a", []))
        parts.extend(q_data.get("labels", []))
        for pic in q_data.get("pictures", []):
            parts.append(str(pic.get("caption", "")))
    parts.append(str(correct_answer))
    parts.append(q_data.get("ideal_answer", ""))
    parts.append(q_data.get("explanation", ""))

    blob = " ".join(p for p in parts if p).lower()
    words = []
    for w in re.findall(r"\w{3,}", blob):
        if w not in STOPWORDS and w not in words:
            words.append(w)
    return words[:15]


def _clean_chunk_text(text: str) -> str:
    text = re.sub(r"\[FIGURE:[^\]]*\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_focused_snippet(text: str, keywords: list[str], max_len: int = 380) -> str:
    text = _clean_chunk_text(text)
    if not text:
        return ""
    if len(text) <= max_len:
        return text

    text_lower = text.lower()
    best_start = 0
    best_score = -1
    step = 40

    for start in range(0, max(1, len(text) - max_len + 1), step):
        window = text_lower[start : start + max_len]
        score = sum(2 for kw in keywords if kw in window)
        if score > best_score:
            best_score = score
            best_start = start

    if best_score <= 0:
        best_start = 0

    snippet = text[best_start : best_start + max_len]
    if best_start > 0:
        snippet = "…" + snippet
    if best_start + max_len < len(text):
        snippet = snippet + "…"
    return snippet


def find_textbook_reference(
    chunks: list[PdfChunk], q_type: str, q_data: dict, correct_answer: str
) -> TextbookReference:
    if not chunks:
        return TextbookReference(excerpt="", page_number=None)

    keywords = _keywords_for_question(q_type, q_data, correct_answer)
    best_chunk = chunks[0]
    best_score = -1

    for chunk in chunks:
        content_lower = chunk.content.lower()
        score = sum(3 for kw in keywords if kw in content_lower)
        if score > best_score:
            best_score = score
            best_chunk = chunk

    excerpt = _extract_focused_snippet(best_chunk.content, keywords)
    return TextbookReference(excerpt=excerpt, page_number=best_chunk.page_number)


def format_paper_answer(question: dict) -> str:
    """Answer as printed on this test paper (same shuffle / letters as the student PDF)."""
    q_type = question.get("type") or ""
    q_data = parse_question_data(question.get("data"))
    q_id = question.get("id")

    if q_type == "mcq":
        correct = q_data.get("correct_answer") or ""
        options = [
            o
            for o in stable_shuffle(
                [correct] + list(q_data.get("distractors") or []),
                seed=q_id or 0,
            )
            if o
        ]
        if correct in options:
            return f"{chr(65 + options.index(correct))}. {correct}"
        return correct

    if q_type == "assertion_reason":
        code = (q_data.get("correct_option_code") or "").upper().strip()
        return f"{code}. {AR_OPTION_LABELS.get(code, code)}"

    if q_type == "true_false":
        return "True" if q_data.get("is_true") else "False"

    if q_type == "fill_blank":
        return q_data.get("correct_word") or ""

    if q_type in ("word_match", "picture_match"):
        expected = compute_expected_match_keys(q_type, q_data, q_id)
        display = _build_match_display(q_data, q_type, q_id or 0)
        right_items = (
            display.get("column_b") if q_type == "word_match" else display.get("labels")
        ) or []
        right = {row["key"]: row["text"] for row in right_items}
        lines = []
        for left_key, right_key in sorted(expected.items(), key=lambda x: int(x[0])):
            lines.append(f"({left_key}) → ({right_key}) {right.get(right_key, '')}")
        return "\n".join(lines)

    if q_type in ("short_answer", "long_answer"):
        return q_data.get("ideal_answer") or ""
    return ""


def format_correct_answer(
    q_type: str, q_data: dict, question_id: int | None = None
) -> str:
    if q_type == "mcq":
        return q_data.get("correct_answer", "")
    if q_type == "assertion_reason":
        code = (q_data.get("correct_option_code") or "").upper().strip()
        return f"{code}. {AR_OPTION_LABELS.get(code, code)}"
    if q_type == "true_false":
        return "True" if q_data.get("is_true") else "False"
    if q_type == "fill_blank":
        return q_data.get("correct_word", "")
    if q_type in ("word_match", "picture_match"):
        key_map = compute_expected_match_keys(q_type, q_data, question_id)
        if q_type == "word_match":
            col_a = q_data.get("column_a", [])
            col_b = q_data.get("column_b", [])
            parts = []
            for a_key, b_key in sorted(key_map.items(), key=lambda x: int(x[0])):
                a_idx = int(a_key) - 1
                b_idx = ord(b_key) - ord("a")
                if 0 <= a_idx < len(col_a) and 0 <= b_idx < len(col_b):
                    parts.append(f"{col_a[a_idx]} → {col_b[b_idx]}")
            return "; ".join(parts)
        labels = q_data.get("labels", [])
        parts = []
        for fig_key, label_key in sorted(key_map.items(), key=lambda x: int(x[0])):
            b_idx = ord(label_key) - ord("a")
            if 0 <= b_idx < len(labels):
                parts.append(f"Figure {fig_key} → {labels[b_idx]}")
        return "; ".join(parts)
    if q_type in ("short_answer", "long_answer"):
        return q_data.get("ideal_answer", "")
    return ""


def grade_objective(
    q_type: str,
    q_data: dict,
    user_answer: Any,
    max_marks: int,
    question_id: int | None = None,
) -> tuple[int, bool, str]:
    """Returns (marks_awarded, is_correct, brief_feedback)."""
    if user_answer is None or (isinstance(user_answer, str) and not user_answer.strip()):
        return 0, False, "No answer provided."

    if q_type == "mcq":
        correct = normalize_text(q_data.get("correct_answer", ""))
        user = normalize_text(str(user_answer))
        is_correct = user == correct
        feedback = "Correct!" if is_correct else f"The correct option is: {q_data.get('correct_answer', '')}"
        return (max_marks if is_correct else 0), is_correct, feedback

    if q_type == "assertion_reason":
        correct_code = (q_data.get("correct_option_code") or "").upper().strip()
        user_code = str(user_answer).upper().strip()
        if len(user_code) > 1:
            for code, label in AR_OPTION_LABELS.items():
                if normalize_text(user_code) == normalize_text(label):
                    user_code = code
                    break
        is_correct = user_code == correct_code
        feedback = "Correct!" if is_correct else f"The correct option is {correct_code}."
        if not is_correct and q_data.get("logical_analysis"):
            feedback += f" {q_data['logical_analysis']}"
        return (max_marks if is_correct else 0), is_correct, feedback

    if q_type == "true_false":
        correct_bool = bool(q_data.get("is_true"))
        user_str = str(user_answer).lower().strip()
        user_bool = user_str in ("true", "t", "1", "yes")
        if user_str in ("false", "f", "0", "no"):
            user_bool = False
        is_correct = user_bool == correct_bool
        correct_label = "True" if correct_bool else "False"
        feedback = "Correct!" if is_correct else f"The correct answer is {correct_label}."
        if not is_correct and q_data.get("explanation"):
            feedback += f" {q_data['explanation']}"
        return (max_marks if is_correct else 0), is_correct, feedback

    if q_type == "fill_blank":
        correct = normalize_text(q_data.get("correct_word", ""))
        user = normalize_text(str(user_answer))
        is_correct = user == correct
        feedback = "Correct!" if is_correct else f"The correct word is: {q_data.get('correct_word', '')}"
        return (max_marks if is_correct else 0), is_correct, feedback

    if q_type in ("word_match", "picture_match"):
        key_map = compute_expected_match_keys(q_type, q_data, question_id)
        user_map = parse_user_mapping(user_answer)
        if not user_map:
            return 0, False, "No answer provided."

        total_pairs = len(key_map)
        correct_count = sum(
            1 for k, expected in key_map.items() if user_map.get(str(k)) == expected
        )
        marks_awarded = int(round((correct_count / total_pairs) * max_marks)) if total_pairs else 0
        is_correct = correct_count == total_pairs
        if is_correct:
            feedback = "Correct!"
        else:
            feedback = (
                f"{correct_count} of {total_pairs} matches correct. "
                f"See correct mapping: {format_correct_answer(q_type, q_data, question_id)}"
            )
        return marks_awarded, is_correct, feedback

    return 0, False, "Unknown question type."


def heuristic_short_answer_score(
    user_answer: str, question_data: dict, max_marks: int
) -> tuple[int, bool] | None:
    """Fast path for common answers — avoids harsh LLM grading."""
    user_l = user_answer.lower()
    question = question_data.get("question", "").lower()

    if "two main parts" in question or ("root" in question and "shoot" in question):
        has_root = "root" in user_l
        has_shoot = "shoot" in user_l
        has_root_loc = any(w in user_l for w in ("soil", "below", "underground", "ground", "beneath"))
        has_shoot_loc = any(w in user_l for w in ("above", "upper", "aerial", "sky"))
        if has_root and has_shoot and has_root_loc and has_shoot_loc:
            return max_marks, True
        if has_root and has_shoot:
            return max(1, max_marks - 1), False

    if "computational thinking" in question:
        ct_terms = ("decomposition", "pattern", "algorithm", "debugging", "observe", "step")
        hits = sum(1 for t in ct_terms if t in user_l)
        plant_terms = ("root", "stem", "leaf", "shoot", "flower", "plant")
        plant_hits = sum(1 for t in plant_terms if t in user_l)
        if hits >= 2 and plant_hits >= 2:
            return max_marks, True
        if hits >= 1 and plant_hits >= 1:
            return max(1, max_marks - 1), False

    return None


async def grade_test(
    test: GeneratedTest,
    answers: dict[str, Any],
    chunks: list[PdfChunk],
    subject_name: str,
) -> dict:
    test_data = parse_test_data(test)
    questions = flatten_questions(test_data)

    results = []
    total_score = 0
    max_score = 0

    for q in questions:
        q_id = str(q.get("id"))
        q_type = q.get("type")
        q_data = parse_question_data(q.get("data"))
        max_marks = int(q.get("marks", 1))
        max_score += max_marks

        user_answer = answers.get(q_id)
        correct_answer = format_correct_answer(q_type, q_data, q.get("id"))

        if q_type in ("short_answer", "long_answer"):
            user_text = str(user_answer or "")
            heuristic = heuristic_short_answer_score(user_text, q_data, max_marks)
            if heuristic:
                marks_awarded, is_correct = heuristic
                feedback = "Correct!" if is_correct else "Good attempt — add more detail from the textbook."
            else:
                ref = find_textbook_reference(chunks, q_type, q_data, correct_answer)
                eval_result = await evaluate_student_answer(
                    question_data=q_data,
                    user_answer=user_text,
                    context=ref.excerpt or chunks[0].content if chunks else "",
                    subject_name=subject_name,
                    max_marks=max_marks,
                )
                marks_awarded = eval_result["marks_awarded"]
                is_correct = marks_awarded == max_marks
                feedback = eval_result["feedback"]
                if not is_correct and eval_result.get("correct_answer"):
                    correct_answer = eval_result["correct_answer"]
        else:
            marks_awarded, is_correct, feedback = grade_objective(
                q_type, q_data, user_answer, max_marks, question_id=q.get("id")
            )

        total_score += marks_awarded

        ref = find_textbook_reference(chunks, q_type, q_data, correct_answer)

        correction = ""
        if not is_correct:
            correction = feedback

        results.append({
            "question_id": q.get("id"),
            "section": q.get("section"),
            "type": q_type,
            "marks_awarded": marks_awarded,
            "max_marks": max_marks,
            "is_correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "correction": correction.strip(),
            "pdf_excerpt": ref.excerpt if not is_correct else "",
            "pdf_page_number": ref.page_number if not is_correct else None,
        })

    return {
        "total_score": total_score,
        "max_score": max_score,
        "percentage": round((total_score / max_score * 100) if max_score else 0, 1),
        "results": results,
    }


async def load_test_with_subject(db: AsyncSession, test_id: int) -> tuple[GeneratedTest, str]:
    result = await db.execute(select(GeneratedTest).where(GeneratedTest.id == test_id))
    test = result.scalars().first()
    if not test:
        raise ValueError("Test not found")

    subject_name = "the subject"
    if test.subject_id:
        sub_result = await db.execute(select(Subject).where(Subject.id == test.subject_id))
        subject = sub_result.scalars().first()
        if subject:
            subject_name = subject.display_name or subject.name

    return test, subject_name
