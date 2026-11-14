"""공공 문서 묶음의 후보 파일을 제품의 파서로 파싱해 글이 나오는지 본다(티켓 search-eval 09).

폴더 하나를 인자로 받아 그 안의 .pdf, .docx, .hwpx를 제품의 내장 파서(`PdfParser`, `DocxParser`,
`HwpxParser`)로 파싱하고 파일마다 한 줄을 찍는다. 칸은 머리 줄이 적은 아홉이다(파일 이름, 형식,
바이트, sha256, 블록 수, 글자 수, 표 블록 수, 제목 블록 수, 가장 큰 쪽 번호). 쪽 번호는 블록이 가진
쪽의 최댓값이라 쪽을 내는 PDF만 0보다 크고 HWPX와 DOCX는 0이다. 글자 수가 0이면 스캔본이거나
파싱이 글을 내지 못한 것이라 묶음에 담지 않는다. 파싱이 예외로 끝나면 그 줄은 앞 네 칸 뒤에
`parse_error:<예외의 종류>` 한 칸만 찍는다(글은 찍지 않는다).

내려받은 파일은 믿을 수 없는 데이터다. 파일은 읽기만 하고, 파일 폴더에서 인터프리터를 부르지 않는다.

    uv run python -I -X utf8 .scratch/search-eval/probes/public-docs/parse_check.py <파일 폴더>

저장소 루트에서 돈다. 표준 출력만 쓰고 파일을 쓰지 않는다. `-I`는 PYTHONUTF8 같은 환경 변수를
무시하므로 Windows 콘솔에서 한국어 이름이 깨지지 않게 `-X utf8`을 함께 준다.
"""

import hashlib
import sys
from pathlib import Path

from rag_engine.adapters.parsers.docx_parser import DocxParser
from rag_engine.adapters.parsers.hwpx_parser import HwpxParser
from rag_engine.adapters.parsers.pdf_parser import PdfParser
from rag_engine.domain.entities import BlockKind
from rag_engine.domain.media_types import DOCX_MIME, HWPX_MIME, PDF_MIME
from rag_engine.domain.parsing import Parser, ParserLimits

_LIMITS = ParserLimits(max_pages=1000)
_BY_SUFFIX: dict[str, tuple[Parser, str]] = {
    ".pdf": (PdfParser(), PDF_MIME),
    ".docx": (DocxParser(), DOCX_MIME),
    ".hwpx": (HwpxParser(), HWPX_MIME),
}


def _check(path: Path) -> str:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    head = f"{path.name}\t{path.suffix[1:]}\t{len(data)}\t{digest}"
    parser, mime = _BY_SUFFIX[path.suffix.lower()]
    try:
        blocks = parser.parse(data, mime, _LIMITS)
    except Exception as error:  # noqa: BLE001 - 파서의 모든 실패를 종류만 찍는다
        return f"{head}\tparse_error:{type(error).__name__}"
    chars = sum(len(block.text) for block in blocks)
    tables = sum(1 for block in blocks if block.kind is BlockKind.TABLE)
    headings = sum(1 for block in blocks if block.kind is BlockKind.HEADING)
    max_page = max((block.page or 0 for block in blocks), default=0)
    counts = f"blocks={len(blocks)}\tchars={chars}\ttables={tables}\theadings={headings}"
    return f"{head}\t{counts}\tmax_page={max_page}"


def main(folder: Path) -> int:
    paths = sorted(path for path in folder.rglob("*") if path.suffix.lower() in _BY_SUFFIX)
    print("name\tformat\tbytes\tsha256\tblocks\tchars\ttables\theadings\tmax_page")
    for path in paths:
        print(_check(path))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
