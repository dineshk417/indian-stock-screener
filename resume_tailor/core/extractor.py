import io
import fitz  # pymupdf
from docx import Document


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n\n".join(p for p in pages if p.strip())


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text_from_upload(uploaded_file) -> str:
    file_bytes = uploaded_file.read()
    mime = uploaded_file.type
    if mime == "application/pdf":
        return extract_text_from_pdf(file_bytes)
    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return extract_text_from_docx(file_bytes)
    raise ValueError(f"Unsupported file type: {mime}")
