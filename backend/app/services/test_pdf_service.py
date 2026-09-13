import json
import os
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.grading_service import (
    build_attempt_payload,
    flatten_questions,
    format_paper_answer,
    parse_question_data,
    parse_test_data,
)
from app.models.generated_test import GeneratedTest


def _p(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _question_header(num: int, mks: int, txt: str) -> Table:
    styles = getSampleStyleSheet()
    q_style = ParagraphStyle(
        "QuestionHeader",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        spaceAfter=4,
    )
    right_style = ParagraphStyle(
        "QuestionMarks",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=2,
    )
    q_para = Paragraph(f"<b>{num}.</b> {txt}", q_style)
    m_para = Paragraph(f"[{mks} mark{'s' if mks != 1 else ''}]", right_style)
    t = Table([[q_para, m_para]], colWidths=[14.4 * cm, 3.0 * cm])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    return t


def _question_text(q_type: str, data: dict) -> str:
    if q_type == "mcq":
        return data.get("question_text", "")
    if q_type == "assertion_reason":
        return (
            f"Assertion (A): {data.get('assertion', '')}<br/>"
            f"Reason (R): {data.get('reason', '')}"
        )
    if q_type == "true_false":
        return data.get("statement", "")
    if q_type == "fill_blank":
        return data.get("sentence_with_blank", "")
    if q_type == "word_match":
        col_a = data.get("column_a", [])
        col_b = data.get("column_b", [])
        left = "<br/>".join(f"({i+1}) {_p(x)}" for i, x in enumerate(col_a))
        right = "<br/>".join(f"({chr(97+i)}) {_p(x)}" for i, x in enumerate(col_b))
        return f"<b>Column A</b><br/>{left}<br/><br/><b>Column B</b><br/>{right}"
    if q_type == "picture_match":
        labels = data.get("labels", [])
        label_lines = "<br/>".join(f"({chr(97+i)}) {_p(x)}" for i, x in enumerate(labels))
        return f"Match each picture with the correct label.<br/><br/><b>Labels</b><br/>{label_lines}"
    if q_type == "short_answer":
        return data.get("question", "")
    return ""


def _picture_cell(pic: dict, image_paths: dict[int, str] | None, body: ParagraphStyle) -> Any:
    """One numbered picture slot for match-the-following PDF layout."""
    key = pic.get("key", "")
    img_id = pic.get("image_id")
    img_path = image_paths.get(int(img_id)) if image_paths and img_id else None
    if img_path and os.path.isfile(img_path):
        try:
            img = Image(img_path, width=3.5 * cm, height=2.5 * cm, kind="proportional")
            inner = Table(
                [[Paragraph(f"<b>({key})</b>", body)], [img]],
                colWidths=[8.0 * cm],
            )
            inner.setStyle(
                TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            return inner
        except Exception:
            pass
    return Paragraph(f"<b>({key})</b> {_p(pic.get('caption', 'Figure'))}", body)


def _picture_match_pdf_block(
    q_num: int,
    marks: int,
    display: dict,
    image_paths: dict[int, str] | None,
    body: ParagraphStyle,
) -> list[Any]:
    """Standard match layout: Column A = pictures 1-5, Column B = shuffled labels a-e."""
    pictures = display.get("pictures", [])[:5]
    labels = display.get("labels", [])[:5]
    while len(pictures) < 5:
        pictures.append({"key": str(len(pictures) + 1), "caption": "—", "image_id": None})
    while len(labels) < 5:
        labels.append({"key": chr(ord("a") + len(labels)), "text": "—"})

    block: list[Any] = []
    block.append(
        _question_header(
            q_num,
            marks,
            "Match each picture (Column A) with the correct label (Column B). "
            f"Each pair carries {max(1, marks // max(len(pictures), 1))} mark(s)."
        )
    )

    n = len(pictures)
    label_style = ParagraphStyle(
        "MatchLabel",
        parent=body,
        fontSize=10,
        leading=14,
        wordWrap="CJK",
    )
    table_data: list[list[Any]] = [
        [
            Paragraph("<b>Column A — Pictures</b>", body),
            Paragraph("<b>Column B — Labels</b> (shuffled)", body),
        ]
    ]
    for i in range(n):
        table_data.append([
            _picture_cell(pictures[i], image_paths, body),
            Paragraph(
                f"<b>({labels[i]['key']})</b> {_p(labels[i]['text'])}",
                label_style,
            ),
        ])
    t = Table(table_data, colWidths=[8.7 * cm, 8.7 * cm])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    block.append(t)
    block.append(Spacer(1, 0.35 * cm))
    return block


def _with_serial_section_letters(
    raw: list[tuple[str, list[dict], str | None]],
) -> list[tuple[str, list[dict], str | None]]:
    """Assign A, B, C, … in order; no letter repeats."""
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
    if q_type in ("short_answer", "long_answer"):
        return q_data.get("question") or ""
    return ""


def build_answer_key_pdf(test: GeneratedTest, subject_name: str) -> bytes:
    """Answer key for only the questions printed on this test paper."""
    test_data = parse_test_data(test)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "KeyTitle",
        parent=styles["Heading1"],
        fontSize=16,
        alignment=1,
        spaceAfter=6,
    )
    section_style = ParagraphStyle(
        "KeySection",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#1e3a5f"),
    )
    body = ParagraphStyle("KeyBody", parent=styles["Normal"], fontSize=10, leading=14)
    answer_style = ParagraphStyle(
        "KeyAnswer",
        parent=body,
        textColor=colors.HexColor("#14532d"),
        leftIndent=12,
        spaceAfter=8,
    )

    story: list[Any] = []
    story.append(Paragraph(f"{_p(test.title or 'Generated Test')} — ANSWER KEY", title_style))
    story.append(
        Paragraph(
            f"Subject: {_p(subject_name)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Max Marks: {test.total_marks}",
            ParagraphStyle("KeyMeta", parent=body, alignment=1),
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            "Answers match the printed test paper (including shuffled option letters).",
            body,
        )
    )

    q_num = 0
    for section_title, questions, _subtitle in _pdf_section_blocks(test_data):
        if not questions:
            continue
        story.append(Paragraph(section_title, section_style))
        for q in questions:
            q_num += 1
            q_type = q.get("type") or ""
            q_data = parse_question_data(q.get("data"))
            stem = _answer_key_stem(q_type, q_data)
            if len(stem) > 160:
                stem = stem[:157] + "..."
            answer = format_paper_answer(q) or "—"
            answer_html = "<br/>".join(_p(line) for line in str(answer).split("\n"))
            story.append(
                Paragraph(f"<b>{q_num}.</b> {_p(stem)}" if stem else f"<b>{q_num}.</b>", body)
            )
            story.append(Paragraph(f"<b>Answer:</b> {answer_html}", answer_style))

    doc.build(story)
    return buffer.getvalue()


def build_test_pdf(
    test: GeneratedTest,
    subject_name: str,
    image_paths: dict[int, str] | None = None,
) -> bytes:
    """Render a printable student test paper PDF."""
    payload = build_attempt_payload(test, subject_name)
    test_data = payload["test_data"]
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
        alignment=1,
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#1e3a5f"),
    )
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)

    story: list[Any] = []
    story.append(Paragraph(_p(payload["title"]), title_style))
    story.append(Paragraph("FINAL EXAMINATION", ParagraphStyle("Sub", parent=body, alignment=1)))
    story.append(Spacer(1, 0.3 * cm))
    meta = Table(
        [
            ["Subject:", _p(subject_name), "Max Marks:", str(payload["total_marks"])],
            ["Time:", "2 Hours", "Questions:", str(payload["total_questions"])],
        ],
        colWidths=[2.2 * cm, 6.5 * cm, 2.5 * cm, 3 * cm],
    )
    meta.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "<b>Instructions:</b> Answer all questions. Write your answers clearly.",
        body,
    ))
    story.append(Spacer(1, 0.4 * cm))

    q_num = 0
    for section_title, questions, section_subtitle in _pdf_section_blocks(test_data):
        if not questions:
            continue

        sec_marks = sum(int(q.get("marks") or 0) for q in questions)
        story.append(
            Paragraph(f"{section_title} ({sec_marks} marks)", section_style)
        )
        if section_subtitle:
            story.append(Paragraph(_p(section_subtitle), body))
            story.append(Spacer(1, 0.15 * cm))

        for q in questions:
            q_num += 1
            marks = q.get("marks", 1)
            display = q.get("display", {})
            q_type = q.get("type", "")

            if q_type == "mcq":
                text = _p(display.get("question_text", ""))
                opts = display.get("options", [])
                opt_lines = "<br/>".join(
                    f"{chr(65+i)}. {_p(o)}" for i, o in enumerate(opts)
                )
                story.append(_question_header(q_num, marks, text))
                story.append(Paragraph(opt_lines, body))
            elif q_type == "assertion_reason":
                text = (
                    f"<b>Assertion (A):</b> {_p(display.get('assertion', ''))}<br/>"
                    f"<b>Reason (R):</b> {_p(display.get('reason', ''))}"
                )
                story.append(_question_header(q_num, marks, text))
                for opt in display.get("options", []):
                    story.append(Paragraph(
                        f"{opt.get('code', '')}. {_p(opt.get('label', ''))}",
                        body,
                    ))
            elif q_type == "true_false":
                story.append(_question_header(q_num, marks, _p(display.get('statement', ''))))
                story.append(Paragraph("True / False: ____________", body))
            elif q_type == "fill_blank":
                story.append(_question_header(q_num, marks, _p(display.get('sentence_with_blank', ''))))
                story.append(Paragraph("Answer: ________________________________", body))
            elif q_type == "word_match":
                story.append(_question_header(q_num, marks, "Match the following:"))
                col_a = display.get("column_a", [])
                col_b = display.get("column_b", [])
                table_data = [[Paragraph("<b>Column A</b>", body), Paragraph("<b>Column B</b>", body)]]
                for i in range(max(len(col_a), len(col_b))):
                    a_cell = Paragraph(f"({col_a[i]['key']}) {_p(col_a[i]['text'])}", body) if i < len(col_a) else ""
                    b_cell = Paragraph(f"({col_b[i]['key']}) {_p(col_b[i]['text'])}", body) if i < len(col_b) else ""
                    table_data.append([a_cell, b_cell])
                t = Table(table_data, colWidths=[8.7 * cm, 8.7 * cm])
                t.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(t)
            elif q_type == "picture_match":
                pm_block = _picture_match_pdf_block(q_num, marks, display, image_paths, body)
                story.extend(pm_block)
                continue
            elif q_type == "short_answer":
                story.append(_question_header(q_num, marks, _p(display.get('question', ''))))
                story.append(Spacer(1, 2.0 * cm))
            else:
                story.append(_question_header(q_num, marks, _question_text(q_type, display)))

            story.append(Spacer(1, 0.25 * cm))

    doc.build(story)
    return buffer.getvalue()
