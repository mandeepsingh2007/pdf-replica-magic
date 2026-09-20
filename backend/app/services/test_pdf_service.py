"""Generate printable test paper and answer-key PDFs with correct Devanagari shaping."""
from __future__ import annotations

import os
from io import BytesIO
import fitz

from app.models.generated_test import GeneratedTest
from app.services.grading_service import (
    build_attempt_payload,
    format_paper_answer,
    parse_question_data,
    parse_test_data,
)

_ASSETS_FONT = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "assets",
        "fonts",
        "NotoSansDevanagari-Regular.ttf",
    )
)

# Prefer bundled Noto (portable + smaller than full Nirmala.ttc), then system fonts.
_FONT_CANDIDATES = (
    _ASSETS_FONT,
    r"C:\Windows\Fonts\Nirmala.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf",
)


def _resolve_hindi_font() -> str:
    for path in _FONT_CANDIDATES:
        if path and os.path.isfile(path):
            return path
    raise RuntimeError(
        "No Devanagari font found. Install Nirmala UI or place "
        "NotoSansDevanagari-Regular.ttf under app/assets/fonts/."
    )


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _marks_label(mks: int) -> str:
    return f"[{mks} mark{'s' if mks != 1 else ''}]"


def _q_header(num: int, mks: int, html_inner: str) -> str:
    return (
        '<table class="qhead"><tr>'
        f'<td class="qtext"><b>{num}.</b> {html_inner}</td>'
        f'<td class="qmarks">{_esc(_marks_label(mks))}</td>'
        "</tr></table>"
    )


def _with_serial_section_letters(
    raw: list[tuple[str, list[dict], str | None]],
) -> list[tuple[str, list[dict], str | None]]:
    out: list[tuple[str, list[dict], str | None]] = []
    for i, (name, questions, subtitle) in enumerate(raw):
        letter = chr(ord("A") + i)
        out.append((f"SECTION {letter}: {name}", questions, subtitle))
    return out


def _pdf_section_blocks(test_data: dict) -> list[tuple[str, list[dict], str | None]]:
    """Same section breakdown as the online Take Test page."""
    raw: list[tuple[str, list[dict], str | None]] = []

    if test_data.get("section_A_MCQs"):
        raw.append(("Multiple Choice Questions", test_data["section_A_MCQs"], None))
    if test_data.get("section_B_AssertionReason"):
        raw.append(
            ("Assertion and Reason", test_data["section_B_AssertionReason"], None)
        )

    objective = test_data.get("section_C_Objective") or []
    true_false = [q for q in objective if q.get("type") == "true_false"]
    fill_blank = [q for q in objective if q.get("type") == "fill_blank"]
    if true_false:
        raw.append(
            (
                "True / False",
                true_false,
                "State whether each statement is True or False.",
            )
        )
    if fill_blank:
        raw.append(("Fill in the Blanks", fill_blank, None))

    match = test_data.get("section_D_MatchFollowing") or []
    word_match = [q for q in match if q.get("type") == "word_match"][:1]
    picture_match = [q for q in match if q.get("type") == "picture_match"][:1]
    if word_match:
        raw.append(
            (
                "Match the Following (Words)",
                word_match,
                "Match each item in Column A with the correct option in Column B.",
            )
        )
    if picture_match:
        raw.append(
            (
                "Match the Picture with Text",
                picture_match,
                "Match each of the 5 pictures with the correct label. Column B is shuffled.",
            )
        )
    if test_data.get("section_D_Subjective"):
        raw.append(("Subjective Questions", test_data["section_D_Subjective"], None))
    if test_data.get("section_oral"):
        raw.append(("मौखिक प्रश्न / Oral Questions", test_data["section_oral"], None))
    if test_data.get("section_who_said"):
        raw.append(("किसने किससे कहा?", test_data["section_who_said"], None))
    if test_data.get("section_answer_following"):
        raw.append(
            ("निम्नलिखित प्रश्नों के उत्तर दीजिए", test_data["section_answer_following"], None)
        )
    if test_data.get("section_creative"):
        raw.append(("रचनात्मक कार्य", test_data["section_creative"], None))
    return _with_serial_section_letters(raw)


def _answer_key_stem(q_type: str, q_data: dict) -> str:
    if q_type == "mcq":
        return q_data.get("question_text") or ""
    if q_type == "assertion_reason":
        return f"A: {q_data.get('assertion', '')}"
    if q_type == "true_false":
        return q_data.get("statement") or ""
    if q_type == "fill_blank":
        return q_data.get("sentence_with_blank") or ""
    if q_type == "word_match":
        return "Match the following (words)"
    if q_type == "picture_match":
        return "Match the picture with text"
    if q_type in ("short_answer", "long_answer", "answer_following", "oral"):
        return q_data.get("question") or ""
    if q_type == "who_said":
        return q_data.get("quote") or ""
    if q_type == "creative":
        return q_data.get("prompt") or ""
    return ""


def _picture_match_html(
    q_num: int,
    marks: int,
    display: dict,
    image_alias: dict[int, str],
) -> str:
    pictures = list(display.get("pictures", [])[:5])
    labels = list(display.get("labels", [])[:5])
    while len(pictures) < 5:
        pictures.append({"key": str(len(pictures) + 1), "caption": "—", "image_id": None})
    while len(labels) < 5:
        labels.append({"key": chr(ord("a") + len(labels)), "text": "—"})

    pair_marks = max(1, marks // max(len(pictures), 1))
    parts = [
        _q_header(
            q_num,
            marks,
            "Match each picture (Column A) with the correct label (Column B). "
            f"Each pair carries {pair_marks} mark(s).",
        ),
        '<table class="match"><tr>'
        "<th>Column A — Pictures</th>"
        "<th>Column B — Labels (shuffled)</th>"
        "</tr>",
    ]
    for i in range(len(pictures)):
        pic = pictures[i]
        key = _esc(str(pic.get("key", "")))
        img_id = pic.get("image_id")
        alias = image_alias.get(int(img_id)) if img_id is not None else None
        if alias:
            left = f'<b>({key})</b><br/><img src="{alias}" width="120" />'
        else:
            left = f"<b>({key})</b> {_esc(pic.get('caption', 'Figure'))}"
        lab = labels[i]
        right = f"<b>({_esc(lab['key'])})</b> {_esc(lab['text'])}"
        parts.append(f"<tr><td>{left}</td><td>{right}</td></tr>")
    parts.append("</table>")
    return "\n".join(parts)


def _question_html(
    q_num: int,
    q: dict,
    image_alias: dict[int, str],
) -> str:
    marks = int(q.get("marks") or 1)
    display = q.get("display") or {}
    q_type = q.get("type") or ""

    if q_type == "mcq":
        text = _esc(display.get("question_text", ""))
        opts = display.get("options") or []
        opt_lines = "<br/>".join(
            f"{chr(65 + i)}. {_esc(o)}" for i, o in enumerate(opts)
        )
        return _q_header(q_num, marks, text) + f"<p class='opts'>{opt_lines}</p>"

    if q_type == "assertion_reason":
        text = (
            f"<b>Assertion (A):</b> {_esc(display.get('assertion', ''))}<br/>"
            f"<b>Reason (R):</b> {_esc(display.get('reason', ''))}"
        )
        opt_html = "".join(
            f"<p class='opts'>{_esc(opt.get('code', ''))}. {_esc(opt.get('label', ''))}</p>"
            for opt in display.get("options") or []
        )
        return _q_header(q_num, marks, text) + opt_html

    if q_type == "true_false":
        return (
            _q_header(q_num, marks, _esc(display.get("statement", "")))
            + "<p class='opts'>True / False: ____________</p>"
        )

    if q_type == "fill_blank":
        return (
            _q_header(q_num, marks, _esc(display.get("sentence_with_blank", "")))
            + "<p class='opts'>Answer: ________________________________</p>"
        )

    if q_type == "word_match":
        col_a = display.get("column_a") or []
        col_b = display.get("column_b") or []
        rows = [
            "<table class='match'><tr><th>Column A</th><th>Column B</th></tr>"
        ]
        for i in range(max(len(col_a), len(col_b))):
            a_cell = (
                f"({_esc(col_a[i]['key'])}) {_esc(col_a[i]['text'])}"
                if i < len(col_a)
                else ""
            )
            b_cell = (
                f"({_esc(col_b[i]['key'])}) {_esc(col_b[i]['text'])}"
                if i < len(col_b)
                else ""
            )
            rows.append(f"<tr><td>{a_cell}</td><td>{b_cell}</td></tr>")
        rows.append("</table>")
        return _q_header(q_num, marks, "Match the following:") + "\n".join(rows)

    if q_type == "picture_match":
        return _picture_match_html(q_num, marks, display, image_alias)

    if q_type in ("short_answer", "oral", "answer_following"):
        return _q_header(q_num, marks, _esc(display.get("question", ""))) + (
            '<div class="anspace"></div>'
        )

    if q_type == "who_said":
        return (
            _q_header(
                q_num,
                marks,
                f"किसने किससे कहा?<br/>“{_esc(display.get('quote', ''))}”",
            )
            + "<p class='opts'>वक्ता: ______________ &nbsp;&nbsp; श्रोता: ______________</p>"
        )

    if q_type == "creative":
        return _q_header(q_num, marks, _esc(display.get("prompt", ""))) + (
            '<div class="anspace tall"></div>'
        )

    return _q_header(q_num, marks, _esc(str(display)))


def _base_css(font_path: str) -> str:
    font_url = font_path.replace("\\", "/")
    return f"""
@font-face {{
  font-family: HindiFont;
  src: url("{font_url}");
}}
body {{
  font-family: HindiFont, sans-serif;
  font-size: 10.5pt;
  line-height: 1.4;
  color: #111;
}}
h1 {{
  font-size: 16pt;
  text-align: center;
  margin: 0 0 4pt 0;
  font-weight: bold;
}}
h2 {{
  font-size: 12pt;
  color: #1e3a5f;
  margin: 14pt 0 6pt 0;
  font-weight: bold;
}}
.sub {{
  text-align: center;
  margin: 0 0 8pt 0;
  font-size: 11pt;
}}
.meta-line {{
  font-size: 9.5pt;
  text-align: center;
  margin: 2pt 0;
}}
.meta-line .label {{
  color: #666;
}}
.instr {{
  margin: 6pt 0 10pt 0;
}}
.qhead {{
  width: 100%;
  border-collapse: collapse;
  margin: 8pt 0 2pt 0;
}}
.qhead .qtext {{
  width: 84%;
  vertical-align: top;
}}
.qhead .qmarks {{
  width: 16%;
  text-align: right;
  vertical-align: top;
  white-space: nowrap;
}}
.opts {{
  margin: 2pt 0 6pt 14pt;
}}
.match {{
  width: 100%;
  border-collapse: collapse;
  margin: 4pt 0 10pt 0;
}}
.match th, .match td {{
  width: 50%;
  vertical-align: top;
  padding: 6pt 8pt 6pt 0;
  text-align: left;
}}
.match th {{
  font-weight: bold;
}}
.anspace {{
  height: 56pt;
  margin-bottom: 6pt;
  border-bottom: 0.5pt solid #ccc;
}}
.anspace.tall {{
  height: 72pt;
}}
.answer {{
  color: #14532d;
  margin: 0 0 10pt 12pt;
}}
.stem {{
  margin: 8pt 0 2pt 0;
}}
.note {{
  margin: 4pt 0 10pt 0;
  font-size: 9.5pt;
}}
"""


def _story_to_pdf(html_body: str, archive: fitz.Archive | None = None) -> bytes:
    font_path = _resolve_hindi_font()
    css = _base_css(font_path)
    html = f"<html><body>{html_body}</body></html>"
    story = fitz.Story(html=html, user_css=css, archive=archive)

    mediabox = fitz.paper_rect("a4")
    where = mediabox + (50, 42, -50, -42)
    buffer = BytesIO()
    writer = fitz.DocumentWriter(buffer)
    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()


def _build_image_archive(
    image_paths: dict[int, str] | None,
) -> tuple[fitz.Archive | None, dict[int, str]]:
    """Register picture-match images under stable virtual names."""
    if not image_paths:
        return None, {}
    archive = fitz.Archive()
    alias: dict[int, str] = {}
    for img_id, path in image_paths.items():
        if not path or not os.path.isfile(path):
            continue
        ext = os.path.splitext(path)[1].lower() or ".png"
        name = f"img_{img_id}{ext}"
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            archive.add((data, name))
            alias[int(img_id)] = name
        except OSError:
            continue
    if not alias:
        return None, {}
    return archive, alias


def build_answer_key_pdf(test: GeneratedTest, subject_name: str) -> bytes:
    """Answer key for only the questions printed on this test paper."""
    test_data = parse_test_data(test)
    parts: list[str] = [
        f"<h1>{_esc(test.title or 'Generated Test')} — ANSWER KEY</h1>",
        (
            f"<p class='sub'>Subject: {_esc(subject_name)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Max Marks: {test.total_marks}</p>"
        ),
        (
            "<p class='note'>Answers match the printed test paper "
            "(including shuffled option letters).</p>"
        ),
    ]

    q_num = 0
    for section_title, questions, _subtitle in _pdf_section_blocks(test_data):
        if not questions:
            continue
        parts.append(f"<h2>{_esc(section_title)}</h2>")
        for q in questions:
            q_num += 1
            q_type = q.get("type") or ""
            q_data = parse_question_data(q.get("data"))
            stem = _answer_key_stem(q_type, q_data)
            if len(stem) > 160:
                stem = stem[:157] + "..."
            answer = format_paper_answer(q) or "—"
            answer_html = "<br/>".join(_esc(line) for line in str(answer).split("\n"))
            stem_bit = f" {_esc(stem)}" if stem else ""
            parts.append(f"<p class='stem'><b>{q_num}.</b>{stem_bit}</p>")
            parts.append(f"<p class='answer'><b>Answer:</b> {answer_html}</p>")

    return _story_to_pdf("\n".join(parts))


def build_test_pdf(
    test: GeneratedTest,
    subject_name: str,
    image_paths: dict[int, str] | None = None,
) -> bytes:
    """Render a printable student test paper PDF."""
    payload = build_attempt_payload(test, subject_name)
    test_data = payload["test_data"]
    archive, image_alias = _build_image_archive(image_paths)

    parts: list[str] = [
        f"<h1>{_esc(payload['title'])}</h1>",
        "<p class='sub'>FINAL EXAMINATION</p>",
        (
            f"<p class='meta-line'><span class='label'>Subject:</span> {_esc(subject_name)}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; <span class='label'>Max Marks:</span> "
            f"{payload['total_marks']}</p>"
            f"<p class='meta-line'><span class='label'>Time:</span> 2 Hours"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; <span class='label'>Questions:</span> "
            f"{payload['total_questions']}</p>"
        ),
        (
            "<p class='instr'><b>Instructions:</b> Answer all questions. "
            "Write your answers clearly.</p>"
        ),
    ]

    q_num = 0
    for section_title, questions, section_subtitle in _pdf_section_blocks(test_data):
        if not questions:
            continue
        sec_marks = sum(int(q.get("marks") or 0) for q in questions)
        parts.append(f"<h2>{_esc(section_title)} ({sec_marks} marks)</h2>")
        if section_subtitle:
            parts.append(f"<p>{_esc(section_subtitle)}</p>")
        for q in questions:
            q_num += 1
            parts.append(_question_html(q_num, q, image_alias))

    return _story_to_pdf("\n".join(parts), archive=archive)
