"""DOCX text extraction."""

from io import BytesIO

from docx import Document


def parse_docx(content: bytes) -> str:
    doc = Document(BytesIO(content))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
