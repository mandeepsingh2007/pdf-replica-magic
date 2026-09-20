"""Local picture-match labels — no Gemini VLM. EasyOCR on figure (Hindi + English)."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from functools import lru_cache

from PIL import Image

from app.services.vlm_service import is_junk_label, normalize_short_label

logger = logging.getLogger(__name__)

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_NOISE = re.compile(r"[^\w\s\u0900-\u097F\-',.]", re.UNICODE)


@lru_cache(maxsize=1)
def _easyocr_reader():
    try:
        import easyocr
    except ImportError:
        return None
    langs = os.getenv("EASYOCR_LANGS", "hi,en").replace(" ", "").split(",")
    use_gpu = os.getenv("EASYOCR_GPU", "0") == "1"
    logger.info("Loading EasyOCR reader langs=%s gpu=%s", langs, use_gpu)
    return easyocr.Reader(langs, gpu=use_gpu, verbose=False)


def _pick_label(lines: list[str]) -> str:
    cleaned: list[str] = []
    for raw in lines:
        s = _NOISE.sub(" ", raw).strip()
        s = re.sub(r"\s+", " ", s)
        if len(s) < 2:
            continue
        if s.lower() in ("figure", "fig", "chitra", "चित्र"):
            continue
        cleaned.append(s)
    if not cleaned:
        return ""

    def score(t: str) -> tuple[int, int]:
        has_dev = 1 if _DEVANAGARI.search(t) else 0
        words = len(t.split())
        ideal = 0 if 2 <= words <= 6 else -abs(words - 3)
        return (has_dev, ideal)

    cleaned.sort(key=score, reverse=True)
    return normalize_short_label(cleaned[0][:60])


def ocr_label_from_file(image_path: str) -> str:
    path = os.path.normpath(image_path)
    if not os.path.isfile(path):
        return ""
    reader = _easyocr_reader()
    if reader is None:
        return ""

    tmp: str | None = None
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            max_side = int(os.getenv("EASYOCR_MAX_SIDE", "960"))
            im.thumbnail((max_side, max_side))
            fd, tmp = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            im.save(tmp, "JPEG", quality=88)
        texts = reader.readtext(tmp, detail=0, paragraph=False)
    except Exception as e:
        logger.warning("EasyOCR failed %s: %s", path, e)
        return ""
    finally:
        if tmp and os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    if not texts:
        return ""
    label = _pick_label([str(t) for t in texts if t])
    if label and not is_junk_label(label):
        return label
    return ""


def ocr_page_text_easyocr(page, page_num: int, *, dpi: int = 120) -> str:
    """Full-page Devanagari/English OCR via EasyOCR (no Gemini quota)."""
    reader = _easyocr_reader()
    if reader is None:
        logger.warning("EasyOCR unavailable for page %s", page_num)
        return ""

    tmp: str | None = None
    try:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        max_side = int(os.getenv("EASYOCR_PAGE_MAX_SIDE", "1200"))
        img.thumbnail((max_side, max_side))
        fd, tmp = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        img.save(tmp, "JPEG", quality=85)
        texts = reader.readtext(
            tmp,
            detail=0,
            paragraph=True,
            decoder="greedy",
            beamWidth=1,
            batch_size=4,
        )
    except Exception as e:
        logger.warning("EasyOCR page %s failed: %s", page_num, e)
        return ""
    finally:
        if tmp and os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    if not texts:
        return ""
    lines = [str(t).strip() for t in texts if t and str(t).strip()]
    return "\n".join(lines).strip()


async def picture_match_label(image_path: str) -> str:
    return await asyncio.to_thread(ocr_label_from_file, image_path)


def gemini_picture_labels_enabled() -> bool:
    return os.getenv("USE_GEMINI_PICTURE_LABELS", "0").strip() in ("1", "true", "yes")
