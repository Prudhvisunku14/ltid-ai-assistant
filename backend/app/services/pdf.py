"""Minimal Markdown -> PDF renderer (headings, paragraphs, bullets, numbered lists, pipe tables, code blocks).

Uses ReportLab's built-in Helvetica (WinAnsi), so characters outside Windows-1252 are transliterated first."""
import io, re
from xml.sax.saxutils import escape

_MAP = {"→": "->", "←": "<-", "Σ": "sum", "≤": "<=", "≥": ">=", "−": "-", "✓": "ok", "✗": "x",
        "×": "x", "≈": "~", "≠": "!=", "•": "-", "‑": "-", " ": " ", "​": ""}

def _ascii(text: str) -> str:
    for k, v in _MAP.items(): text = text.replace(k, v)
    return text.encode("cp1252", "replace").decode("cp1252")

def _inline(text: str) -> str:
    text = escape(_ascii(text))
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" size="8.5">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])_([^_]+)_(?![\w*])", r"<i>\1</i>", text)
    return text

def markdown_to_pdf(md: str, title: str = "Report") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13)
    cell = ParagraphStyle("c", parent=body, fontSize=8, leading=10)
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=17, textColor=colors.HexColor("#172033"), spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, textColor=colors.HexColor("#2f4fd1"), spaceBefore=12, spaceAfter=4)
    h3 = ParagraphStyle("h3", parent=ss["Heading3"], fontSize=10, spaceBefore=8, spaceAfter=2)
    code = ParagraphStyle("code", fontName="Courier", fontSize=7.5, leading=9.5, backColor=colors.HexColor("#F1F5F9"), leftIndent=4, rightIndent=4, spaceAfter=6)

    story, lines, i = [], md.split("\n"), 0
    def flush_list(items, ordered):
        if items:
            story.append(ListFlowable([ListItem(Paragraph(_inline(t), body), leftIndent=12) for t in items],
                                      bulletType="1" if ordered else "bullet", start=1 if ordered else None, leftIndent=14, bulletFontSize=8))
            story.append(Spacer(1, 3))
    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            j = i + 1; buf = []
            while j < len(lines) and not lines[j].startswith("```"): buf.append(lines[j]); j += 1
            story.append(Preformatted(_ascii("\n".join(buf)), code)); i = j + 1; continue
        if l.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells): rows.append(cells)
                i += 1
            n = max(len(r) for r in rows)
            data = [[Paragraph(_inline(c), cell) for c in r + [""] * (n - len(r))] for r in rows]
            t = Table(data, repeatRows=1, colWidths=[(A4[0] - 36 * mm) / n] * n)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5EAF1")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
            story += [t, Spacer(1, 6)]; continue
        m_b, m_n = re.match(r"^\s*[-*] (.*)", l), re.match(r"^\s*\d+\. (.*)", l)
        if m_b or m_n:
            items, ordered = [], bool(m_n)
            while i < len(lines) and re.match(r"^\s*(?:[-*]|\d+\.) (.*)", lines[i]) and bool(re.match(r"^\s*\d+\. ", lines[i])) == ordered:
                items.append(re.match(r"^\s*(?:[-*]|\d+\.) (.*)", lines[i]).group(1)); i += 1
            flush_list(items, ordered); continue
        if l.startswith("### "): story.append(Paragraph(_inline(l[4:]), h3))
        elif l.startswith("## "): story.append(Paragraph(_inline(l[3:]), h2))
        elif l.startswith("# "): story.append(Paragraph(_inline(l[2:]), h1))
        elif l.strip(): story.append(Paragraph(_inline(l), body))
        i += 1
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                      title=_ascii(title), author="LTID Assistant").build(story)
    return buf.getvalue()
