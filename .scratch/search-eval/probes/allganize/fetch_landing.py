"""`allganize_bundle.py fetch`가 받지 못한 게시판 페이지의 첨부 PDF를 찾아 받는다(티켓 search-eval
19).

`fetch`가 받은 폴더(`--out`)의 `missing.tsv`(받을 문서의 목록)를 읽는다. `missing.tsv`는 번호,
도메인, 질문 수, 쪽수, 파일 이름, 출처 주소, 자동 결과를 탭으로 가른 줄이다. 번호를 인자로 주면 그
문서만 받는다. 같은 출처 주소를 가진 문서는 페이지를 한 번만 읽는다.

문서마다 출처 주소의 페이지를 `curl`(Windows에서는 인증서를 운영체제 저장소로 확인한다)로 읽어 첨부
후보 주소를 모은다. 링크의 주소에 `pdf`, `down`, `file`, `attach`, `getfile`, `bbs/home`가 든 것과
법원 게시판의 `download('<파일>', ...)` 호출(`https://file.scourt.go.kr/dcboard/<파일>`로 바꾼다)이
후보다. 후보를 받아 `%PDF-`로 시작하고 쪽 수가 `documents.csv`의 쪽수와 같은 파일만
`pdf/<번호>.pdf`로 둔다. 쪽 수가 같은 후보가 여럿이면 파일 이름의 앞 여덟 글자가 든 것을 먼저
고른다. 인증서 확인을 끄지 않는다.

    uv run python -I -X utf8 .scratch/search-eval/probes/allganize/fetch_landing.py <폴더> [번호
    ...]

저장소 루트에서 돈다. 받은 파일은 믿을 수 없는 데이터라 읽지만 실행하지 않는다.

못 보는 것. (1) 쪽 수가 같다고 그 문서라는 뜻이 아니다. 게시판은 "지금 올라 있는 첨부"를 주므로
지난 보도자료 자리에 다른 날의 문서가 쪽 수만 같게 들어올 수 있다(`documents.csv`의 5번이 그랬다.
6쪽짜리 금융위 보도자료 대신 2026-11-13자 주택시장 보도자료를 받았다). 그 판정은
`verify_documents.py` 가 정답 낱말로 대 보고, 후보를 사람이 읽고
`allganize_bundle.py convert --exclude`로 뺀다. (2) 첨부를 스크립트로만 내거나 보기 화면만 있는
페이지(문서 9, 10, 15, 20, 21, 49, 64)와 첨부 링크가 없는 법원 게시판(문서 51)은 후보를 찾지 못한다.
(3) 지난 보도자료가 내려간 게시판(문서 6, 7, 8)은 받을 파일이 없다. (4) 쪽 수가 하나 다른 판(외교부
앙골라 개황 47쪽, 목록은 48쪽, 문서 19)은 받지 않는다.
"""

import io
import re
import subprocess
import sys
import tempfile
from html import unescape
from pathlib import Path
from typing import Final
from urllib.parse import unquote, urljoin

from pdfminer.pdfpage import PDFPage

_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
)
_LINK: Final = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_HINT: Final = re.compile(r"pdf|down|file|attach|getfile|bbs/home", re.IGNORECASE)
_NOT_PDF: Final = re.compile(
    r"\.(?:jpg|jpeg|png|gif|css|js|ico|svg|hwp|hwpx|xlsx?|docx?|pptx?|zip)(?:\?|$)", re.IGNORECASE
)
_COURT_DOWNLOAD: Final = re.compile(r"download\('([^']+)'")
_COURT_FILES: Final = "https://file.scourt.go.kr/dcboard/"
_MAX_CANDIDATES: Final = 14
_CURL_SECONDS: Final = 90
_CALL_SECONDS: Final = 120


def _curl(url: str, out: Path, jar: Path, referer: str | None = None) -> tuple[int, str, str]:
    """(종료 코드, 최종 주소, 응답 머리). 시간을 넘기면 종료 코드 28이다."""
    head = out.with_suffix(out.suffix + ".h")
    command = ["curl", "-sSL", "--max-time", str(_CURL_SECONDS), "-A", _AGENT]
    command += ["-b", str(jar), "-c", str(jar), "-D", str(head), "-o", str(out)]
    command += ["-w", "%{url_effective}"]
    if referer:
        command += ["-e", referer]
    command.append(url)
    try:
        done = subprocess.run(command, capture_output=True, timeout=_CALL_SECONDS, check=False)  # noqa: S603
    except subprocess.TimeoutExpired:
        return 28, url, ""
    headers = head.read_text(encoding="latin-1") if head.exists() else ""
    return done.returncode, done.stdout.decode("latin-1"), headers


def _decode(body: bytes) -> str:
    for encoding in ("utf-8", "euc-kr"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("latin-1")


def _pages(data: bytes) -> int | None:
    try:
        return sum(1 for _ in PDFPage.get_pages(io.BytesIO(data)))
    except Exception:  # noqa: BLE001 - 깨진 파일의 모든 실패를 쪽 수 없음으로 센다
        return None


def _candidates(html: str, base: str) -> list[str]:
    found: list[str] = []
    for raw in _LINK.findall(html):
        link = unescape(raw).strip()
        if link.startswith(("javascript:", "#", "mailto:")):
            continue
        absolute = urljoin(base, link)
        if _HINT.search(absolute) and not _NOT_PDF.search(absolute) and absolute not in found:
            found.append(absolute)
    found.extend(_COURT_FILES + match for match in _COURT_DOWNLOAD.findall(html))
    return found[:_MAX_CANDIDATES]


def _wanted(root: Path, only: set[int]) -> dict[str, list[tuple[int, str, int]]]:
    """출처 주소마다 (번호, 파일 이름, 쪽수)의 목록. 이미 받은 문서는 뺀다."""
    lines = (root / "missing.tsv").read_text(encoding="utf-8").splitlines()[1:]
    by_url: dict[str, list[tuple[int, str, int]]] = {}
    for line in lines:
        cells = line.split("\t")
        index = int(cells[0])
        if (only and index not in only) or (root / "pdf" / f"{index:02d}.pdf").exists():
            continue
        pages = int(cells[3]) if cells[3].isdigit() else -1
        by_url.setdefault(cells[5], []).append((index, cells[4], pages))
    return by_url


def _download(
    candidates: list[str], referer: str, work: Path, jar: Path
) -> dict[str, tuple[bytes, str]]:
    got: dict[str, tuple[bytes, str]] = {}
    for number, candidate in enumerate(candidates):
        target = work / f"c{number}.bin"
        target.unlink(missing_ok=True)
        code, _, headers = _curl(candidate, target, jar, referer)
        if code != 0 or not target.exists():
            continue
        data = target.read_bytes()
        if not data.startswith(b"%PDF-"):
            continue
        named = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";\r\n]+)", headers, re.IGNORECASE)
        got[candidate] = (data, unquote(named.group(1)) if named else candidate.rsplit("/", 1)[-1])
    return got


def _place(
    root: Path, wanted: list[tuple[int, str, int]], got: dict[str, tuple[bytes, str]]
) -> None:
    counted = {url: (_pages(data), name) for url, (data, name) in got.items()}
    for index, name, expected in wanted:
        stem = re.sub(r"\W", "", Path(name).stem)[:8]
        exact = [url for url, (count, _) in counted.items() if count == expected]
        exact.sort(key=lambda url: stem not in re.sub(r"\W", "", counted[url][1]))
        if exact:
            data = got[exact[0]][0]
            (root / "pdf" / f"{index:02d}.pdf").write_bytes(data)
            print(f"OK   {index:02d} pages={expected} bytes={len(data)} ties={len(exact)}")
        else:
            have = [count for count, _ in counted.values()]
            print(f"MISS {index:02d} want_pages={expected} have_pages={have[:6]}")


def main(argv: list[str]) -> int:
    root = Path(argv[0])
    only = {int(item) for item in argv[1:]}
    with tempfile.TemporaryDirectory(prefix="allganize_") as folder:
        work = Path(folder)
        jar = work / "jar"
        for url, wanted in _wanted(root, only).items():
            page = work / "page.html"
            page.unlink(missing_ok=True)
            code, final, _ = _curl(url, page, jar)
            if code != 0 or not page.exists():
                print(f"PAGE-FAIL curl={code} docs={[item[0] for item in wanted]}")
                continue
            candidates = _candidates(_decode(page.read_bytes()), final)
            got = _download(candidates, final, work, jar)
            print(
                f"PAGE docs={[item[0] for item in wanted]} cands={len(candidates)} pdfs={len(got)}"
            )
            _place(root, wanted, got)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
