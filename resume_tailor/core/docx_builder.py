import io
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

_FONT = "Calibri"
_NAVY = RGBColor(0x1B, 0x2A, 0x4A)
_ACCENT = RGBColor(0x2E, 0x6D, 0xA4)
_GRAY = RGBColor(0x55, 0x55, 0x55)
_BLACK = RGBColor(0x1A, 0x1A, 0x1A)

# Right tab stop at ~17cm (fits A4 with 2cm margins)
_RIGHT_TAB = Twips(9640)


def _set_para_spacing(p, before=0, after=4, line=None):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if line:
        pf.line_spacing = Pt(line)


def _add_bottom_border(paragraph, color="2E6DA4"):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _set_right_tab(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    tabs_el = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(int(_RIGHT_TAB)))
    tabs_el.append(tab)
    pPr.append(tabs_el)


def _run(paragraph, text, bold=False, italic=False, size=9.5, color=None):
    r = paragraph.add_run(text)
    r.font.name = _FONT
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color or _BLACK
    return r


def _section_header(doc, title):
    p = doc.add_paragraph()
    _run(p, title.upper(), bold=True, size=10.5, color=_ACCENT)
    _add_bottom_border(p)
    _set_para_spacing(p, before=10, after=3)


def _entry(doc, role, org, duration, location, bullets):
    # Role line with right-aligned duration
    p = doc.add_paragraph()
    _set_right_tab(p)
    _set_para_spacing(p, before=4, after=1)
    _run(p, role, bold=True, size=10, color=_BLACK)
    if duration:
        _run(p, "\t", size=10)
        _run(p, duration, size=9, color=_GRAY)

    # Org line with right-aligned location
    if org:
        p2 = doc.add_paragraph()
        _set_right_tab(p2)
        _set_para_spacing(p2, before=0, after=2)
        _run(p2, org, italic=True, size=9.5, color=_GRAY)
        if location:
            _run(p2, "\t", size=9.5)
            _run(p2, location, size=9, color=_GRAY)

    # Bullets
    for bullet in bullets:
        bp = doc.add_paragraph(style="List Bullet")
        _set_para_spacing(bp, before=0, after=2)
        _run(bp, bullet, size=9.5)


def build_resume_docx(structure: dict) -> bytes:
    doc = Document()

    # Page margins
    for sec in doc.sections:
        sec.top_margin = Cm(1.8)
        sec.bottom_margin = Cm(1.8)
        sec.left_margin = Cm(2.0)
        sec.right_margin = Cm(2.0)

    # Remove default paragraph spacing from Normal style
    doc.styles["Normal"].paragraph_format.space_before = Pt(0)
    doc.styles["Normal"].paragraph_format.space_after = Pt(0)

    # ── Name ──
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_para_spacing(name_p, before=0, after=4)
    _run(name_p, structure.get("name", "Your Name"), bold=True, size=22, color=_NAVY)

    # ── Contact line ──
    contacts = structure.get("contact", [])
    if contacts:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_para_spacing(cp, before=0, after=6)
        _run(cp, "  |  ".join(contacts), size=9, color=_GRAY)

    # ── Summary ──
    summary = structure.get("summary", "")
    if summary:
        _section_header(doc, "Summary")
        sp = doc.add_paragraph()
        _set_para_spacing(sp, before=2, after=6)
        _run(sp, summary, size=9.5)

    # ── Sections ──
    for section in structure.get("sections", []):
        _section_header(doc, section.get("title", ""))
        kind = section.get("type", "text")

        if kind == "entries":
            for e in section.get("entries", []):
                _entry(
                    doc,
                    role=e.get("role", ""),
                    org=e.get("org", ""),
                    duration=e.get("duration", ""),
                    location=e.get("location", ""),
                    bullets=e.get("bullets", []),
                )

        elif kind == "skills":
            for category in section.get("categories", []):
                kp = doc.add_paragraph()
                _set_para_spacing(kp, before=2, after=3)
                label = category.get("label", "")
                items = category.get("items", "")
                if label:
                    _run(kp, label + ": ", bold=True, size=9.5)
                _run(kp, items, size=9.5)

        else:  # plain text block
            tp = doc.add_paragraph()
            _set_para_spacing(tp, before=2, after=6)
            _run(tp, section.get("content", ""), size=9.5)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def text_to_docx_bytes(text: str, title: str = "") -> bytes:
    """Plain fallback used for cover letter."""
    doc = Document()
    for sec in doc.sections:
        sec.top_margin = Cm(2.0)
        sec.bottom_margin = Cm(2.0)
        sec.left_margin = Cm(2.5)
        sec.right_margin = Cm(2.5)
    if title:
        h = doc.add_heading(title, level=1)
        h.runs[0].font.size = Pt(16)
        h.runs[0].font.color.rgb = _NAVY
    for line in text.splitlines():
        p = doc.add_paragraph(line)
        p.paragraph_format.space_after = Pt(4)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
