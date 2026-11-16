"""A4 report composition adapted from PolyInterview's section-based PDF pipeline."""
from html import escape
from io import BytesIO
import math
import re

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

from .indexed_doc_template import IndexedDocTemplate

TEAL = colors.HexColor("#2f6558")
INK = colors.HexColor("#34463f")
MUTED = colors.HexColor("#596b63")
LIGHT = colors.HexColor("#edf3ee")
WIDTH = A4[0] - 96


def score_label(value):
    return "Not assessed" if value is None else f"{value:g}/10"


def _paragraph(value, style):
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or ""))
    chosen = style
    if re.search(r"[\u3400-\u9fff]", value):
        chosen = ParagraphStyle(style.name + "CJK", parent=style, fontName="STSong-Light", wordWrap="CJK")
    return Paragraph(escape(value).replace("\n", "<br/>"), chosen)


def _radar(items):
    drawing = Drawing(WIDTH, 240)
    cx, cy, radius = WIDTH / 2, 125, 75
    angles = [-math.pi / 2 + i * 2 * math.pi / len(items) for i in range(len(items))]
    def point(index, fraction):
        return cx + radius * fraction * math.cos(angles[index]), cy - radius * fraction * math.sin(angles[index])
    for level in range(1, 6):
        points = [coordinate for i in range(len(items)) for coordinate in point(i, level / 5)]
        drawing.add(Polygon(points, fillColor=None, strokeColor=colors.HexColor("#d6e1d9"), strokeWidth=.6))
    for i in range(len(items)):
        x, y = point(i, 1)
        drawing.add(Line(cx, cy, x, y, strokeColor=colors.HexColor("#d6e1d9")))
    if all(item["score"] is not None for item in items):
        points = [coordinate for i, item in enumerate(items) for coordinate in point(i, item["score"] / 10)]
        drawing.add(Polygon(points, fillColor=colors.HexColor("#d9e9df"), strokeColor=TEAL, strokeWidth=1.8))
    labels = ["Coherence", "Vocabulary", "Grammar", "Task response"]
    for i, item in enumerate(items):
        if item["score"] is not None:
            x, y = point(i, item["score"] / 10)
            drawing.add(Circle(x, y, 3, fillColor=TEAL, strokeColor=colors.white))
        x, y = point(i, 1.37)
        drawing.add(String(x, y + 4, labels[i], fontName="Helvetica-Bold", fontSize=10, fillColor=INK, textAnchor="middle"))
        drawing.add(String(x, y - 10, score_label(item["score"]), fontName="Helvetica", fontSize=9, fillColor=MUTED, textAnchor="middle"))
    return drawing


def render_report(data):
    """Return PDF bytes using a saved report view; no filesystem or model access."""
    if "STSong-Light" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("BodyCopy", fontName="Helvetica", fontSize=10, leading=14, textColor=INK, spaceAfter=6))
    styles.add(ParagraphStyle("SmallCopy", parent=styles["BodyCopy"], fontSize=8.5, leading=12, textColor=MUTED))
    styles.add(ParagraphStyle("TOCHeading1", fontName="Helvetica-Bold", fontSize=19, leading=25, textColor=TEAL, spaceBefore=14, spaceAfter=13, keepWithNext=True))
    styles.add(ParagraphStyle("TOCHeading2", fontName="Helvetica-Bold", fontSize=13, leading=19, textColor=INK, spaceBefore=14, spaceAfter=9, keepWithNext=True))
    styles.add(ParagraphStyle("Brand", fontName="Helvetica-Bold", fontSize=34, leading=42, textColor=TEAL, spaceAfter=20))
    styles.add(ParagraphStyle("ReportTitle", fontName="Helvetica-Bold", fontSize=24, leading=31, textColor=INK, spaceAfter=20))
    body, small = styles["BodyCopy"], styles["SmallCopy"]
    buffer = BytesIO()
    doc = IndexedDocTemplate(buffer, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=58, bottomMargin=48,
                             title="ispeak Speaking Practice Report", author="ispeak")
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(48, 28, "ispeak | Speaking practice | Not an official exam score")
        base = document.first_content_page
        if base and document.page >= base:
            canvas.drawRightString(A4[0] - 48, 28, str(document.page - base + 1))
        canvas.restoreState()
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=footer)])
    story = []
    def paragraph(value, style=body):
        story.append(_paragraph(value, style))
    def heading(value, level=1):
        paragraph(value, styles[f"TOCHeading{level}"])
    def bullets(items):
        for item in items:
            paragraph("- " + item)
    def dimension_table(items):
        rows = [[_paragraph("Dimension", small), _paragraph("Practice score", small), _paragraph("Feedback", small)]]
        rows += [[_paragraph(item["label"], body), _paragraph(score_label(item["score"]), body),
                  _paragraph(item["comment"] or "No reliable evidence is available for this dimension.", body)] for item in items]
        table = Table(rows, colWidths=[155, 82, WIDTH - 237], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LINEBELOW", (0, 0), (-1, 0), .6, TEAL), ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#dce5de")),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                   ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.append(table)

    story.append(Spacer(1, 90))
    paragraph("ispeak", styles["Brand"])
    paragraph("Speaking Practice Report", styles["ReportTitle"])
    story.append(Spacer(1, 24))
    for label, value in [("Exam", data["exam"]), ("Practice set", data["title"]), ("Learner", data["candidate"] or "Not specified"),
                         ("Session date", data["created_at"]), ("Answers submitted", str(len(data["questions"]))), ("Mode", data["mode"])]:
        paragraph(f"{label}: {value}")
    story.append(Spacer(1, 24))
    paragraph(data["scope"], small)
    paragraph("This document reflects saved feedback. Downloading it does not run a new assessment or change your recording.", small)
    story.append(PageBreak())
    paragraph("Contents", styles["Title"])
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("Contents1", fontName="Helvetica", fontSize=11, leading=17, spaceBefore=9, textColor=INK),
                       ParagraphStyle("Contents2", fontName="Helvetica", fontSize=9, leading=14, leftIndent=14, textColor=MUTED)]
    story += [toc, PageBreak()]

    heading("Performance overview")
    paragraph(data["summary"] or "No overall summary is available.")
    coverage = data["coverage"]
    if coverage.get("early_finish"):
        paragraph("This session ended early. The report covers only submitted answers.", small)
    if data["source"] == "offline_demo":
        paragraph("Offline walkthrough: no AI scores were generated.", small)
    story.append(_radar(data["dimensions"]))
    paragraph("A filled radar is shown only when all four dimensions have scores. Unassessed dimensions are not plotted as zero.", small)
    dimension_table(data["dimensions"])
    if data["strengths"]:
        heading("What went well", 2)
        bullets(data["strengths"])
    if data["improvements"]:
        heading("What to improve", 2)
        bullets(data["improvements"])
    heading("Next practice steps", 2)
    bullets(data["next_steps"] or ["Review the answer evidence and choose one improvement for your next attempt."])

    story.append(PageBreak())
    heading("Answer review")
    if not data["questions"]:
        paragraph("No answers were submitted.")
    for question in data["questions"]:
        heading(f"Question {question['number']}", 2)
        paragraph(question["question"])
        paragraph("Stage: " + question["stage"].replace("_", " ") + " | Status: " + question["status"].replace("_", " "), small)
        paragraph("Your answer", styles["Heading4"])
        paragraph(question["answer"] or "No answer was captured.")
        if any(item["score"] is not None for item in question["dimensions"]):
            dimension_table(question["dimensions"])
        else:
            paragraph("No text-based dimension scores are available for this answer.", small)
        for group in question["groups"]:
            paragraph(group["label"], styles["Heading4"])
            for feature in group["items"]:
                paragraph(f"{feature['label']}: {score_label(feature['score'])}")
                if feature["quote"]:
                    paragraph('Evidence: "' + feature["quote"] + '"')
                if feature["comment"]:
                    paragraph(feature["comment"])
                if feature["suggestion"]:
                    paragraph("Suggestion: " + feature["suggestion"])
        if question["corrections"]:
            paragraph("Suggested revisions", styles["Heading4"])
            for correction in question["corrections"]:
                paragraph("Original: " + correction["original"])
                paragraph("Revised: " + correction["revised"])
                paragraph("Reason: " + correction["reason"], small)
        voice = question["voice"]
        if voice:
            paragraph("Recorded pace and pauses", styles["Heading4"])
            for label, key, unit in [("Estimated pace", "pace", "words/min"), ("Pauses of at least 0.6 s", "pauses", ""), ("Detected span", "span", "seconds")]:
                value = voice[key]
                paragraph(f"{label}: {value if value is not None else 'Not available'} {unit}")
            if voice["advice"]:
                paragraph("Fine-tuned model advice: " + voice["advice"])
            paragraph(voice["scope"], small)
    doc.multiBuild(story)
    return buffer.getvalue()
