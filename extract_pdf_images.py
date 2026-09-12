"""
Extract textbook illustrations from a PDF — one clear picture per file.

Usage:
    python extract_pdf_images.py "C:\\path\\book.pdf"
    python extract_pdf_images.py book.pdf -o out_images --dpi 220
    python extract_pdf_images.py book.pdf --pages 3-12

Always renders the placed figure from the page (not raw XObject bytes),
tight-crops whitespace, splits stacked / side-by-side scenes, and drops
banners, worksheets, and near-blank clips.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

MIN_RECT_PT = 32
MIN_SAVE_PX = 72
MAX_PAGE_AREA = 0.55
PAD_PT = 3
BG_DELTA = 24
MAX_PER_PAGE = 24


def _parse_pages(spec: str | None, n_pages: int) -> list[int]:
    if not spec:
        return list(range(n_pages))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a), int(b)
            out.update(range(max(1, lo), min(n_pages, hi) + 1))
        else:
            i = int(part)
            if 1 <= i <= n_pages:
                out.add(i)
    return sorted(p - 1 for p in out)


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
                exp = fitz.Rect(cur.x0 - gap, cur.y0 - gap, cur.x1 + gap, cur.y1 + gap)
                if exp.intersects(merged[j]):
                    cur |= merged[j]
                    used[j] = True
                    changed = True
            out.append(cur)
        merged = out
    return merged


def _bg_mask(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape[:2]
    cs = max(4, min(14, h // 16, w // 16))
    corners = np.concatenate(
        [
            arr[:cs, :cs].reshape(-1, 3),
            arr[:cs, -cs:].reshape(-1, 3),
            arr[-cs:, :cs].reshape(-1, 3),
            arr[-cs:, -cs:].reshape(-1, 3),
        ]
    )
    bg = np.median(corners, axis=0)
    dist = np.abs(arr.astype(np.int16) - bg).mean(axis=2)
    return dist <= BG_DELTA


def _content_bbox(arr: np.ndarray, pad: int = 8) -> tuple[int, int, int, int] | None:
    content = ~_bg_mask(arr)
    if content.mean() < 0.012:
        return None
    ys, xs = np.where(content)
    if len(ys) == 0:
        return None
    h, w = arr.shape[:2]
    x0 = max(int(xs.min()) - pad, 0)
    y0 = max(int(ys.min()) - pad, 0)
    x1 = min(int(xs.max()) + pad + 1, w)
    y1 = min(int(ys.max()) + pad + 1, h)
    if (x1 - x0) < 20 or (y1 - y0) < 20:
        return None
    return x0, y0, x1, y1


def _pixel_stats(arr: np.ndarray) -> dict:
    rgb = arr[:, :, :3]
    white = float(np.all(rgb >= 235, axis=2).mean())
    gray = rgb.mean(axis=2)
    dark = float((gray < 80).mean())
    mx = rgb.max(axis=2).astype(np.float32)
    mn = rgb.min(axis=2).astype(np.float32)
    color = float(((mx - mn) / (mx + 1e-6) > 0.15).mean())
    h, w = rgb.shape[:2]
    return {
        "white": white,
        "dark": dark,
        "color": color,
        "aspect": w / max(h, 1),
        "w": w,
        "h": h,
    }


def _is_illustration(st: dict, area_frac: float) -> bool:
    if st["w"] < MIN_SAVE_PX or st["h"] < MIN_SAVE_PX:
        return False
    if min(st["w"], st["h"]) < 56:
        return False
    asp = max(st["aspect"], 1 / max(st["aspect"], 1e-6))
    if asp >= 5.8:
        return False
    if st["white"] > 0.93 and st["color"] < 0.06:
        return False
    if st["white"] > 0.82 and st["dark"] < 0.08 and st["color"] < 0.12:
        return False
    if st["aspect"] > 2.4 and st["white"] > 0.55 and st["color"] < 0.18 and st["h"] < 140:
        return False
    if 0.7 <= st["aspect"] <= 1.4 and st["color"] < 0.05 and st["dark"] > 0.14:
        return False
    if area_frac > 0.38 and st["white"] > 0.70 and st["color"] < 0.20:
        return False
    return True


def _gutter_cuts(is_gutter: np.ndarray, size: int, min_gutter: int) -> list[int]:
    runs: list[tuple[int, int]] = []
    start = None
    for i, g in enumerate(is_gutter):
        if g and start is None:
            start = i
        elif not g and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, size))

    cuts = [0]
    for a, b in runs:
        if b - a < min_gutter:
            continue
        mid = (a + b) // 2
        if 0.07 * size < mid < 0.93 * size:
            cuts.append(mid)
    cuts.append(size)
    return sorted(set(cuts))


def _boxes_from_cuts(
    arr: np.ndarray, cuts: list[int], axis: str
) -> list[tuple[int, int, int, int]]:
    h, w = arr.shape[:2]
    boxes: list[tuple[int, int, int, int]] = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 40:
            continue
        if axis == "v":
            band = arr[a:b]
        else:
            band = arr[:, a:b]
        box = _content_bbox(band, pad=4)
        if not box:
            continue
        x0, y0, x1, y1 = box
        if axis == "v":
            boxes.append((x0, y0 + a, x1, y1 + a))
        else:
            boxes.append((x0 + a, y0, x1 + a, y1))
    if axis == "v":
        boxes = [b for b in boxes if (b[3] - b[1]) >= max(50, int(h * 0.08))]
    else:
        boxes = [b for b in boxes if (b[2] - b[0]) >= max(50, int(w * 0.08))]
    return boxes if len(boxes) >= 2 else []


def _split_panels(arr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Split a crop on background gutters (stacked first, then side-by-side)."""
    h, w = arr.shape[:2]
    if h < 80 or w < 80:
        return []
    bg = _bg_mask(arr)
    v_cuts = _gutter_cuts(bg.mean(axis=1) >= 0.86, h, max(8, int(h * 0.018)))
    if len(v_cuts) >= 3:
        boxes = _boxes_from_cuts(arr, v_cuts, "v")
        if len(boxes) >= 2:
            return boxes[:8]
    h_cuts = _gutter_cuts(bg.mean(axis=0) >= 0.86, w, max(8, int(w * 0.018)))
    if len(h_cuts) >= 3:
        boxes = _boxes_from_cuts(arr, h_cuts, "h")
        if len(boxes) >= 2:
            return boxes[:8]
    return []


def _render_clip(page, clip: fitz.Rect, dpi: float) -> np.ndarray | None:
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    if pix.width < 8 or pix.height < 8:
        return None
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 1:
        arr = np.repeat(arr, 3, axis=2)
    elif pix.n >= 3:
        arr = arr[:, :, :3]
    return arr


def _candidate_rects(page) -> list[fitz.Rect]:
    page_rect = page.rect
    seen: list[fitz.Rect] = []

    for img in page.get_images(full=True):
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []
        for rect in rects or []:
            r = fitz.Rect(rect) & page_rect
            if r.is_empty:
                continue
            seen.append(r)

    drawings = page.get_drawings()
    if len(page.get_images(full=True)) < 2 and len(drawings) >= 8:
        raw: list[fitz.Rect] = []
        for d in drawings:
            r = d.get("rect")
            if not r:
                continue
            rect = fitz.Rect(r) & page_rect
            if rect.is_empty or rect.width < 8 or rect.height < 8:
                continue
            if rect.height < 6 and rect.width > page_rect.width * 0.5:
                continue
            raw.append(rect)
        for cluster in _merge_rects(raw, 16):
            if cluster.get_area() < 3500:
                continue
            seen.append(cluster)

    padded: list[fitz.Rect] = []
    for r in seen:
        p = fitz.Rect(r.x0 - PAD_PT, r.y0 - PAD_PT, r.x1 + PAD_PT, r.y1 + PAD_PT) & page_rect
        if p.width < MIN_RECT_PT or p.height < MIN_RECT_PT:
            continue
        if p.get_area() > MAX_PAGE_AREA * page_rect.get_area():
            continue
        aspect = p.width / max(p.height, 1.0)
        if aspect > 6.5 or aspect < 0.16:
            continue
        padded.append(p)
    return padded


def _dedupe(rects: list[fitz.Rect], iou: float = 0.58) -> list[fitz.Rect]:
    ranked = sorted(rects, key=lambda r: r.get_area(), reverse=True)
    kept: list[fitz.Rect] = []
    for r in ranked:
        if any((r & k).get_area() / max((r | k).get_area(), 1.0) >= iou for k in kept):
            continue
        kept.append(r)
    return kept


def extract_pdf_images(pdf_path: str, out_dir: str, dpi: float = 220, pages: str | None = None) -> int:
    pdf_path = os.path.abspath(pdf_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    page_indexes = _parse_pages(pages, len(doc))
    saved = 0

    for page_i in page_indexes:
        page = doc.load_page(page_i)
        page_no = page_i + 1
        page_rect = page.rect
        rects = _dedupe(_candidate_rects(page))
        fig = 0
        page_saved = 0

        for rect in rects:
            if page_saved >= MAX_PER_PAGE:
                break
            arr = _render_clip(page, rect, dpi)
            if arr is None:
                continue
            tight = _content_bbox(arr)
            if tight:
                x0, y0, x1, y1 = tight
                arr = arr[y0:y1, x0:x1]
            area_frac = rect.get_area() / max(page_rect.get_area(), 1.0)
            pieces = _split_panels(arr) or [(0, 0, arr.shape[1], arr.shape[0])]

            for box in pieces:
                crop = arr[box[1] : box[3], box[0] : box[2]]
                st = _pixel_stats(crop)
                if not _is_illustration(st, area_frac if len(pieces) == 1 else area_frac / len(pieces)):
                    continue
                name = f"page{page_no}_fig{fig}.png"
                path = out / name
                Image.fromarray(crop).save(path, "PNG", optimize=True)
                fig += 1
                saved += 1
                page_saved += 1
                if page_saved >= MAX_PER_PAGE:
                    break

        print(f"  page {page_no:>3}/{len(doc)}  candidates={len(rects)}  saved={page_saved}")

    doc.close()
    print(f"\nDone. {saved} images -> {out}")
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract clear textbook images from a PDF.")
    parser.add_argument("pdf", help="Path to the PDF")
    parser.add_argument("-o", "--out", default="", help="Output folder (default: <pdf_stem>_images)")
    parser.add_argument("--dpi", type=float, default=220, help="Render DPI (default 220)")
    parser.add_argument("--pages", default=None, help="Pages to extract, e.g. 1-8 or 3,5,9-12")
    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    out = args.out or str(Path(args.pdf).with_name(Path(args.pdf).stem + "_images"))
    extract_pdf_images(args.pdf, out, dpi=args.dpi, pages=args.pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
