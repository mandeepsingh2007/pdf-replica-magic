import json
import logging
import os
import random
import re
from typing import Callable, Awaitable

from app.schemas.question_schemas import (
    MCQListSchema,
    TrueFalseListSchema,
    FillInBlankListSchema,
    WordMatchListSchema,
    PictureMatchListSchema,
    AssertionReasonListSchema,
    ShortAnswerListSchema,
)
from app.services.llm_service import generate_structured_output
from app.services.vlm_service import (
    enrich_picture_match_labels,
    heuristic_short_label_from_description,
    is_junk_label,
    is_placeholder_description,
    short_label_for_image,
    short_label_for_image_lowmem,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

META_TERMS = ("retrieved", "vector database", "embedding", "chunk", "selected subject")

PDF_ONLY_RULES = (
    "Create questions strictly from the textbook excerpt. "
    "Each question must reference concepts, terms, or facts present in the excerpt. "
    "Do NOT use general knowledge outside the excerpt."
)

STANDALONE_PAPER_RULES = (
    "The student sees ONLY the question on the paper — no textbook excerpt, passage, or reading block. "
    "Never write 'provided text', 'the passage', 'the excerpt', 'above text', or 'following text'. "
    "Ask directly (e.g. 'Which of the following is a Popular Indian?' not 'mentioned in the provided text')."
)

_PASSAGE_PHRASE_RE = re.compile(
    r"provided text|the passage|reading passage|above text|following text|given text|"
    r"in the text|from the text|according to the (?:passage|text|excerpt)|"
    r"as (?:mentioned|stated|described) in",
    re.I,
)

ProgressCallback = Callable[[int, str], Awaitable[None]]


def quota_for_type(q_type: str, questions_per_type: int = 5) -> int:
    """Match-the-following is 1 exercise with 5 pairs, not 5 separate exercises."""
    if q_type in MATCH_FORMAT_TYPES:
        return MATCH_QUESTIONS_PER_FORMAT
    return questions_per_type

MIN_USABLE_IMAGE_PX = 120
MIN_MATCH_AREA_PX = 18_000
MAX_MATCH_ASPECT = 3.5
MAX_MATCH_BBOX_AREA_FRAC = 0.45
PDF_PAGE_AREA_PT = 595.0 * 842.0
MATCH_PAIRS_PER_QUESTION = 5
MATCH_QUESTIONS_PER_FORMAT = 1
MATCH_FORMAT_TYPES = frozenset({"word_match", "picture_match"})

# When strict filters leave too few images, relax geometry — still skip strips/page sections.
MATCH_QUALITY_TIERS: dict[str, dict[str, float]] = {
    "strict": {
        "min_side": 120,
        "min_area": 18_000,
        "max_aspect": 3.5,
        "max_bbox_frac": 0.45,
    },
    "relaxed": {
        "min_side": 90,
        "min_area": 10_000,
        "max_aspect": 4.5,
        "max_bbox_frac": 0.55,
    },
}
SKIP_MATCH_DESCRIPTIONS = (
    "list of",
    "word check",
    "activity for",
    "qr code",
    "test paper",
    "sl. no",
    "table of contents",
    "missing numbers",
    "logical reasoning",
    "textbook page",
    "page from",
    "title page",
    "chapter title",
    "worksheet",
    "exercise box",
    "paragraph of text",
    "block of text",
    "multiple illustrations",
    "several pictures",
    "two-panel",
    "two separate illustration",
    "two separate illustrations",
    "stacked vertically",
    "distinct images stacked",
    "semester",
    "publisher",
)


def _is_illustration_image(img: dict) -> bool:
    """Skip text blocks / worksheets — keep real pictures for match questions."""
    desc = (img.get("description") or img.get("caption") or "").lower()
    return not any(skip in desc for skip in SKIP_MATCH_DESCRIPTIONS)


def _sample_image_stats(path: str) -> dict | None:
    """Lightweight pixel heuristics — drop text-heavy / blank crops."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            thumb = rgb.resize((min(64, w), min(64, h)))
            pixels = list(thumb.getdata())
        if not pixels:
            return None
        white = sum(1 for r, g, b in pixels if r >= 235 and g >= 235 and b >= 235)
        white_ratio = white / len(pixels)
        colorish = sum(
            1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) > 38
        )
        color_frac = colorish / len(pixels)
        return {
            "width": w,
            "height": h,
            "white_ratio": white_ratio,
            "color_frac": color_frac,
        }
    except Exception:
        return None


def _passes_match_geometry(
    img: dict,
    stats: dict,
    *,
    min_side: float = MIN_USABLE_IMAGE_PX,
    min_area: float = MIN_MATCH_AREA_PX,
    max_aspect: float = MAX_MATCH_ASPECT,
    max_bbox_frac: float = MAX_MATCH_BBOX_AREA_FRAC,
) -> bool:
    w, h = stats["width"], stats["height"]
    short, long = min(w, h), max(w, h)
    if short < min_side:
        return False
    if long / max(short, 1) > max_aspect:
        return False
    if w * h < min_area:
        return False

    bw = img.get("bbox_width") or 0
    bh = img.get("bbox_height") or 0
    if bw > 0 and bh > 0:
        if (bw * bh) / PDF_PAGE_AREA_PT > max_bbox_frac:
            return False
        aspect = bw / max(bh, 1.0)
        if bh / 842.0 < 0.07 and aspect > 1.8:
            return False

    wr = stats["white_ratio"]
    cf = stats["color_frac"]
    if wr > 0.85 and cf < 0.06 and w * h > 280_000:
        return False
    if wr > 0.93 and cf < 0.04:
        return False
    return True


def filter_quality_images(
    images: list[dict],
    *,
    tier: str = "strict",
    min_side: int | None = None,
) -> list[dict]:
    """Keep square-ish illustrations; reject leftover stacked composites."""
    from app.services.image_quality import is_stacked_composite

    cfg = MATCH_QUALITY_TIERS.get(tier, MATCH_QUALITY_TIERS["strict"])
    side = min_side if min_side is not None else int(cfg["min_side"])
    usable: list[dict] = []
    for img in images:
        if not _is_illustration_image(img):
            continue
        path = img.get("image_path")
        if not path or not os.path.isfile(path):
            continue
        stats = _sample_image_stats(path)
        if not stats:
            continue
        if stats["width"] < side or stats["height"] < side:
            continue
        if not _passes_match_geometry(
            img,
            stats,
            min_side=cfg["min_side"],
            min_area=cfg["min_area"],
            max_aspect=cfg["max_aspect"],
            max_bbox_frac=cfg["max_bbox_frac"],
        ):
            continue
        if is_stacked_composite(path):
            continue
        usable.append({**img, "width": stats["width"], "height": stats["height"]})
    return usable


def _allocate_picture_pool(images: list[dict]) -> list[dict]:
    """Shuffle once; consume sequentially so no image repeats until pool exhausted."""
    pool = list(images)
    random.shuffle(pool)
    return pool


def question_contains_meta_terms(question_data: dict, source_context: str) -> bool:
    """Reject infrastructure/meta questions unless those terms appear in the source PDF text."""
    text_blob = json.dumps(question_data).lower()
    source_lower = source_context.lower()
    for term in META_TERMS:
        if term in text_blob and term not in source_lower:
            return True
    if "context" in text_blob and "context" not in source_lower:
        return True
    return False


def sample_chunk_context(chunks: list, batch_index: int, batch_size: int | None = None) -> str:
    """Pick a random rotating slice so each generation run sees different textbook pages."""
    if not chunks:
        return ""
    batch_size = batch_size or settings.CHUNKS_PER_GENERATION_BATCH
    n = len(chunks)
    step = max(1, n // batch_size)
    start = (batch_index * 4 + random.randint(0, n - 1)) % n
    selected = [chunks[(start + i * step) % n] for i in range(min(batch_size, n))]
    return "\n\n".join(c.content for c in selected)


def heuristic_quality_score(q_data: dict, context: str) -> float:
    """Fast local scoring — avoids 50+ extra LLM calls that block generation for minutes."""
    if question_contains_meta_terms(q_data, context):
        return 0.0

    text_blob = json.dumps(q_data).lower()
    if len(text_blob) < 25:
        return 0.3

    filler = ("lorem ipsum", "placeholder", "example question", "not available")
    if any(f in text_blob for f in filler):
        return 0.2

    return 0.88


def _mcq_references_unshown_passage(q_data: dict) -> bool:
    text = (q_data.get("question_text") or "").strip()
    return bool(text and _PASSAGE_PHRASE_RE.search(text))


async def generate_mcqs(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    questions: list[dict] = []
    ask = max(count, count + 3)
    for attempt in range(2):
        if len(questions) >= count:
            break
        need = ask if attempt == 0 else count + (count - len(questions))
        prompt = (
            f"Generate EXACTLY {need} multiple choice questions for {subject_name}. "
            f"{PDF_ONLY_RULES} {STANDALONE_PAPER_RULES} Ensure distractors are plausible."
        )
        data = await generate_structured_output(
            prompt, MCQListSchema, context, subject_name, chapter_scope
        )
        if "questions" not in data:
            if data.get("error"):
                logger.error("MCQ generation failed: %s", data.get("error"))
            continue
        for q_data in data["questions"]:
            if len(questions) >= count:
                break
            if _mcq_references_unshown_passage(q_data):
                logger.info(
                    "Dropped MCQ referencing unseen passage: %s",
                    (q_data.get("question_text") or "")[:80],
                )
                continue
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "mcq", "data": q_data, "score": score, "marks": 1})
    return questions[:count]


async def generate_assertion_reason(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} Assertion-Reason questions for {subject_name}. "
        f"{PDF_ONLY_RULES} "
        "Step 1: Write an assertion from the excerpt. Step 2: Write a reason. "
        "Step 3: Analyze logical link. Step 4: Pick correct option A/B/C/D."
    )
    data = await generate_structured_output(
        prompt, AssertionReasonListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "assertion_reason", "data": q_data, "score": score, "marks": 1})
    elif data.get("error"):
        logger.error("Assertion-Reason generation failed: %s", data.get("error"))
    return questions


def _text_mapping_to_keys(column_a: list[str], column_b: list[str], text_map: dict) -> dict[str, str]:
    """Convert LLM text-to-text mapping into stable answer keys (1-4 → a-d)."""
    key_map: dict[str, str] = {}
    for i, a_item in enumerate(column_a):
        matched = text_map.get(a_item)
        if matched in column_b:
            b_idx = column_b.index(matched)
        else:
            b_idx = i % len(column_b)
        key_map[str(i + 1)] = chr(ord("a") + b_idx)
    return key_map


def _dedupe_labels(labels: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for lbl in labels:
        key = lbl.lower().strip()
        count = seen.get(key, 0)
        seen[key] = count + 1
        result.append(f"{lbl} ({count + 1})" if count else lbl)
    return result


def runtime_vision_enabled() -> bool:
    """Gemini vision + full image bytes can OOM on small hosts during picture-match."""
    if os.getenv("SKIP_RUNTIME_VLM") == "1":
        return False
    if os.getenv("SKIP_RUNTIME_VLM") == "0":
        return True
    return not os.getenv("RENDER")


def _filename_hint(img: dict) -> str:
    path = img.get("image_path") or ""
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"^PDF\d+_P\d+_IMG\d+", "Figure", stem, flags=re.I)
    return stem.replace("_", " ").strip() or "Figure"


async def _labels_for_images(selected: list[dict]) -> list[str]:
    """Proper names from the photo — never filenames or 'man in glasses'."""
    labels: list[str] = []
    for img in selected:
        path = img.get("image_path")
        label = ""
        if path and os.path.isfile(path):
            if runtime_vision_enabled():
                label = await short_label_for_image(path)
            if not label or is_junk_label(label):
                label = await short_label_for_image_lowmem(path)
        if not label or is_junk_label(label):
            desc = (img.get("description") or img.get("caption") or "").strip()
            label = heuristic_short_label_from_description(desc)
        labels.append(label or "")
    labels = await enrich_picture_match_labels(labels, selected)
    return _dedupe_labels(labels)


def _finalize_picture_match(
    q_data: dict, images: list[dict], context: str
) -> dict | None:
    pairs = MATCH_PAIRS_PER_QUESTION
    labels = q_data.get("labels", [])[:pairs]
    captions = q_data.get("picture_captions", [])[:pairs]
    mapping = q_data.get("correct_mapping", {})
    if len(labels) < pairs:
        return None

    q_data["labels"] = labels
    if len(captions) >= pairs:
        q_data["pictures"] = [{"caption": captions[i]} for i in range(pairs)]
    else:
        q_data["pictures"] = [{"caption": f"Figure {i + 1}"} for i in range(pairs)]

    q_data["correct_label_by_figure"] = {
        str(i + 1): mapping.get(str(i + 1), labels[i]) for i in range(pairs)
    }
    score = heuristic_quality_score(q_data, context)
    return {"type": "picture_match", "data": q_data, "score": score, "marks": 5}


async def _generate_picture_match_from_images(
    images: list[dict],
    count: int,
    subject_name: str,
    context: str,
    used_image_ids: set[int] | None = None,
) -> list[dict]:
    """Build picture-match questions — one exercise uses 5 unique images."""
    questions: list[dict] = []
    pairs = MATCH_PAIRS_PER_QUESTION
    pool = _allocate_picture_pool(images)
    cursor = 0

    if len(pool) < pairs:
        return questions

    for q_idx in range(count):
        selected: list[dict] = []
        while len(selected) < pairs and cursor < len(pool):
            candidate = pool[cursor]
            cursor += 1
            if candidate in selected:
                continue
            selected.append(candidate)

        if len(selected) < pairs:
            logger.warning(
                "Picture match: need %d images, only found %d at question %d/%d",
                pairs,
                len(selected),
                q_idx + 1,
                count,
            )
            break

        labels = await _labels_for_images(selected)
        if len(labels) < pairs:
            continue

        correct_label_by_figure = {str(i + 1): labels[i] for i in range(pairs)}
        q_data = {
            "labels": labels[:pairs],
            "correct_label_by_figure": correct_label_by_figure,
            "pictures": [
                {"image_id": img["id"], "caption": labels[i]}
                for i, img in enumerate(selected)
            ],
        }
        if len(q_data["pictures"]) < pairs or len(q_data["labels"]) < pairs:
            continue

        if used_image_ids is not None:
            used_image_ids.update(img["id"] for img in selected)

        score = heuristic_quality_score(q_data, context)
        questions.append({"type": "picture_match", "data": q_data, "score": score, "marks": 5})

    return questions


async def generate_word_match(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} 'Match the Following' word-matching questions for {subject_name}. "
        f"Each question must have exactly {MATCH_PAIRS_PER_QUESTION} items in column_a and "
        f"{MATCH_PAIRS_PER_QUESTION} related items in column_b. "
        f"correct_mapping must map each column_a item text to its matching column_b item text. "
        f"{PDF_ONLY_RULES}"
    )
    data = await generate_structured_output(
        prompt, WordMatchListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            col_a = q_data.get("column_a", [])[:MATCH_PAIRS_PER_QUESTION]
            col_b = q_data.get("column_b", [])[:MATCH_PAIRS_PER_QUESTION]
            if len(col_a) < MATCH_PAIRS_PER_QUESTION or len(col_b) < MATCH_PAIRS_PER_QUESTION:
                continue
            q_data["column_a"] = col_a
            q_data["column_b"] = col_b
            q_data["correct_mapping_keys"] = _text_mapping_to_keys(
                col_a, col_b, q_data.get("correct_mapping", {})
            )
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "word_match", "data": q_data, "score": score, "marks": 5})
    elif data.get("error"):
        logger.error("Word match generation failed: %s", data.get("error"))
    return questions


async def _generate_picture_match_llm(
    context: str,
    count: int,
    subject_name: str,
    chapter_scope: str | None,
) -> list[dict]:
    pairs = MATCH_PAIRS_PER_QUESTION
    prompt = (
        f"Generate EXACTLY {count} 'Match the picture with text' questions for {subject_name}. "
        f"Each question must have exactly {pairs} picture_captions (diagram descriptions from the excerpt), "
        f"{pairs} labels (short terms), and correct_mapping with keys '1'-'{pairs}' mapping to label text. "
        f"{PDF_ONLY_RULES}"
    )
    data = await generate_structured_output(
        prompt, PictureMatchListSchema, context, subject_name, chapter_scope
    )
    questions: list[dict] = []
    if "questions" in data:
        for q_data in data["questions"]:
            finalized = _finalize_picture_match(q_data, [], context)
            if finalized:
                questions.append(finalized)
    elif data.get("error"):
        logger.error("Picture match LLM fallback failed: %s", data.get("error"))
    return questions


async def generate_picture_match(
    context: str,
    count: int,
    subject_name: str,
    images: list[dict],
    chapter_scope: str | None = None,
    used_image_ids: set[int] | None = None,
) -> list[dict]:
    pairs = MATCH_PAIRS_PER_QUESTION
    used: set[int] = set(used_image_ids or ())
    questions: list[dict] = []

    for tier in ("strict", "relaxed"):
        tier_images = filter_quality_images(images, tier=tier)
        available = [img for img in tier_images if img["id"] not in used]
        if len(available) < pairs:
            logger.info(
                "Picture match tier=%s: %d usable images (need %d more ids)",
                tier,
                len(available),
                pairs * (count - len(questions)) - len(available),
            )
            continue

        batch = await _generate_picture_match_from_images(
            available,
            count - len(questions),
            subject_name,
            context,
            used,
        )
        questions.extend(batch)
        logger.info(
            "Picture match tier=%s: +%d questions (total %d/%d)",
            tier,
            len(batch),
            len(questions),
            count,
        )
        if len(questions) >= count:
            return questions[:count]

    remaining = count - len(questions)
    if remaining > 0:
        logger.warning(
            "Picture match: only %d/%d from images — LLM fallback for %d",
            len(questions),
            count,
            remaining,
        )
        llm_batch = await _generate_picture_match_llm(
            context, remaining, subject_name, chapter_scope
        )
        questions.extend(llm_batch[:remaining])

    logger.info("Picture match: %d questions ready", len(questions[:count]))
    return questions[:count]


async def generate_true_false(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} True/False statements for {subject_name}. "
        f"{PDF_ONLY_RULES}"
    )
    data = await generate_structured_output(
        prompt, TrueFalseListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "true_false", "data": q_data, "score": score, "marks": 1})
    elif data.get("error"):
        logger.error("True/False generation failed: %s", data.get("error"))
    return questions


async def generate_fill_blank(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} fill-in-the-blank sentences for {subject_name}. "
        f"{PDF_ONLY_RULES} Use key facts from the excerpt."
    )
    data = await generate_structured_output(
        prompt, FillInBlankListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "fill_blank", "data": q_data, "score": score, "marks": 1})
    elif data.get("error"):
        logger.error("Fill-in-blank generation failed: %s", data.get("error"))
    return questions


async def generate_short_answer(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} short subjective questions for {subject_name}. "
        f"These questions require a brief typed answer from the student. "
        f"{PDF_ONLY_RULES} Provide an ideal detailed answer and a grading rubric."
    )
    data = await generate_structured_output(
        prompt, ShortAnswerListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "short_answer", "data": q_data, "score": score, "marks": 2})
    elif data.get("error"):
        logger.error("Short answer generation failed: %s", data.get("error"))
    return questions



VALID_QUESTION_TYPES = frozenset({
    "mcq",
    "assertion_reason",
    "true_false",
    "fill_blank",
    "word_match",
    "picture_match",
    "short_answer",
})

DEFAULT_TYPE_COUNTS: dict[str, int] = {
    "mcq": 15,
    "assertion_reason": 10,
    "word_match": 5,
    "picture_match": 5,
    "true_false": 10,
    "fill_blank": 10,
    "short_answer": 5,
}


async def generate_all_types(
    chunks: list,
    image_metadata: list,
    subject_name: str,
    on_progress: ProgressCallback | None = None,
    include_types: list[str] | None = None,
    questions_per_type: int = 5,
    chapter_scope: str | None = None,
) -> list[dict]:
    """
    Generate exactly `questions_per_type` questions for each selected format.
    Each format uses a different random textbook slice for variety across runs.
    """
    all_generators: list[tuple] = [
        ("MCQs", generate_mcqs, "mcq", 0),
        ("Assertion-Reason", generate_assertion_reason, "assertion_reason", 1),
        ("Word Match", generate_word_match, "word_match", 2),
        ("Picture Match", generate_picture_match, "picture_match", 3),
        ("True/False", generate_true_false, "true_false", 4),
        ("Fill in the Blank", generate_fill_blank, "fill_blank", 5),
        ("Short Answer", generate_short_answer, "short_answer", 6),
    ]

    if include_types:
        allowed = {t for t in include_types if t in VALID_QUESTION_TYPES}
        generators = [g for g in all_generators if g[2] in allowed]
    else:
        generators = all_generators

    if not generators:
        return []

    all_questions: list[dict] = []
    total = len(generators)
    used_image_ids: set[int] = set()

    for i, entry in enumerate(generators):
        label, gen_fn, q_type, batch_idx = entry
        if on_progress:
            pct = 32 + int((i / total) * 46)
            await on_progress(pct, f"Generating {label} from textbook ({i + 1}/{total})")

        context = sample_chunk_context(chunks, batch_idx + random.randint(0, 3))
        keep = quota_for_type(q_type, questions_per_type)
        if gen_fn is generate_picture_match:
            result = await gen_fn(
                context,
                keep,
                subject_name,
                image_metadata,
                chapter_scope,
                used_image_ids,
            )
            picked = result[:keep]
        else:
            extra = 0 if q_type in MATCH_FORMAT_TYPES else 2
            result = await gen_fn(context, keep + extra, subject_name, chapter_scope)
            result.sort(key=lambda q: q.get("score", 0), reverse=True)
            picked = result[:keep]

        all_questions.extend(picked)
        logger.info("%s: generated %d, kept %d", label, len(result), len(picked))

    return all_questions
