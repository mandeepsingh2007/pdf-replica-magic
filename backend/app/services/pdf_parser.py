import fitz  # PyMuPDF
import io
import os
import time
import numpy as np
import google.generativeai as genai
from PIL import Image
from app.core.config import settings
from app.services.image_quality import split_illustration_file

# Class 1 textbooks have many small icons / counters — keep them usable
MIN_IMAGE_SIDE_PX = 48
MIN_RECT_SIDE = 28
IMAGE_RENDER_ZOOM = 2.5
MAX_IMAGES_PER_PAGE = 20
DRAWING_CLUSTER_MIN_AREA = 4000
DRAWING_MERGE_GAP = 18

OCR_PROMPT = """You are an expert OCR system. Extract ALL text content from this scanned textbook page image.

Rules:
1. Extract every word, sentence, paragraph, heading, subheading, and caption visible on the page.
2. Preserve the logical reading order (top to bottom, left to right).
3. Use markdown formatting for headings (# for chapter titles, ## for section headings, etc.).
4. If there are tables, reproduce them in a readable format.
5. If there are math equations, write them in plain text notation.
6. If there are diagrams/figures, write [FIGURE: brief description] as a placeholder.
7. Skip page numbers, watermarks, and publisher logos.
8. Output ONLY the extracted text. No commentary.
"""


def ocr_page_with_gemini(page, page_num: int, retries: int = 3) -> str:
    """Convert a PDF page to image and OCR it using Gemini Vision."""
    if not settings.GEMINI_API_KEY:
        return ""

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.LLM_MODEL)

    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")

    for attempt in range(retries):
        try:
            response = model.generate_content([
                OCR_PROMPT,
                {"mime_type": "image/png", "data": img_bytes},
            ])
            text = response.text.strip()
            if text:
                return text
        except Exception as e:
            print(f"    OCR attempt {attempt+1} failed for page {page_num}: {e}")
            if "429" in str(e) or "quota" in str(e).lower():
                time.sleep(15 * (attempt + 1))
            else:
                time.sleep(3)

    return ""


def _rects_overlap_or_near(a: fitz.Rect, b: fitz.Rect, gap: float) -> bool:
    expanded = fitz.Rect(a.x0 - gap, a.y0 - gap, a.x1 + gap, a.y1 + gap)
    return expanded.intersects(b)


def _merge_rects(rects: list[fitz.Rect], gap: float) -> list[fitz.Rect]:
    if not rects:
        return []
    merged = [fitz.Rect(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out: list[fitz.Rect] = []
        used = [False] * len(merged)
        for i, r in enumerate(merged):
            if used[i]:
                continue
            cur = fitz.Rect(r)
            used[i] = True
            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                if _rects_overlap_or_near(cur, merged[j], gap):
                    cur |= merged[j]
                    used[j] = True
                    changed = True
            out.append(cur)
        merged = out
    return merged


def _pixmap_content_stats(pix) -> dict:
    """Heuristic stats to distinguish illustrations from text/layout raster blocks."""
    samples = pix.samples
    if not samples:
        return {
            "white_ratio": 1.0,
            "dark_ratio": 0.0,
            "color_frac": 0.0,
            "aspect": 1.0,
        }

    arr = np.frombuffer(samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n >= 3:
        rgb = arr[:, :, :3]
    else:
        rgb = np.repeat(arr[:, :, :1], 3, axis=2)

    white_ratio = float(np.all(rgb >= 235, axis=2).mean())
    gray = rgb.mean(axis=2)
    dark_ratio = float((gray < 80).mean())
    mx = rgb.max(axis=2).astype(np.float32)
    mn = rgb.min(axis=2).astype(np.float32)
    color_frac = float(((mx - mn) / (mx + 1e-6) > 0.15).mean())
    aspect = float(pix.width / max(pix.height, 1))
    return {
        "white_ratio": white_ratio,
        "dark_ratio": dark_ratio,
        "color_frac": color_frac,
        "aspect": aspect,
    }


def _is_likely_illustration(stats: dict, clip: fitz.Rect, page_rect: fitz.Rect) -> bool:
    """Drop text blocks, headers, QR codes, and worksheet tables kept as raster images."""
    wr = stats["white_ratio"]
    dr = stats["dark_ratio"]
    cf = stats["color_frac"]
    asp = stats["aspect"]
    rel_h = clip.height / max(page_rect.height, 1.0)
    area_frac = clip.get_area() / max(page_rect.get_area(), 1.0)
    rel_y0 = clip.y0 / max(page_rect.height, 1.0)

    # Plain text on white (poem lines, MCQ blocks, captions)
    if wr > 0.82 and dr < 0.10 and cf < 0.15:
        return False

    # Wide text strip
    if asp > 2.2 and wr > 0.50 and cf < 0.20 and rel_h < 0.22:
        return False

    # QR / barcode-like square
    if 0.65 <= asp <= 1.45 and cf < 0.06 and dr > 0.12:
        return False

    # Large worksheet / exercise box
    if wr > 0.80 and cf < 0.10 and dr < 0.04 and area_frac > 0.35:
        return False

    # Thin UI banner (e.g. semester label)
    if asp > 2.5 and dr < 0.008 and rel_h < 0.12:
        return False

    # Checklist / table block
    if 0.48 <= wr <= 0.72 and dr < 0.04 and cf < 0.30 and asp < 1.5 and area_frac > 0.45:
        return False

    # Chapter header band at top of page
    if rel_y0 < 0.15 and rel_h < 0.15 and asp > 1.8 and wr > 0.45 and cf < 0.42:
        return False

    # Mostly blank clip
    if wr > 0.97 and dr < 0.005:
        return False

    # Mixed text + small figures (whole activity box, not one illustration)
    if area_frac > 0.26 and wr > 0.68 and cf < 0.22 and asp > 1.05:
        return False

    return True


def _is_good_match_crop(clip: fitz.Rect, page_rect: fitz.Rect) -> bool:
    """Reject strips, slivers, and near full-page composites for picture-match."""
    if clip.is_empty:
        return False
    aspect = clip.width / max(clip.height, 1.0)
    if aspect > 4.0 or aspect < 0.25:
        return False
    rel_h = clip.height / max(page_rect.height, 1.0)
    rel_w = clip.width / max(page_rect.width, 1.0)
    if rel_h < 0.08 and aspect > 1.8:
        return False
    if rel_w < 0.08 and aspect < 0.55:
        return False
    area_frac = clip.get_area() / max(page_rect.get_area(), 1.0)
    if area_frac > 0.48:
        return False
    return True


def _dedupe_by_overlap(candidates: list[dict], iou_thresh: float = 0.55) -> list[dict]:
    """Keep largest regions when boxes heavily overlap."""
    ranked = sorted(
        candidates,
        key=lambda c: c["bbox_width"] * c["bbox_height"],
        reverse=True,
    )
    kept: list[dict] = []
    for cand in ranked:
        a = fitz.Rect(
            cand["bbox_x"],
            cand["bbox_y"],
            cand["bbox_x"] + cand["bbox_width"],
            cand["bbox_y"] + cand["bbox_height"],
        )
        too_similar = False
        for prev in kept:
            b = fitz.Rect(
                prev["bbox_x"],
                prev["bbox_y"],
                prev["bbox_x"] + prev["bbox_width"],
                prev["bbox_y"] + prev["bbox_height"],
            )
            inter = a & b
            if inter.is_empty:
                continue
            union = a | b
            iou = inter.get_area() / max(union.get_area(), 1.0)
            if iou >= iou_thresh:
                too_similar = True
                break
        if not too_similar:
            kept.append(cand)
    return kept


def _save_clipped_region(
    page,
    rect: fitz.Rect,
    output_image_dir: str,
    page_num: int,
    fig_index: int,
    page_rect: fitz.Rect,
) -> list[dict]:
    clip = fitz.Rect(rect) & page_rect
    if clip.is_empty or clip.width < MIN_RECT_SIDE or clip.height < MIN_RECT_SIDE:
        return []
    # Skip near-full-page clips (usually backgrounds / borders)
    if clip.get_area() > 0.82 * page_rect.get_area():
        return []

    matrix = fitz.Matrix(IMAGE_RENDER_ZOOM, IMAGE_RENDER_ZOOM)
    pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
    if pix.width < MIN_IMAGE_SIDE_PX or pix.height < MIN_IMAGE_SIDE_PX:
        return []

    stats = _pixmap_content_stats(pix)
    if not _is_likely_illustration(stats, clip, page_rect):
        return []
    if not _is_good_match_crop(clip, page_rect):
        return []

    image_filename = f"page{page_num}_fig{fig_index}.png"
    image_path = os.path.join(output_image_dir, image_filename)
    pix.save(image_path)
    meta = {
        "page": page_num,
        "image_path": image_path,
        "bbox_x": float(clip.x0),
        "bbox_y": float(clip.y0),
        "bbox_width": float(clip.width),
        "bbox_height": float(clip.height),
        "width": pix.width,
        "height": pix.height,
    }
    return _split_saved_image(meta)


def _split_saved_image(meta: dict) -> list[dict]:
    """Replace a stacked crop with one file per scene."""
    panels = split_illustration_file(meta["image_path"])
    if len(panels) < 2:
        return [meta]
    out: list[dict] = []
    for path in panels:
        try:
            with Image.open(path) as im:
                w, h = im.size
        except Exception:
            continue
        out.append({
            **meta,
            "image_path": path,
            "width": w,
            "height": h,
            "bbox_height": float(meta["bbox_height"]) / len(panels),
        })
    if len(out) < 2:
        return [meta]
    try:
        if os.path.isfile(meta["image_path"]):
            os.remove(meta["image_path"])
    except OSError:
        pass
    return out


def _extract_embedded_images(doc, page, page_num: int, output_image_dir: str) -> list[dict]:
    page_rect = page.rect
    image_list = page.get_images(full=True)
    seen_xrefs: set[int] = set()
    found: list[dict] = []
    fig_index = 0

    for img in image_list:
        xref = img[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        try:
            rects = page.get_image_rects(xref)
            if rects:
                used: list[fitz.Rect] = []
                for rect in sorted(rects, key=lambda r: r.width * r.height, reverse=True):
                    if any(
                        (rect & prev).get_area() / max(rect.get_area(), 1.0) > 0.75
                        for prev in used
                    ):
                        continue
                    saved = _save_clipped_region(
                        page, rect, output_image_dir, page_num, fig_index, page_rect
                    )
                    if saved:
                        found.extend(saved)
                        fig_index += len(saved)
                        used.append(rect)
                continue

            base_image = doc.extract_image(xref)
            w, h = base_image.get("width", 0), base_image.get("height", 0)
            if w < MIN_IMAGE_SIDE_PX or h < MIN_IMAGE_SIDE_PX:
                continue

            # Validate raw bytes too — some text blocks have no placement rect
            try:
                pil_img = Image.open(io.BytesIO(base_image["image"])).convert("RGB")
                arr = np.array(pil_img)
                white_ratio = float(np.all(arr >= 235, axis=2).mean())
                gray = arr.mean(axis=2)
                dark_ratio = float((gray < 80).mean())
                mx = arr.max(axis=2).astype(np.float32)
                mn = arr.min(axis=2).astype(np.float32)
                color_frac = float(((mx - mn) / (mx + 1e-6) > 0.15).mean())
                stats = {
                    "white_ratio": white_ratio,
                    "dark_ratio": dark_ratio,
                    "color_frac": color_frac,
                    "aspect": float(w / max(h, 1)),
                }
                pseudo_clip = fitz.Rect(0, 0, w, h)
                if not _is_likely_illustration(stats, pseudo_clip, page_rect):
                    continue
            except Exception:
                pass

            image_ext = base_image["ext"]
            image_filename = f"page{page_num}_fig{fig_index}.{image_ext}"
            image_path = os.path.join(output_image_dir, image_filename)
            with open(image_path, "wb") as f:
                f.write(base_image["image"])
            found.append({
                "page": page_num,
                "image_path": image_path,
                "bbox_x": 0.0,
                "bbox_y": 0.0,
                "bbox_width": float(w),
                "bbox_height": float(h),
                "width": w,
                "height": h,
            })
            split_raw = _split_saved_image(found[-1])
            found.pop()
            found.extend(split_raw)
            fig_index += len(split_raw)
        except Exception as e:
            print(f"    image xref {xref} failed on page {page_num}: {e}", flush=True)

    return found


def _extract_drawing_clusters(
    page,
    page_num: int,
    output_image_dir: str,
    start_index: int,
    embedded_count: int = 0,
) -> list[dict]:
    """Capture vector illustrations that are not embedded image XObjects."""
    drawings = page.get_drawings()
    if len(drawings) < 8:
        return []
    # Scanned/layout PDFs already expose text as embedded images — drawing clusters add noise
    if embedded_count >= 2:
        return []

    page_rect = page.rect
    raw_rects: list[fitz.Rect] = []
    for d in drawings:
        r = d.get("rect")
        if not r:
            continue
        rect = fitz.Rect(r)
        if rect.is_empty or rect.width < 8 or rect.height < 8:
            continue
        # Ignore thin lines / full-width rules
        if rect.height < 6 and rect.width > page_rect.width * 0.5:
            continue
        raw_rects.append(rect)

    clusters = _merge_rects(raw_rects, DRAWING_MERGE_GAP)
    found: list[dict] = []
    fig_index = start_index

    for cluster in clusters:
        if cluster.get_area() < DRAWING_CLUSTER_MIN_AREA:
            continue
        # Prefer compact figure-like regions over huge text underlines
        aspect = cluster.width / max(cluster.height, 1.0)
        if aspect > 8 or aspect < 0.12:
            continue
        saved = _save_clipped_region(
            page, cluster, output_image_dir, page_num, fig_index, page_rect
        )
        if saved:
            found.extend(saved)
            fig_index += len(saved)

    return found


def extract_pdf_data(file_path: str, output_image_dir: str):
    """
    Extracts text, structural elements, and images from a PDF using PyMuPDF.
    Falls back to Gemini OCR for scanned/image-based pages.
    Returns extracted structural text and a list of extracted image metadata.
    """
    if not os.path.exists(output_image_dir):
        os.makedirs(output_image_dir)

    doc = fitz.open(file_path)
    total_pages = len(doc)
    extracted_text_blocks = []
    extracted_images = []

    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        current = page_num + 1

        # 1. Try native text extraction first (scanned pages often have tiny junk text)
        native_text = page.get_text().strip()

        if native_text and len(native_text) > 50:
            print(f"  Page {current}/{total_pages}: native text ({len(native_text)} chars)", flush=True)
            extracted_text_blocks.append({
                "page": current,
                "text": native_text,
                "bbox": (0, 0, page.rect.width, page.rect.height),
            })
        else:
            # 2. Scanned page: use Gemini OCR
            print(f"  Page {current}/{total_pages}: OCR via Gemini...", end=" ", flush=True)
            ocr_text = ocr_page_with_gemini(page, current)
            if ocr_text:
                print(f"done ({len(ocr_text)} chars)", flush=True)
                extracted_text_blocks.append({
                    "page": current,
                    "text": ocr_text,
                    "bbox": (0, 0, page.rect.width, page.rect.height),
                })
                time.sleep(2)  # Rate limit
            else:
                print("no text", flush=True)

        # 3. Extract embedded images + vector drawing clusters
        original_xrefs = page.get_images(full=True)
        original_unique = len({img[0] for img in original_xrefs})
        original_drawings = len(page.get_drawings())

        embedded = _extract_embedded_images(doc, page, current, output_image_dir)
        drawings = _extract_drawing_clusters(
            page,
            current,
            output_image_dir,
            start_index=len(embedded) + 100,
            embedded_count=len(embedded),
        )
        before_dedupe = len(embedded) + len(drawings)
        page_images = _dedupe_by_overlap(embedded + drawings)
        after_dedupe = len(page_images)
        page_images = sorted(
            page_images,
            key=lambda c: c["bbox_width"] * c["bbox_height"],
            reverse=True,
        )[:MAX_IMAGES_PER_PAGE]
        final_kept = len(page_images)
        filtered_out = original_unique + (1 if original_drawings >= 8 else 0) - final_kept
        if filtered_out < 0:
            filtered_out = 0

        print(
            f"    IMAGES page {current}/{total_pages}: "
            f"in_pdf={original_unique} "
            f"extracted={final_kept} "
            f"| embedded={len(embedded)} "
            f"drawings_cluster={len(drawings)} "
            f"vector_primitives={original_drawings} "
            f"deduped={after_dedupe} "
            f"dropped={max(0, before_dedupe - final_kept)}",
            flush=True,
        )
        extracted_images.extend(page_images)

    print(
        f"  IMAGE TOTAL: pages={total_pages} images_extracted={len(extracted_images)}",
        flush=True,
    )
    doc.close()
    return extracted_text_blocks, extracted_images
