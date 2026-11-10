"""시험이 python-docx로 만드는 DOCX 픽스처. 저장소에 바이너리를 두지 않는다(티켓 07)."""

import io

from docx import Document


def docx_bytes(title: str, *paragraphs: str) -> bytes:
    """수준 1 제목 하나와 문단들로 이뤄진 DOCX 바이트."""
    document = Document()
    document.add_heading(title, level=1)
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
