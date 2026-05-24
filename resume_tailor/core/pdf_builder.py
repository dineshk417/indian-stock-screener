import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Colour palette ────────────────────────────────────────────────────────────
C_NAVY   = HexColor("#1B2A4A")
C_ACCENT = HexColor("#2E6DA4")
C_WHITE  = white
C_BLACK  = HexColor("#111111")
C_DARK   = HexColor("#2D2D2D")
C_MID    = HexColor("#555555")
C_SUBTLE = HexColor("#888888")
C_CARD   = HexColor("#F4F6F9")   # very light blue-gray for section bodies

# ── Fonts (built-in, always available) ───────────────────────────────────────
F   = "Helvetica"
FB  = "Helvetica-Bold"
FI  = "Helvetica-Oblique"

# ── Page geometry ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4          # 595.27 x 841.89 pts
MARGIN_X = 1.8 * cm
MARGIN_Y = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN_X   # ≈ 457 pts

# ── Paragraph styles ─────────────────────────────────────────────────────────
def _ps(name, font=F, size=10, color=C_BLACK, align=TA_LEFT,
        leading=None, spaceAfter=0, spaceBefore=0,
        leftIndent=0, firstLineIndent=0):
    return ParagraphStyle(
        name,
        fontName=font, fontSize=size,
        textColor=color,
        alignment=align,
        leading=leading or size * 1.25,
        spaceAfter=spaceAfter,
        spaceBefore=spaceBefore,
        leftIndent=leftIndent,
        firstLineIndent=firstLineIndent,
    )

S_NAME     = _ps("name",    FB,  20, C_WHITE, TA_CENTER, leading=24)
S_CONTACT  = _ps("contact",  F,   9, HexColor("#BDC9DC"), TA_CENTER, leading=13)
S_SECTION  = _ps("section", FB,  9.5, C_WHITE, leading=12)
S_ROLE     = _ps("role",    FB, 10,  C_DARK)
S_DATE     = _ps("date",     F,  9,  C_MID, TA_RIGHT)
S_ORG      = _ps("org",     FI, 9.5, C_MID)
S_LOC      = _ps("loc",      F,  9,  C_SUBTLE, TA_RIGHT)
S_BULLET   = _ps("bullet",   F,  9.5, C_DARK, leading=13,
                  leftIndent=10, firstLineIndent=-10, spaceAfter=1)
S_BODY     = _ps("body",     F,  9.5, C_DARK, leading=13, spaceAfter=3)
S_SKILL_LB = _ps("skill_lb", FB, 9.5, C_DARK)
S_SKILL_TX = _ps("skill_tx",  F, 9.5, C_DARK)
S_SUMMARY  = _ps("summary",   F, 9.5, C_DARK, leading=14, spaceAfter=2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section_header(title: str) -> Table:
    """Dark navy card with white section title."""
    cell = Paragraph(f"<b>{title.upper()}</b>", S_SECTION)
    t = Table([[cell]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    return t


def _entry_block(role, org, duration, location, bullets) -> list:
    """Returns a list of flowables for one job / education entry."""
    col_l = CONTENT_W * 0.70
    col_r = CONTENT_W * 0.30

    rows = []
    # Role | Date
    rows.append([
        Paragraph(f"<b>{role}</b>", S_ROLE) if role else Paragraph("", S_ROLE),
        Paragraph(duration or "", S_DATE),
    ])
    # Org | Location
    if org or location:
        rows.append([
            Paragraph(org or "", S_ORG),
            Paragraph(location or "", S_LOC),
        ])

    tbl = Table(rows, colWidths=[col_l, col_r])
    tbl.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
    ]))

    items = [Spacer(1, 3), tbl]
    for b in bullets:
        items.append(Paragraph(f"• {b}", S_BULLET))
    items.append(Spacer(1, 5))
    return items


def _skills_block(categories: list) -> list:
    items = []
    for cat in categories:
        label = (cat.get("label") or "").strip()
        vals  = (cat.get("items") or "").strip()
        if not vals:
            continue
        text = f'<font name="{FB}">{label}:  </font>{vals}' if label else vals
        items.append(Paragraph(text, S_BODY))
    items.append(Spacer(1, 4))
    return items


# ── Name / contact header drawn on canvas ────────────────────────────────────

def _draw_header(canvas, doc, name: str, contacts: list[str]):
    canvas.saveState()
    banner_h = 2.5 * cm
    y0 = PAGE_H - MARGIN_Y - banner_h
    # Navy banner
    canvas.setFillColor(C_NAVY)
    canvas.roundRect(MARGIN_X, y0, CONTENT_W, banner_h, 4, fill=1, stroke=0)
    # Name
    canvas.setFillColor(C_WHITE)
    canvas.setFont(FB, 18)
    canvas.drawCentredString(PAGE_W / 2, y0 + banner_h - 0.8 * cm, name.upper())
    # Contact bar
    canvas.setFont(F, 9)
    canvas.setFillColor(HexColor("#BDC9DC"))
    contact_str = "   •   ".join(c for c in contacts if c)
    canvas.drawCentredString(PAGE_W / 2, y0 + 0.3 * cm, contact_str)
    canvas.restoreState()


# ── Public builder ────────────────────────────────────────────────────────────

def build_resume_pdf(structure: dict) -> bytes:
    buf = io.BytesIO()

    name     = (structure.get("name") or "Your Name").strip()
    contacts = [c.strip() for c in structure.get("contact", []) if c and c.strip()]
    summary  = (structure.get("summary") or "").strip()

    # Reserve space for the fixed header banner (2.5cm + gap)
    top_offset = 2.5 * cm + 0.5 * cm

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_Y + top_offset, bottomMargin=MARGIN_Y,
    )
    frame = Frame(
        MARGIN_X, MARGIN_Y,
        CONTENT_W, PAGE_H - 2 * MARGIN_Y - top_offset,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
    )

    def _on_page(canvas, doc):
        _draw_header(canvas, doc, name, contacts)

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_on_page)])

    story = []

    # Summary
    if summary:
        story += [
            _section_header("Summary"),
            Spacer(1, 4),
            Paragraph(summary, S_SUMMARY),
            Spacer(1, 6),
        ]

    # Sections
    for section in structure.get("sections", []):
        title = section.get("title", "")
        kind  = section.get("type", "text")

        section_items = [_section_header(title), Spacer(1, 4)]

        if kind == "entries":
            for e in section.get("entries", []):
                section_items += _entry_block(
                    role     = e.get("role", ""),
                    org      = e.get("org", ""),
                    duration = e.get("duration", ""),
                    location = e.get("location", ""),
                    bullets  = e.get("bullets", []),
                )

        elif kind == "skills":
            section_items += _skills_block(section.get("categories", []))

        else:
            content = (section.get("content") or "").strip()
            if content:
                section_items += [Paragraph(content, S_BODY), Spacer(1, 4)]

        story.append(KeepTogether(section_items[:4]))   # keep header with first entry
        story += section_items[4:]
        story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()
