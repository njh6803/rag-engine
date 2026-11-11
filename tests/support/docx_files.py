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


def docx_outline(*entries: str | tuple[int, str]) -> bytes:
    """문자열은 문단이고 `(수준, 글)`은 그 수준의 제목인 DOCX 바이트. 수준은 1부터다."""
    document = Document()
    for entry in entries:
        if isinstance(entry, str):
            document.add_paragraph(entry)
        else:
            level, text = entry
            document.add_heading(text, level=level)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
