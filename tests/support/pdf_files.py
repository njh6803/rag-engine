"""시험이 손으로 쓰는 PDF 픽스처(티켓 08).

PDF를 쓰는 라이브러리가 의존성에 없어서 최소한의 PDF를 직접 쓴다. 글꼴은 내장하지 않은 Type0
(Identity-H)이고 글자마다 CID를 새로 매기며, `ToUnicode` 사상이 CID를 글자로 되돌려 한글도 뽑힌다.
선(`PdfRule`)은 표 추출이 읽는 괘선이다. 암호 PDF는 표준 보안 처리기(V1, R2, RC4 40비트)로 스트림을
암호화해 쓴다. 이 도우미가 낸 암호 PDF가 정말 암호 PDF인지는 맞는 암호로 열리는 시험이 보인다.
"""

import hashlib
import struct
from collections.abc import Sequence
from dataclasses import dataclass

FONT_SIZE = 12.0
LEADING = 16.0
_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")
_FILE_ID = bytes(range(16))
_OWNER_PASSWORD = b"owner-only-secret"
_PERMISSIONS = -4


@dataclass(frozen=True, slots=True)
class PdfText:
    x: float
    y: float
    text: str


@dataclass(frozen=True, slots=True)
class PdfRule:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True, slots=True)
class PdfPage:
    texts: tuple[PdfText, ...] = ()
    rules: tuple[PdfRule, ...] = ()


def text_block(*lines: str | None, top: float = 740.0, x: float = 72.0) -> tuple[PdfText, ...]:
    """줄 간격 `LEADING`으로 위에서 아래로 쓴다. `None`은 빈 줄이다(그만큼 더 내려간다)."""
    texts: list[PdfText] = []
    y = top
    for line in lines:
        if line is not None:
            texts.append(PdfText(x, y, line))
        y -= LEADING
    return tuple(texts)


def grid(
    rows: Sequence[Sequence[str]],
    *,
    top: float,
    x: float = 72.0,
    cell_width: float = 100.0,
    cell_height: float = 24.0,
) -> PdfPage:
    """괘선이 있는 표. 칸마다 글 하나를 쓰고 가로·세로 괘선을 긋는다."""
    columns = max(len(row) for row in rows)
    bottom = top - len(rows) * cell_height
    right = x + columns * cell_width
    rules = [
        PdfRule(x, top - i * cell_height, right, top - i * cell_height)
        for i in range(len(rows) + 1)
    ]
    rules += [
        PdfRule(x + j * cell_width, top, x + j * cell_width, bottom) for j in range(columns + 1)
    ]
    texts = [
        PdfText(x + j * cell_width + 6, top - (i + 1) * cell_height + 8, cell)
        for i, row in enumerate(rows)
        for j, cell in enumerate(row)
    ]
    return PdfPage(tuple(texts), tuple(rules))


def merge(*parts: PdfPage | tuple[PdfText, ...]) -> PdfPage:
    texts: list[PdfText] = []
    rules: list[PdfRule] = []
    for part in parts:
        if isinstance(part, PdfPage):
            texts.extend(part.texts)
            rules.extend(part.rules)
        else:
            texts.extend(part)
    return PdfPage(tuple(texts), tuple(rules))


def pdf_bytes(pages: Sequence[PdfPage], *, user_password: str | None = None) -> bytes:
    """페이지들로 PDF를 쓴다. `user_password`를 주면 그 암호가 있어야 열린다."""
    characters = sorted({char for page in pages for text in page.texts for char in text.text})
    cids = {char: index + 1 for index, char in enumerate(characters)}
    builder = _Builder(user_password)
    builder.add_dict("<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = [7 + 2 * index + 1 for index in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    builder.add_dict(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    builder.add_dict(
        "<< /Type /Font /Subtype /Type0 /BaseFont /TestSans /Encoding /Identity-H"
        " /DescendantFonts [4 0 R] /ToUnicode 6 0 R >>"
    )
    space = cids.get(" ")
    widths = f" /W [{space} [250]]" if space is not None else ""
    builder.add_dict(
        "<< /Type /Font /Subtype /CIDFontType2 /BaseFont /TestSans"
        " /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>"
        f" /FontDescriptor 5 0 R /DW 1000{widths} >>"
    )
    builder.add_dict(
        "<< /Type /FontDescriptor /FontName /TestSans /Flags 4 /FontBBox [0 -200 1000 900]"
        " /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>"
    )
    builder.add_stream("", _to_unicode_cmap(cids).encode())
    for page in pages:
        content = builder.add_stream("", _content_stream(page, cids).encode())
        builder.add_dict(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            f" /Contents {content} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
    return builder.finish()


def blank_pages_pdf(page_count: int) -> bytes:
    """글도 내용도 없는 쪽이 `page_count`장인 PDF. 쪽이 수만 장인 문서를 싸게 만든다."""
    builder = _Builder(None)
    builder.add_dict("<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + index} 0 R" for index in range(page_count))
    builder.add_dict(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>")
    for _ in range(page_count):
        builder.add_dict("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")
    return builder.finish()


def _content_stream(page: PdfPage, cids: dict[str, int]) -> str:
    operations = ["0.5 w"]
    operations += [f"{r.x1} {r.y1} m {r.x2} {r.y2} l S" for r in page.rules]
    for text in page.texts:
        hex_codes = "".join(f"{cids[char]:04X}" for char in text.text)
        operations.append(f"BT /F1 {FONT_SIZE} Tf 1 0 0 1 {text.x} {text.y} Tm <{hex_codes}> Tj ET")
    return "\n".join(operations)


def _to_unicode_cmap(cids: dict[str, int]) -> str:
    entries = [
        f"<{cid:04X}> <{char.encode('utf-16-be').hex().upper()}>" for char, cid in cids.items()
    ]
    blocks = [
        f"{len(chunk)} beginbfchar\n" + "\n".join(chunk) + "\nendbfchar"
        for chunk in (entries[start : start + 100] for start in range(0, len(entries), 100))
    ]
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        + "\n".join(blocks)
        + "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    )


class _Builder:
    """객체를 차례로 쓰고 xref와 trailer를 붙인다. 객체 번호는 1부터 더한 차례다."""

    def __init__(self, user_password: str | None) -> None:
        self._body = bytearray(b"%PDF-1.4\n")
        self._offsets: list[int] = []
        self._key: bytes | None = None
        self._encrypt_entry = ""
        if user_password is not None:
            self._key, self._encrypt_entry = _encryption(user_password.encode())

    def add_dict(self, text: str) -> int:
        return self._add(text.encode())

    def add_stream(self, entries: str, data: bytes) -> int:
        number = len(self._offsets) + 1
        payload = data if self._key is None else _rc4(self._object_key(number), data)
        head = f"<< {entries} /Length {len(payload)} >>\nstream\n".encode()
        return self._add(head + payload + b"\nendstream")

    def finish(self) -> bytes:
        encrypt_id = self.add_dict(self._encrypt_entry) if self._key is not None else None
        xref_at = len(self._body)
        count = len(self._offsets) + 1
        xref = [f"xref\n0 {count}\n0000000000 65535 f \n"]
        xref += [f"{offset:010d} 00000 n \n" for offset in self._offsets]
        trailer = f"trailer\n<< /Size {count} /Root 1 0 R"
        if encrypt_id is not None:
            file_id = _FILE_ID.hex()
            trailer += f" /Encrypt {encrypt_id} 0 R /ID [<{file_id}> <{file_id}>]"
        trailer += f" >>\nstartxref\n{xref_at}\n%%EOF\n"
        return bytes(self._body) + "".join(xref).encode() + trailer.encode()

    def _add(self, content: bytes) -> int:
        number = len(self._offsets) + 1
        self._offsets.append(len(self._body))
        self._body += f"{number} 0 obj\n".encode() + content + b"\nendobj\n"
        return number

    def _object_key(self, number: int) -> bytes:
        assert self._key is not None
        material = self._key + number.to_bytes(3, "little") + (0).to_bytes(2, "little")
        return hashlib.md5(material, usedforsecurity=False).digest()[: len(self._key) + 5]


def _encryption(user_password: bytes) -> tuple[bytes, str]:
    """표준 보안 처리기 R2(RC4 40비트)의 파일 키와 `/Encrypt` 사전."""
    padded_user = (user_password + _PAD)[:32]
    # 소유자 암호가 비면 빈 암호가 소유자로 인증되어 사용자 암호를 되찾으므로 따로 정한다.
    owner_key = hashlib.md5((_OWNER_PASSWORD + _PAD)[:32], usedforsecurity=False).digest()[:5]
    owner_entry = _rc4(owner_key, padded_user)
    permissions = struct.pack("<i", _PERMISSIONS)
    material = padded_user + owner_entry + permissions + _FILE_ID
    key = hashlib.md5(material, usedforsecurity=False).digest()[:5]
    user_entry = _rc4(key, _PAD)
    entry = (
        f"<< /Filter /Standard /V 1 /R 2 /O <{owner_entry.hex()}> /U <{user_entry.hex()}>"
        f" /P {_PERMISSIONS} >>"
    )
    return key, entry


def _rc4(key: bytes, data: bytes) -> bytes:
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]
    output = bytearray()
    i = j = 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        output.append(byte ^ state[(state[i] + state[j]) % 256])
    return bytes(output)
