import re
from dataclasses import dataclass


@dataclass
class ChapterInfo:
    id: str
    number: int
    title: str
    start_page: int
    end_page: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
        }


TOC_ROW = re.compile(
    r"^\|\s*(\d+)\.\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|",
    re.MULTILINE,
)
# Class 1 OCR TOC: "1. Thing I Do\n2" (title line then page number line)
TOC_PLAIN_ROW = re.compile(
    r"^(\d+)\.\s*(.+?)\s*\n(\d+)\s*$",
    re.MULTILINE,
)
CHAPTER_SINGLE_LINE = re.compile(
    r"^#\s*(\d+)\s+(.+?)\s*$",
    re.MULTILINE,
)
CHAPTER_TWO_LINE = re.compile(
    r"^#\s*(\d+)\s*\n#\s*(.+?)\s*$",
    re.MULTILINE,
)
# OCR sometimes puts the chapter number alone: "4\n# If I Were an Apple"
CHAPTER_NUM_THEN_HASH_TITLE = re.compile(
    r"^(\d+)\s*\n#\s*(.+?)\s*$",
    re.MULTILINE,
)
# First chapter may omit the number: "# Thing I Do\n\n## Warm Up"
CHAPTER_TITLE_ONLY = re.compile(
    r"^#\s+([A-Za-z][^\n#]{3,80})\s*\n\n##\s+Warm Up",
    re.MULTILINE,
)
CHAPTER_HASH_TITLE = re.compile(
    r"^#\s+([A-Z][^\n#]{4,80})\s*\n\n##\s+Learning Objective",
    re.MULTILINE,
)
# Hindi Pathmala: "पाठ 1 शीर्षक" / "पाठ १ : शीर्षक"
HINDI_PATH_LINE = re.compile(
    r"पाठ\s*([0-9०-९]+)\s*[:.\-–]?\s*(.+)",
)
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

_HINDI_FOOTER = (
    "पाठमाला",
    "शिक्षण संकेत",
    "लेखन अभ्यास",
    "रे मिलकर",
    "हिन्दी पाठमाला",
)
# Hindi Pathmala-1 (Grafalco): 14 chapters — PDF page where chapter badge appears.
HINDI_1_CHAPTERS: list[tuple[int, str]] = [
    (1, "मेरा नाम और जन्मदिन"),
    (2, "प्यारा विद्यालय"),
    (3, "मेरा परिवार"),
    (4, "मेरा शरीर"),
    (6, "ऋतु और महीने"),
    (7, "हमारे राष्ट्रीय प्रतीक"),
    (13, "स्वर और उनकी मात्राएँ"),
    (53, "संयुक्त व्यंजन"),
    (57, "संयुक्ताक्षर एवं द्वित्व व्यंजन"),
    (61, "नुक्ता"),
    (62, "अन्य वर्ण"),
    (72, "चिड़िया के बच्चे"),
    (75, "दीपू बदल गया"),
    (79, "उँगलियों की लड़ाई"),
]

# Verified against the numbered lesson badges in Hindi Pathmala-1 Proof 2.
# Standalone reading/activity pages between lessons are not part of that lesson.
HINDI_1_END_PAGES = [1, 2, 3, 5, 6, 7, 52, 56, 60, 61, 64, 74, 77, 81]

# Hindi Pathmala-2 (Grafalco): 13 numbered lessons — PDF page of chapter badge.
# PDF has no text layer; pages are 1-based file pages (printed page = PDF + 7).
HINDI_2_CHAPTERS: list[tuple[int, str]] = [
    (1, "मेरी प्यारी माँ"),
    (7, "नीमा की दादी"),
    (14, "जंगल का डॉक्टर"),
    (20, "समय का महत्व"),
    (27, "सब्जी की टोकरी"),
    (34, "खरगोश और कछुआ"),
    (43, "आ गया वसंत"),
    (50, "बादल"),
    (57, "सच का इनाम"),
    (63, "कंप्यूटर"),
    (70, "सच्चे वीर"),
    (76, "भाग्य या मेहनत"),
    (83, "काली कोयल"),
]

# Page 42 ("स्वच्छता वीर", केवल पढ़ने के लिए) is excluded from lesson 6.
HINDI_2_END_PAGES = [6, 13, 19, 26, 33, 41, 49, 56, 62, 69, 75, 82, 89]

# Hindi Reader-3 (Grafalco): 14 numbered lessons — PDF page of chapter badge.
# Scanned book (no text layer). Page 49 ("चाँद पर छोटा-सा गाँव", केवल पढ़ने के लिए)
# sits between lessons 7 and 8 and is excluded from both.
HINDI_3_CHAPTERS: list[tuple[int, str]] = [
    (1, "जागो प्यारे"),
    (7, "मोहन बना हीरो"),
    (14, "छोटी चींटी, बड़ा काम"),
    (20, "पेड़ों का उपहार"),
    (25, "जादुई रंगों की दुनिया"),
    (33, "सब्जियों की सभा"),
    (42, "चमकीला आसमान"),
    (50, "बाँसुरीवाले का न्याय"),
    (58, "जंगल में इंटरनेट"),
    (65, "प्यारे बोल"),
    (71, "स्वच्छता ही सुंदरता है"),
    (78, "जल चक्र का रहस्य"),
    (85, "ज्ञान का खजाना"),
    (91, "खो-खो का मुकाबला"),
]

HINDI_3_END_PAGES = [6, 13, 19, 24, 32, 41, 48, 57, 64, 70, 77, 84, 90, 97]


def _int_loose(value: str) -> int:
    return int(str(value).translate(_DEV_DIGITS))

SKIP_TITLES = frozenset({
    "brain play",
    "science",
    "semester - 1",
    "let's sum it up!",
    "smart words",
    "teacher's treasure",
    "good values",
    "test paper",
    "answers",
})


def _clean_title(title: str) -> str:
    title = re.sub(r"^[#\*\.\-\s]+", "", title)
    title = re.sub(r"[#\*\.\-\s]+$", "", title)
    return re.sub(r"\s+", " ", title).strip()


def _append_chapter(
    chapters: list[ChapterInfo],
    seen_titles: set[str],
    num: int,
    title: str,
    page: int,
) -> None:
    title_clean = _clean_title(title)
    if title_clean.lower() in SKIP_TITLES or title_clean.lower() in seen_titles:
        return
    seen_titles.add(title_clean.lower())
    chapters.append(
        ChapterInfo(
            id=f"ch-{num}",
            number=num,
            title=title_clean,
            start_page=page,
        )
    )


def _parse_toc(full_text: str) -> list[ChapterInfo]:
    chapters: list[ChapterInfo] = []
    seen_titles: set[str] = set()
    for num, title, page in TOC_ROW.findall(full_text):
        _append_chapter(chapters, seen_titles, int(num), title, int(page))
    return chapters


def _toc_region(full_text: str) -> str:
    """Limit plain TOC parsing to the index block at the start of the book."""
    lower = full_text.lower()
    start = 0
    for marker in ("page no.", "topics", "sl. no."):
        idx = lower.find(marker)
        if idx != -1:
            start = idx
            break

    region = full_text[start:]
    for stop in ("good values", "test paper", "[figure:", "english-1", "maths-1"):
        idx = region.lower().find(stop)
        if idx != -1:
            region = region[:idx]
            break
    return region


def _parse_plain_toc(full_text: str) -> list[ChapterInfo]:
    """Parse Class 1-style plain TOC blocks: '1. Title\\n2'."""
    chapters: list[ChapterInfo] = []
    seen_titles: set[str] = set()
    seen_numbers: set[int] = set()
    last_page = 0

    for num, title, page in TOC_PLAIN_ROW.findall(_toc_region(full_text)):
        num_i, page_i = int(num), int(page)
        if num_i in seen_numbers or page_i <= last_page:
            continue
        seen_numbers.add(num_i)
        last_page = page_i
        _append_chapter(chapters, seen_titles, num_i, title, page_i)

    return chapters


def _parse_heading_chapters(chunks: list) -> list[ChapterInfo]:
    found: dict[int, ChapterInfo] = {}
    
    def add_if_unique(n: int, title_clean: str, page: int, pseudo: bool = False):
        if title_clean.lower() in SKIP_TITLES:
            return
        if any(c.title.lower() == title_clean.lower() for c in found.values()):
            return
        if not pseudo and n in found:
            return
        
        chap_id = f"ch-{title_clean.lower().replace(' ', '-')[:40]}" if pseudo else f"ch-{n}"
        found[n] = ChapterInfo(chap_id, n, title_clean, page)

    for chunk in chunks:
        content = chunk.content or ""
        page = chunk.page_number or 1

        for num, title in CHAPTER_SINGLE_LINE.findall(content):
            # "#2 पहचान..." is a lesson marker in Hindi books, not an English chapter heading.
            if re.search(r"[\u0900-\u097F]", title):
                continue
            add_if_unique(int(num), _clean_title(title), page)

        for num, title in CHAPTER_TWO_LINE.findall(content):
            add_if_unique(int(num), _clean_title(title), page)

        for num, title in CHAPTER_NUM_THEN_HASH_TITLE.findall(content):
            add_if_unique(int(num), _clean_title(title), page)

        for title in CHAPTER_TITLE_ONLY.findall(content):
            pseudo_num = 100 + len(found)
            add_if_unique(pseudo_num, _clean_title(title), page, pseudo=True)

        for title in CHAPTER_HASH_TITLE.findall(content):
            pseudo_num = 200 + len(found)
            add_if_unique(pseudo_num, _clean_title(title), page, pseudo=True)

        for line in content.splitlines():
            m = HINDI_PATH_LINE.search(line)
            if m:
                add_if_unique(_int_loose(m.group(1)), _clean_title(m.group(2)), page)

    return sorted(found.values(), key=lambda c: (c.start_page, c.number))


def _hindi1_page_chapters(chunks: list) -> list[ChapterInfo]:
    max_page = max((c.page_number or 1) for c in chunks)
    out: list[ChapterInfo] = []
    for i, (start, title) in enumerate(HINDI_1_CHAPTERS, start=1):
        if start > max_page:
            break
        out.append(
            ChapterInfo(
                id=f"ch-h1-{i}",
                number=i,
                title=title,
                start_page=start,
                end_page=min(HINDI_1_END_PAGES[i - 1], max_page),
            )
        )
    return out


def _hindi2_page_chapters(chunks: list) -> list[ChapterInfo]:
    max_page = max((c.page_number or 1) for c in chunks)
    out: list[ChapterInfo] = []
    for i, (start, title) in enumerate(HINDI_2_CHAPTERS, start=1):
        if start > max_page:
            break
        out.append(
            ChapterInfo(
                id=f"ch-h2-{i}",
                number=i,
                title=title,
                start_page=start,
                end_page=min(HINDI_2_END_PAGES[i - 1], max_page),
            )
        )
    return out


def _hindi3_page_chapters(chunks: list) -> list[ChapterInfo]:
    max_page = max((c.page_number or 1) for c in chunks)
    out: list[ChapterInfo] = []
    for i, (start, title) in enumerate(HINDI_3_CHAPTERS, start=1):
        if start > max_page:
            break
        out.append(
            ChapterInfo(
                id=f"ch-h3-{i}",
                number=i,
                title=title,
                start_page=start,
                end_page=min(HINDI_3_END_PAGES[i - 1], max_page),
            )
        )
    return out


def _parse_hindi_section_starts(chunks: list) -> list[ChapterInfo]:
    seen: set[str] = set()
    chapters: list[ChapterInfo] = []
    num = 0
    for chunk in chunks:
        page = chunk.page_number or 1
        for line in (chunk.content or "").splitlines()[:12]:
            raw = line.strip()
            if not raw or len(raw) > 42:
                continue
            if any(m in raw for m in _HINDI_FOOTER):
                continue
            dev = sum(1 for c in raw if "\u0900" <= c <= "\u097F")
            if dev < max(4, len(raw) // 3):
                continue
            title = _clean_title(re.sub(r"^[\W\d०-९#()\[\]«»]+", "", raw))
            if len(title) < 4 or title.lower() in SKIP_TITLES:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            num += 1
            chapters.append(
                ChapterInfo(
                    id=f"ch-h-{num}",
                    number=num,
                    title=title,
                    start_page=page,
                )
            )
    return chapters


def extract_chapters(chunks: list, *, subject_name: str | None = None) -> list[ChapterInfo]:
    if not chunks:
        return []

    sub = (subject_name or "").lower()
    if sub == "hindi-1":
        return _hindi1_page_chapters(chunks)
    if sub == "hindi-2":
        return _hindi2_page_chapters(chunks)
    if sub == "hindi-3":
        return _hindi3_page_chapters(chunks)

    full_text = "\n\n".join(c.content for c in chunks if c.content)
    toc_md = _parse_toc(full_text)
    toc_plain = _parse_plain_toc(full_text)
    toc_chapters = toc_plain if len(toc_plain) >= len(toc_md) else toc_md
    heading_chapters = _parse_heading_chapters(chunks)
    hindi_sections = _parse_hindi_section_starts(chunks)

    # Prefer TOC when it lists more chapters (Class 1 books use plain-text TOC)
    if len(toc_chapters) >= len(heading_chapters) and toc_chapters:
        chapters = toc_chapters
    elif heading_chapters:
        chapters = heading_chapters
    else:
        chapters = toc_chapters

    if sub == "hindi-1" and len(chapters) <= 2:
        chapters = _hindi1_page_chapters(chunks)
    elif sub == "hindi-2" and len(chapters) <= 2:
        chapters = _hindi2_page_chapters(chunks)
    elif sub == "hindi-3" and len(chapters) <= 2:
        chapters = _hindi3_page_chapters(chunks)
    elif sub.startswith("hindi") and len(chapters) <= 2 and len(hindi_sections) >= 3:
        chapters = hindi_sections

    if not chapters:
        return []

    if not all(ch.end_page is not None for ch in chapters):
        chapters.sort(key=lambda c: c.start_page)
        for i, ch in enumerate(chapters):
            if ch.end_page is not None:
                continue
            if i + 1 < len(chapters):
                ch.end_page = max(ch.start_page, chapters[i + 1].start_page - 1)
            else:
                ch.end_page = max(c.page_number or 1 for c in chunks)

    return chapters


def filter_chunks_by_chapters(
    chunks: list,
    chapter_ids: list[str] | None,
    *,
    subject_name: str | None = None,
) -> list:
    if not chapter_ids:
        return chunks

    chapters = extract_chapters(chunks, subject_name=subject_name)
    selected = [c for c in chapters if c.id in chapter_ids]
    unknown = set(chapter_ids) - {c.id for c in chapters}
    if unknown:
        raise ValueError("Unknown chapter selection: " + ", ".join(sorted(unknown)) + ". Refresh the chapter list.")

    filtered = []
    for chunk in chunks:
        page = chunk.page_number
        if page is None:
            continue
        if any(ch.start_page <= page <= (ch.end_page or ch.start_page) for ch in selected):
            filtered.append(chunk)

    return filtered
