"""Detect and split stacked textbook illustrations into single scenes."""
from __future__ import annotations

import os
import re

import numpy as np
from PIL import Image

_PANEL_SUFFIX = re.compile(r"_p\d+$", re.I)


def is_panel_path(path: str) -> bool:
    stem, _ = os.path.splitext(os.path.basename(path or ""))
    return bool(_PANEL_SUFFIX.search(stem))


def original_stem_from_panel(path: str) -> str:
    stem, ext = os.path.splitext(path)
    return _PANEL_SUFFIX.sub("", stem) + ext


def _bg_mask(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape[:2]
    cs = max(4, min(12, h // 20, w // 20))
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
    return dist <= 22


def _merge_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b[1])
    merged = [boxes[0]]
    for x0, y0, x1, y1 in boxes[1:]:
        px0, py0, px1, py1 = merged[-1]
        if y0 < py1 - 2:
            merged[-1] = (min(px0, x0), min(py0, y0), max(px1, x1), max(py1, y1))
        else:
            merged.append((x0, y0, x1, y1))
    return merged


def find_vertical_panel_boxes(arr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Return content boxes split on horizontal background gutters."""
    h, w = arr.shape[:2]
    if h < 90 or w < 40:
        return []

    bg = _bg_mask(arr)
    is_gutter = bg.mean(axis=1) >= 0.86

    gutters: list[tuple[int, int]] = []
    start = None
    for i, g in enumerate(is_gutter):
        if g and start is None:
            start = i
        elif not g and start is not None:
            gutters.append((start, i))
            start = None
    if start is not None:
        gutters.append((start, h))

    cuts = [0]
    min_gutter = max(8, int(h * 0.015))
    for a, b in gutters:
        if b - a < min_gutter:
            continue
        mid = (a + b) // 2
        if 0.06 * h < mid < 0.94 * h:
            cuts.append(mid)
    cuts.append(h)
    cuts = sorted(set(cuts))
    if len(cuts) < 3:
        return []

    min_band = max(40, int(h * 0.07))
    boxes: list[tuple[int, int, int, int]] = []
    for y0, y1 in zip(cuts, cuts[1:]):
        if y1 - y0 < min_band:
            continue
        band = arr[y0:y1]
        content = ~_bg_mask(band)
        if content.mean() < 0.04:
            continue
        ys, xs = np.where(content)
        if len(ys) == 0:
            continue
        pad = 4
        bx0 = max(int(xs.min()) - pad, 0)
        bx1 = min(int(xs.max()) + pad + 1, w)
        by0 = max(int(ys.min()) + y0 - pad, 0)
        by1 = min(int(ys.max()) + y0 + pad + 1, h)
        if by1 - by0 < 50 or bx1 - bx0 < 50:
            continue
        boxes.append((bx0, by0, bx1, by1))

    boxes = _merge_boxes(boxes)
    min_h = max(55, int(h * 0.08))
    boxes = [b for b in boxes if (b[3] - b[1]) >= min_h and (b[2] - b[0]) >= 60]
    if len(boxes) < 2:
        return []
    return boxes[:8]


def split_illustration_file(image_path: str) -> list[str]:
    """
    If the file is several scenes stacked with a background gap, write each
    panel next to it (`_p0`, `_p1`, …) and return those paths.
    Otherwise return an empty list (caller should keep the original).
    """
    if not image_path or not os.path.isfile(image_path):
        return []
    if is_panel_path(image_path):
        return []

    try:
        with Image.open(image_path) as im:
            rgb = im.convert("RGB")
        arr = np.array(rgb)
    except Exception:
        return []

    boxes = find_vertical_panel_boxes(arr)
    if len(boxes) < 2:
        return []

    stem, ext = os.path.splitext(image_path)
    written: list[str] = []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        panel_path = f"{stem}_p{i}{ext or '.png'}"
        try:
            rgb.crop((x0, y0, x1, y1)).save(panel_path)
            written.append(panel_path)
        except Exception:
            continue
    return written if len(written) >= 2 else []


def is_stacked_composite(image_path: str) -> bool:
    if not image_path or is_panel_path(image_path) or not os.path.isfile(image_path):
        return False
    try:
        with Image.open(image_path) as im:
            arr = np.array(im.convert("RGB"))
        return len(find_vertical_panel_boxes(arr)) >= 2
    except Exception:
        return False
