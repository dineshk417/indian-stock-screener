import io
from docx import Document
from docx.shared import Pt


def text_to_docx_bytes(text: str, title: str = "") -> bytes:
    doc = Document()
    if title:
        heading = doc.add_heading(title, level=1)
        heading.runs[0].font.size = Pt(16)
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
