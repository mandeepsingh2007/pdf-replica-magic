import gc
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
    OralListSchema,
    WhoSaidListSchema,
    CreativeWorkListSchema,
)
from app.services.llm_service import generate_structured_output
from app.services.image_label_service import gemini_picture_labels_enabled, picture_match_label
from app.services.vlm_service import (
    heuristic_short_label_from_description,
    is_junk_label,
    is_placeholder_description,
    short_label_for_image,
    short_label_for_image_lowmem,
    vision_quota_tripped,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

META_TERMS = ("retrieved", "vector database", "embedding", "chunk", "selected subject")

PDF_ONLY_RULES = (
    "Create questions strictly from the textbook excerpt. "
    "Each question must reference concepts, terms, or facts present in the excerpt. "
    "Do NOT use general knowledge outside the excerpt."
)

HINDI_RULES = (
    "Write question text, options, and answers in Hindi (Devanagari). "
    "Keep names as they appear in the lesson."
)

CHAPTER_BALANCE_RULES = (
    "Cover ALL selected chapters roughly equally. "
    "Do NOT focus most questions on a single chapter or story. "
    "Spread facts, characters, and vocabulary across every chapter listed in CHAPTER SCOPE."
)

CROSS_FORMAT_RULES = (
    "This item is ONE section of a multi-section exam. "
    "Do NOT repeat the same fact or sentence wording used in other sections "
    "(MCQ vs fill-in-blank vs word-match vs short answer must cover different points or phrasing)."
)

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def _is_hindi_subject(subject_name: str) -> bool:
    name = subject_name or ""
    return "hindi" in name.lower() or bool(_DEVANAGARI_RE.search(name))


def _label_needs_hindi(label: str) -> bool:
    """True when a picture-match label is English-only and should be replaced."""
    s = (label or "").strip()
    if not s:
        return True
    if _DEVANAGARI_RE.search(s):
        return False
    return bool(re.search(r"[A-Za-z]{3,}", s))


def _lang_rules(subject_name: str) -> str:
    if _is_hindi_subject(subject_name):
        return HINDI_RULES
    return ""

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


def _allocate_picture_pool_balanced(
    images: list[dict],
    chapter_ranges: list[tuple[int, int]] | None,
) -> list[dict]:
    """Round-robin across selected chapter page ranges so one lesson cannot dominate."""
    if not chapter_ranges or len(chapter_ranges) < 2:
        return _allocate_picture_pool(images)

    buckets: list[list[dict]] = [[] for _ in chapter_ranges]
    unassigned: list[dict] = []
    for img in images:
        page = img.get("page_number")
        placed = False
        if page:
            for i, (start, end) in enumerate(chapter_ranges):
                if start <= page <= end:
                    buckets[i].append(img)
                    placed = True
                    break
        if not placed:
            unassigned.append(img)

    for bucket in buckets:
        random.shuffle(bucket)
    random.shuffle(unassigned)

    pool: list[dict] = []
    cursors = [0] * len(buckets)
    while True:
        added = False
        for i, bucket in enumerate(buckets):
            if cursors[i] < len(bucket):
                pool.append(bucket[cursors[i]])
                cursors[i] += 1
                added = True
        if not added:
            break
    pool.extend(unassigned)
    return pool


def _context_for_quality_scoring(source_context: str) -> str:
    """Strip cross-section hints we append for the LLM — not part of the textbook."""
    marker = "---\nQuestions already used in OTHER sections"
    if marker in source_context:
        return source_context.split(marker, 1)[0]
    return source_context


def question_contains_meta_terms(question_data: dict, source_context: str) -> bool:
    """Reject infrastructure/meta questions unless those terms appear in the source PDF text."""
    source_lower = _context_for_quality_scoring(source_context).lower()
    skip_keys = frozenset(
        {
            "grading_rubric",
            "ideal_answer",
            "correct_answer",
            "correct_word",
            "correct_mapping",
            "correct_label_by_figure",
            "correct_mapping_keys",
            "correct_option_code",
            "is_true",
        }
    )
    check_payload = {k: v for k, v in question_data.items() if k not in skip_keys}
    text_blob = json.dumps(check_payload, ensure_ascii=False).lower()
    for term in META_TERMS:
        if term in text_blob and term not in source_lower:
            return True
    return False


def sample_chunk_context(
    chunks: list,
    batch_index: int,
    batch_size: int | None = None,
    chapter_ranges: list[tuple[int, int]] | None = None,
) -> str:
    """Disjoint slices per format; when chapters are selected, sample each chapter equally."""
    if not chunks:
        return ""
    batch_size = batch_size or settings.CHUNKS_PER_GENERATION_BATCH

    if chapter_ranges and len(chapter_ranges) > 1:
        per = max(1, batch_size // len(chapter_ranges))
        selected: list = []
        for start, end in chapter_ranges:
            ch_chunks = [
                c
                for c in chunks
                if c.page_number and start <= c.page_number <= end and c.content
            ]
            if not ch_chunks:
                continue
            offset = (batch_index * per) % len(ch_chunks)
            for i in range(min(per, len(ch_chunks))):
                selected.append(ch_chunks[(offset + i) % len(ch_chunks)])
        if selected:
            # Keep chapter order stable for the LLM, but rotate start by batch.
            return "\n\n".join(
                f"[PDF PAGE {c.page_number}]\n{c.content}" for c in selected
            )

    n = len(chunks)
    if n <= batch_size:
        return "\n\n".join(f"[PDF PAGE {c.page_number}]\n{c.content}" for c in chunks if c.content)
    window = max(1, n // max(8, batch_size))
    start = (batch_index * window) % n
    selected = [chunks[(start + i) % n] for i in range(min(batch_size, n))]
    return "\n\n".join(f"[PDF PAGE {c.page_number}]\n{c.content}" for c in selected if c.content)


def _append_avoid_block(context: str, avoid_stems: list[str]) -> str:
    if not avoid_stems:
        return context
    recent = avoid_stems[-35:]
    block = "\n".join(f"- {s}" for s in recent if s.strip())
    return (
        f"{context}\n\n---\n"
        "Questions already used in OTHER sections of this same test (do NOT duplicate):\n"
        f"{block}"
    )


def _stem_for_avoid(q: dict) -> str:
    data = q.get("data") or {}
    t = q.get("type")
    if t == "mcq":
        return (data.get("question_text") or "").strip()[:140]
    if t == "fill_blank":
        return (data.get("sentence_with_blank") or "").strip()[:140]
    if t == "word_match":
        col = data.get("column_a") or []
        return "; ".join(str(x) for x in col[:3])[:140]
    if t in ("short_answer", "answer_following", "oral"):
        return (data.get("question") or "").strip()[:140]
    if t == "true_false":
        return (data.get("statement") or "").strip()[:140]
    return ""


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


async def generate_mcqs(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} multiple choice questions for {subject_name}. "
        f"{PDF_ONLY_RULES} {CROSS_FORMAT_RULES} {_lang_rules(subject_name)} "
        "Ensure distractors are plausible."
    )
    data = await generate_structured_output(
        prompt, MCQListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "mcq", "data": q_data, "score": score, "marks": 1})
    elif data.get("error"):
        logger.error("MCQ generation failed: %s", data.get("error"))
    return questions


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
    """Gemini Vision for picture labels — independent of text LLM (Groq/OpenAI).

    Disabled on Render by default (512MB OOM risk). Override with
    SKIP_RUNTIME_VLM=0 / ALLOW_RUNTIME_VLM_ON_RENDER=1.
    """
    if vision_quota_tripped():
        return False
    if os.getenv("SKIP_RUNTIME_VLM") == "1":
        return False
    if os.getenv("SKIP_RUNTIME_VLM") == "0":
        return True
    if os.getenv("RENDER") and os.getenv("ALLOW_RUNTIME_VLM_ON_RENDER") != "1":
        return False
    return bool(settings.GEMINI_API_KEY)


async def _translate_label_to_hindi(english: str) -> str:
    """Cheap Groq text translation when Gemini Vision quota is exhausted."""
    text = (english or "").strip()
    if not text or not settings.GROQ_API_KEY:
        return ""
    if _DEVANAGARI_RE.search(text):
        return text
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        model = settings.LLM_MODEL if "qwen" in (settings.LLM_MODEL or "").lower() else "qwen/qwen3.8-27b"
        if (settings.LLM_PROVIDER or "").lower() != "groq":
            model = "qwen/qwen3.8-27b"
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the picture label into short Hindi Devanagari (2-5 words). "
                        "Reply with ONLY the Hindi label — no English, no quotes, no explanation."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=40,
        )
        out = (resp.choices[0].message.content or "").strip().strip('"').strip("'")
        out = out.split("\n")[0].strip()
        if out and _DEVANAGARI_RE.search(out) and not is_junk_label(out):
            return out[:60]
    except Exception as e:
        logger.warning("Hindi label translate failed for %r: %s", text[:40], e)
    return ""


async def _resolve_picture_label(img: dict, *, prefer_hindi: bool = False) -> str:
    """Student-facing label from OCR on the figure, not seeded OCR-failure placeholders."""
    desc = (img.get("description") or img.get("caption") or "").strip()
    label = ""
    path = img.get("image_path")
    english_seed = ""

    use_seeded = bool(desc) and not is_junk_label(desc) and not desc.startswith("[OCR:")
    use_seeded = use_seeded and "manual import" not in desc.lower()

    if use_seeded:
        if prefer_hindi and not _DEVANAGARI_RE.search(desc):
            english_seed = desc
            use_seeded = False
        else:
            label = heuristic_short_label_from_description(desc)
            if not label and len(desc.split()) <= 8:
                from app.services.vlm_service import normalize_short_label

                label = normalize_short_label(desc)
            if prefer_hindi and label and _label_needs_hindi(label):
                english_seed = label
                label = ""

    if (not label or is_junk_label(label)) and path and os.path.isfile(path):
        label = await picture_match_label(path)
        if prefer_hindi and label and _label_needs_hindi(label):
            if not english_seed:
                english_seed = label
            label = ""

    # Prefer Groq translate of known English caption over burning Gemini Vision quota.
    if prefer_hindi and (not label or is_junk_label(label)) and english_seed:
        translated = await _translate_label_to_hindi(english_seed)
        if translated:
            return translated

    if (not label or is_junk_label(label)) and path and os.path.isfile(path):
        if runtime_vision_enabled():
            if gemini_picture_labels_enabled():
                label = await short_label_for_image(path, hindi_only=prefer_hindi)
            elif settings.GEMINI_API_KEY:
                label = await short_label_for_image_lowmem(path, hindi_only=prefer_hindi)

    if not label or is_junk_label(label):
        # Last resort: use English seed translated, or skip
        if prefer_hindi and english_seed:
            translated = await _translate_label_to_hindi(english_seed)
            if translated:
                return translated
        return ""
    if prefer_hindi and _label_needs_hindi(label):
        translated = await _translate_label_to_hindi(label)
        return translated or ""
    return label


async def count_labeled_figures(
    images: list[dict],
    *,
    max_probe: int = 48,
    tier: str = "relaxed",
    prefer_hindi: bool = False,
) -> int:
    """How many chapter figures get a student-facing label (OCR or runtime vision)."""
    pool = filter_quality_images(images, tier=tier)
    labeled = 0
    for img in pool[:max_probe]:
        if await _resolve_picture_label(img, prefer_hindi=prefer_hindi):
            labeled += 1
    return labeled


async def _labels_for_images(selected: list[dict], *, prefer_hindi: bool = False) -> list[str]:
    labels: list[str] = []
    for img in selected:
        labels.append(await _resolve_picture_label(img, prefer_hindi=prefer_hindi))
    return _dedupe_labels([l for l in labels if l and not is_junk_label(l)])


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
    chapter_ranges: list[tuple[int, int]] | None = None,
) -> list[dict]:
    """Build picture-match questions — one exercise uses 5 unique images."""
    questions: list[dict] = []
    pairs = MATCH_PAIRS_PER_QUESTION
    prefer_hindi = _is_hindi_subject(subject_name)
    # Round-robin across chapters; do not re-sort by page (that re-clusters one lesson).
    pool = _allocate_picture_pool_balanced(images, chapter_ranges)
    cursor = 0

    if len(pool) < pairs:
        return questions

    for q_idx in range(count):
        selected: list[dict] = []
        labels: list[str] = []
        # When Vision quota is dead we rely on OCR/Groq translate — don't probe forever.
        max_probes = min(len(pool), 12 if vision_quota_tripped() else max(15, len(pool)))
        probes = 0
        while len(selected) < pairs and cursor < len(pool) and probes < max_probes:
            candidate = pool[cursor]
            cursor += 1
            probes += 1
            if any(candidate.get("id") == s.get("id") for s in selected):
                continue
            label = await _resolve_picture_label(candidate, prefer_hindi=prefer_hindi)
            if not label:
                continue
            selected.append(candidate)
            labels.append(label)

        if len(selected) < pairs:
            logger.warning(
                "Picture match: need %d labeled figures, only found %d at question %d/%d",
                pairs,
                len(selected),
                q_idx + 1,
                count,
            )
            break

        labels = _dedupe_labels(labels[:pairs])
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
        f"{PDF_ONLY_RULES} {CROSS_FORMAT_RULES} {_lang_rules(subject_name)}"
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
    chapter_ranges: list[tuple[int, int]] | None = None,
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
            chapter_ranges=chapter_ranges,
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

    # Caption-only inventions are not pictures from the selected textbook pages.
    if len(questions) < count:
        logger.warning(
            "Picture match: only %d/%d questions — need %d labeled textbook images "
            "in the selected chapter pages. Skipping remaining picture-match items.",
            len(questions),
            count,
            pairs,
        )
        return questions

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
        f"{PDF_ONLY_RULES} {CROSS_FORMAT_RULES} "
        "Use different sentences than MCQ stems; blank one key word per sentence."
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
        f"{PDF_ONLY_RULES} {CROSS_FORMAT_RULES} "
        "Provide an ideal detailed answer and a grading rubric."
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


async def generate_oral(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} मौखिक प्रश्न (oral questions) for {subject_name}. "
        f"{PDF_ONLY_RULES} {HINDI_RULES} "
        "These are asked aloud in class; answers should be short spoken replies from the lesson."
    )
    data = await generate_structured_output(
        prompt, OralListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "oral", "data": q_data, "score": score, "marks": 2})
    elif data.get("error"):
        logger.error("Oral generation failed: %s", data.get("error"))
    return questions


async def generate_who_said(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} 'किसने किससे कहा?' questions for {subject_name}. "
        f"{PDF_ONLY_RULES} {HINDI_RULES} "
        "Each item is a dialogue or line from the lesson with speaker and listener."
    )
    data = await generate_structured_output(
        prompt, WhoSaidListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "who_said", "data": q_data, "score": score, "marks": 2})
    elif data.get("error"):
        logger.error("Who-said generation failed: %s", data.get("error"))
    return questions


async def generate_answer_following(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} 'निम्नलिखित प्रश्नों के उत्तर दीजिए' questions for {subject_name}. "
        f"{PDF_ONLY_RULES} {CROSS_FORMAT_RULES} {HINDI_RULES} "
        "Short written answers from the lesson. Provide ideal_answer and a grading rubric."
    )
    data = await generate_structured_output(
        prompt, ShortAnswerListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "answer_following", "data": q_data, "score": score, "marks": 2})
    elif data.get("error"):
        logger.error("Answer-following generation failed: %s", data.get("error"))
    return questions


async def generate_creative(
    context: str, count: int, subject_name: str, chapter_scope: str | None = None
) -> list[dict]:
    prompt = (
        f"Generate EXACTLY {count} रचनात्मक कार्य (creative work) tasks for {subject_name}. "
        f"{PDF_ONLY_RULES} {HINDI_RULES} "
        "Drawing, few sentences, or a short poem tied to the lesson — not generic art prompts."
    )
    data = await generate_structured_output(
        prompt, CreativeWorkListSchema, context, subject_name, chapter_scope
    )
    questions = []
    if "questions" in data:
        for q_data in data["questions"]:
            score = heuristic_quality_score(q_data, context)
            questions.append({"type": "creative", "data": q_data, "score": score, "marks": 3})
    elif data.get("error"):
        logger.error("Creative generation failed: %s", data.get("error"))
    return questions


VALID_QUESTION_TYPES = frozenset({
    "mcq",
    "assertion_reason",
    "true_false",
    "fill_blank",
    "word_match",
    "picture_match",
    "short_answer",
    "oral",
    "who_said",
    "answer_following",
    "creative",
})

DEFAULT_TYPE_COUNTS: dict[str, int] = {
    "mcq": 15,
    "assertion_reason": 10,
    "word_match": 5,
    "picture_match": 5,
    "true_false": 10,
    "fill_blank": 10,
    "short_answer": 5,
    "oral": 10,
    "who_said": 10,
    "answer_following": 10,
    "creative": 5,
}


async def generate_all_types(
    chunks: list,
    image_metadata: list,
    subject_name: str,
    on_progress: ProgressCallback | None = None,
    include_types: list[str] | None = None,
    questions_per_type: int = 5,
    chapter_scope: str | None = None,
    chapter_ranges: list[tuple[int, int]] | None = None,
) -> list[dict]:
    """
    Generate exactly `questions_per_type` questions for each selected format.
    Each format uses a different textbook slice; selected chapters are sampled evenly.
    """
    all_generators: list[tuple] = [
        ("MCQs", generate_mcqs, "mcq", 0),
        ("Assertion-Reason", generate_assertion_reason, "assertion_reason", 1),
        ("Word Match", generate_word_match, "word_match", 2),
        ("Picture Match", generate_picture_match, "picture_match", 3),
        ("True/False", generate_true_false, "true_false", 4),
        ("Fill in the Blank", generate_fill_blank, "fill_blank", 5),
        ("Short Answer", generate_short_answer, "short_answer", 6),
        ("Oral", generate_oral, "oral", 7),
        ("Who Said", generate_who_said, "who_said", 8),
        ("Answer Following", generate_answer_following, "answer_following", 9),
        ("Creative", generate_creative, "creative", 10),
    ]

    if include_types:
        allowed = {t for t in include_types if t in VALID_QUESTION_TYPES}
        generators = [g for g in all_generators if g[2] in allowed]
    else:
        generators = all_generators

    if os.getenv("LOW_MEMORY") == "1" and any(g[2] == "picture_match" for g in generators):
        generators.sort(key=lambda g: (0 if g[2] == "picture_match" else 1, g[3]))

    if not generators:
        return []

    balance_extra = ""
    if chapter_ranges and len(chapter_ranges) > 1:
        balance_extra = f" {CHAPTER_BALANCE_RULES}"
        if chapter_scope:
            chapter_scope = f"{chapter_scope}\n{CHAPTER_BALANCE_RULES}"

    all_questions: list[dict] = []
    total = len(generators)
    used_image_ids: set[int] = set()
    avoid_stems: list[str] = []

    for i, entry in enumerate(generators):
        label, gen_fn, q_type, batch_idx = entry
        if on_progress:
            pct = 32 + int((i / total) * 46)
            await on_progress(pct, f"Generating {label} from textbook ({i + 1}/{total})")

        context = _append_avoid_block(
            sample_chunk_context(
                chunks, batch_idx, chapter_ranges=chapter_ranges
            ),
            avoid_stems,
        )
        keep = quota_for_type(q_type, questions_per_type)
        if gen_fn is generate_picture_match:
            result = await gen_fn(
                context,
                keep,
                subject_name,
                image_metadata,
                chapter_scope,
                used_image_ids,
                chapter_ranges=chapter_ranges,
            )
            picked = result[:keep]
        else:
            extra = 0
            result = await gen_fn(context, keep + extra, subject_name, chapter_scope)
            result.sort(key=lambda q: q.get("score", 0), reverse=True)
            picked = result[:keep]

        all_questions.extend(picked)
        for q in picked:
            stem = _stem_for_avoid(q)
            if stem:
                avoid_stems.append(stem)
        logger.info("%s: generated %d, kept %d%s", label, len(result), len(picked), balance_extra and " [balanced]")
        del result
        del picked
        del context
        gc.collect()

    return all_questions
