"""PDF text extraction."""

from io import BytesIO

from pypdf import PdfReader


def parse_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n\n".join(text_parts)
