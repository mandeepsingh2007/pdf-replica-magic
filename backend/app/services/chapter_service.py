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

    return sorted(found.values(), key=lambda c: (c.start_page, c.number))


def extract_chapters(chunks: list) -> list[ChapterInfo]:
    if not chunks:
        return []

    full_text = "\n\n".join(c.content for c in chunks if c.content)
    toc_md = _parse_toc(full_text)
    toc_plain = _parse_plain_toc(full_text)
    toc_chapters = toc_plain if len(toc_plain) >= len(toc_md) else toc_md
    heading_chapters = _parse_heading_chapters(chunks)

    # Prefer TOC when it lists more chapters (Class 1 books use plain-text TOC)
    if len(toc_chapters) >= len(heading_chapters) and toc_chapters:
        chapters = toc_chapters
    elif heading_chapters:
        chapters = heading_chapters
    else:
        chapters = toc_chapters

    if not chapters:
        return []

    chapters.sort(key=lambda c: c.start_page)
    for i, ch in enumerate(chapters):
        if i + 1 < len(chapters):
            ch.end_page = max(ch.start_page, chapters[i + 1].start_page - 1)
        else:
            ch.end_page = max(c.page_number or 1 for c in chunks)

    return chapters


def filter_chunks_by_chapters(chunks: list, chapter_ids: list[str] | None) -> list:
    if not chapter_ids:
        return chunks

    chapters = extract_chapters(chunks)
    selected = [c for c in chapters if c.id in chapter_ids]
    if not selected:
        return chunks

    filtered = []
    for chunk in chunks:
        page = chunk.page_number or 1
        if any(ch.start_page <= page <= (ch.end_page or ch.start_page) for ch in selected):
            filtered.append(chunk)

    if not filtered:
        # Fallback to text content matching if page numbers are misaligned
        for chunk in chunks:
            content = (chunk.content or "").lower()
            if any(ch.title.lower() in content for ch in selected):
                filtered.append(chunk)

    return filtered
