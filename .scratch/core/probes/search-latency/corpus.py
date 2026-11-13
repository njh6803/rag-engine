"""검색 지연 프로브(`probe.py`)의 표본 문서 생성기.

실제 사내 문서가 아니라 규칙으로 지은 한국어 문서다. 재려는 것이 문서 내용의 품질이 아니라 길이와
형식(제목, 문단, 표, 쪽)에 따른 처리 시간이라 내용은 도메인 낱말을 정해진 문형에 끼워 넣어 만들고,
같은 시드로 같은 문서가 나온다. 낱말은 여덟 도메인(인사, 보안, 구매, 시설, 개발, 고객지원, 안전,
재무)에서 나오고, 질의 집합은 같은 낱말에서 뽑아 키워드 쪽도 후보를 내게 한다.

PDF·DOCX·HWPX는 시험이 쓰는 도우미(`tests/support/`)와 같은 방식으로 쓴다. PDF는 글꼴을 내장하지
않은 손으로 쓴 PDF라(`tests/support/pdf_files.py`) 쪽마다 글이 든 PDF의 파싱 시간은 재지만 실제
생산기가 쓴 PDF의 레이아웃 복잡도는 재지 못한다.
"""

import io
import random
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from docx import Document

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.support.hwpx_files import (  # noqa: E402
    HwpxHeading,
    HwpxParagraph,
    HwpxTable,
    hwpx_bytes,
)
from tests.support.pdf_files import PdfPage, pdf_bytes, text_block  # noqa: E402

_PDF_LINE_CHARS = 36
_PDF_LINES_PER_PAGE = 40

# 도메인마다 낱말 열넷. 명사만 두어 조사를 글자 받침으로 골라 붙인다.
_DOMAINS: dict[str, list[str]] = {
    "인사": [
        "연차휴가",
        "휴직",
        "급여",
        "근태",
        "채용",
        "승진",
        "평가",
        "복지",
        "교육",
        "퇴직금",
        "재택근무",
        "출장",
        "초과근무",
        "신입사원",
    ],
    "보안": [
        "접근 권한",
        "비밀번호",
        "백업",
        "계정",
        "방화벽",
        "로그",
        "암호화",
        "취약점",
        "VPN 접속",
        "보안 점검",
        "단말기",
        "인증서",
        "침해 사고",
        "개인정보",
    ],
    "구매": [
        "견적서",
        "검수",
        "대금",
        "발주",
        "계약",
        "공급업체",
        "납품",
        "재고",
        "단가",
        "입찰",
        "구매 요청",
        "세금계산서",
        "반품",
        "품질 기준",
    ],
    "시설": [
        "출입증",
        "회의실",
        "주차장",
        "엘리베이터",
        "비상구",
        "청소",
        "냉난방",
        "방문객",
        "사물함",
        "휴게실",
        "소방 설비",
        "전기 설비",
        "택배",
        "시설 점검",
    ],
    "개발": [
        "배포",
        "장애 대응",
        "코드 리뷰",
        "브랜치",
        "릴리스",
        "테스트",
        "모니터링",
        "롤백",
        "형상 관리",
        "빌드",
        "의존성",
        "운영 환경",
        "API 명세",
        "기술 부채",
    ],
    "고객지원": [
        "문의",
        "환불",
        "교환",
        "불만 접수",
        "상담 이력",
        "응대 시간",
        "만족도",
        "에스컬레이션",
        "서비스 등급",
        "공지",
        "이용 약관",
        "보증 기간",
        "사후 관리",
        "답변 템플릿",
    ],
    "안전": [
        "안전 교육",
        "보호구",
        "작업 허가",
        "사고 보고",
        "위험성 평가",
        "비상 훈련",
        "점검표",
        "응급 처치",
        "화재 예방",
        "유해 물질",
        "작업 환경",
        "순찰",
        "재해 예방",
        "안전 수칙",
    ],
    "재무": [
        "예산",
        "정산",
        "지출 결의",
        "법인카드",
        "회계 마감",
        "세무 신고",
        "자산",
        "감가상각",
        "원가",
        "청구",
        "수금",
        "환율",
        "감사",
        "증빙 서류",
    ],
}
_PLACES = ["전산 시스템", "관리 대장", "공유 문서함", "결재 시스템", "업무 포털", "보관 폴더"]
_DAYS = [3, 5, 7, 10, 14, 30]

# `{n}`은 낱말 번호이고 `|`로 조사 짝(은·이·을·과)을 붙이면 받침에 따라 고른다. `{p}`는 보관처다.
_TEMPLATES = [
    "{a|은} {b|을} 확인한 뒤 {p}에 기록해야 한다.",
    "{a} 담당자는 {d}일 이내에 {b|을} 검토하고 결과를 통보한다.",
    "{b|이} 변경되면 {a|은} 즉시 {p}에 반영한다.",
    "{a|과} {b|은} 분기마다 점검하며 점검 결과는 {p}에 보관한다.",
    "{p}에 등록되지 않은 {b|은} 처리 대상에서 제외한다.",
    "예외가 필요한 경우 {a} 책임자의 승인을 받아 {b|을} 따로 관리한다.",
    "{a|은} 요청을 접수한 날부터 {d}일 안에 {b|을} 처리하고 그 내역을 {p}에 남긴다.",
    "다만 {b|이} 불명확한 경우에는 {a|과} 협의하여 정한다.",
    "{a} 업무를 맡은 부서는 {b|을} 연 1회 이상 정비하고 개선 사항을 공유한다.",
    "{b|은} 담당 부서장이 승인한 경우에만 {a|과} 함께 변경할 수 있다.",
]
_PARTICLES = {"은": ("은", "는"), "이": ("이", "가"), "을": ("을", "를"), "과": ("과", "와")}
_SLOT = re.compile(r"\{(\w)(?:\|(은|이|을|과))?\}")


def _has_final_consonant(word: str) -> bool:
    last = word[-1]
    return "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 != 0


def _render(template: str, words: dict[str, str]) -> str:
    def fill(match: re.Match[str]) -> str:
        word = words[match.group(1)]
        particle = match.group(2)
        if particle is None:
            return word
        with_final, without_final = _PARTICLES[particle]
        return word + (with_final if _has_final_consonant(word) else without_final)

    return _SLOT.sub(fill, template)


def _sentence(rng: random.Random, nouns: Sequence[str]) -> str:
    a, b = rng.sample(list(nouns), 2)
    words = {"a": a, "b": b, "p": rng.choice(_PLACES), "d": str(rng.choice(_DAYS))}
    return _render(rng.choice(_TEMPLATES), words)


def _paragraph(rng: random.Random, nouns: Sequence[str]) -> str:
    return " ".join(_sentence(rng, nouns) for _ in range(rng.randint(3, 5)))


@dataclass(frozen=True, slots=True)
class Section:
    heading: str
    paragraphs: tuple[str, ...]
    table: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class Draft:
    domain: str
    title: str
    sections: tuple[Section, ...]


def draft_document(rng: random.Random, domain: str, *, sections: int) -> Draft:
    nouns = _DOMAINS[domain]
    built: list[Section] = []
    for number in range(1, sections + 1):
        a, b = rng.sample(nouns, 2)
        paragraphs = tuple(_paragraph(rng, nouns) for _ in range(rng.randint(3, 6)))
        table = (
            ("구분", "담당", "기한"),
            *(
                (rng.choice(nouns), rng.choice(nouns), f"{rng.choice(_DAYS)}일")
                for _ in range(rng.randint(2, 4))
            ),
        )
        built.append(Section(f"제{number}장 {a} {b} 기준", paragraphs, table))
    return Draft(domain, f"{domain} 업무 규정 {rng.randint(100, 999)}", tuple(built))


def queries(rng: random.Random, count: int) -> list[str]:
    """도메인 낱말로 짓는 질의. 문장형, 명사구형, 영어가 섞인 것을 번갈아 낸다."""
    forms = [
        "{a} {b} 처리 기한이 얼마나 되나요",
        "{a|이} 변경되면 {b|은} 어떻게 해야 하나",
        "{a} 담당자 승인 절차",
        "{a|과} {b} 점검 주기",
        "{a} 예외 승인",
    ]
    result: list[str] = []
    domains = list(_DOMAINS)
    for index in range(count):
        a, b = rng.sample(_DOMAINS[domains[index % len(domains)]], 2)
        result.append(_render(forms[index % len(forms)], {"a": a, "b": b}))
    return result


def _wrapped(paragraph: str) -> list[str | None]:
    lines: list[str | None] = [
        paragraph[start : start + _PDF_LINE_CHARS]
        for start in range(0, len(paragraph), _PDF_LINE_CHARS)
    ]
    lines.append(None)
    return lines


def _pdf_pages(lines: list[str | None]) -> list[PdfPage]:
    return [
        PdfPage(text_block(*lines[start : start + _PDF_LINES_PER_PAGE]))
        for start in range(0, len(lines), _PDF_LINES_PER_PAGE)
    ]


def pdf_file(draft: Draft) -> bytes:
    """제목과 장 제목, 문단을 줄로 풀어 쓴다. 문단 사이는 빈 줄이고 쪽은
    `_PDF_LINES_PER_PAGE`줄이다. PDF 파서는 제목 블록을 내지 않으므로(명세) 제목도 한 줄의 글로
    든다. 표는 두지 않는다(괘선이 없는 글 표는 문단이 된다)."""
    lines: list[str | None] = [draft.title, None]
    for section in draft.sections:
        lines += [section.heading, None]
        for paragraph in section.paragraphs:
            lines += _wrapped(paragraph)
    return pdf_bytes(_pdf_pages(lines))


def pdf_pages(rng: random.Random, domain: str, *, pages: int) -> list[PdfPage]:
    """쪽이 정확히 `pages`장이 될 때까지 장을 더한 PDF의 쪽들. 한도 근처 문서를 만든다."""
    nouns = _DOMAINS[domain]
    lines: list[str | None] = [f"{domain} 업무 규정 합본", None]
    number = 0
    while len(lines) < pages * _PDF_LINES_PER_PAGE:
        number += 1
        lines += [f"제{number}장 {rng.choice(nouns)} 기준", None]
        for _ in range(rng.randint(3, 6)):
            lines += _wrapped(_paragraph(rng, nouns))
    return _pdf_pages(lines[: pages * _PDF_LINES_PER_PAGE])


def docx_file(draft: Draft) -> bytes:
    document = Document()
    document.add_heading(draft.title, level=1)
    for section in draft.sections:
        document.add_heading(section.heading, level=2)
        for paragraph in section.paragraphs:
            document.add_paragraph(paragraph)
        table = document.add_table(rows=len(section.table), cols=3)
        for row_index, row in enumerate(section.table):
            for column_index, cell in enumerate(row):
                table.cell(row_index, column_index).text = cell
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def hwpx_file(draft: Draft) -> bytes:
    items: list[HwpxHeading | HwpxParagraph | HwpxTable] = [HwpxHeading(draft.title, 1)]
    for section in draft.sections:
        items.append(HwpxHeading(section.heading, 2))
        items += [HwpxParagraph(paragraph) for paragraph in section.paragraphs]
        items.append(HwpxTable(section.table))
    return hwpx_bytes(*items)


@dataclass(frozen=True, slots=True)
class SampleFile:
    path: Path
    kind: str
    characters: int


def write_corpus(directory: Path, *, seed: int, per_kind: int, sections: int) -> list[SampleFile]:
    """도메인을 돌려 가며 PDF, DOCX, HWPX를 `per_kind`개씩 쓴다. 문서마다 장이 `sections`개다."""
    rng = random.Random(seed)
    directory.mkdir(parents=True, exist_ok=True)
    writers = {"pdf": pdf_file, "docx": docx_file, "hwpx": hwpx_file}
    domains = list(_DOMAINS)
    written: list[SampleFile] = []
    for kind, write in writers.items():
        for index in range(per_kind):
            draft = draft_document(rng, domains[index % len(domains)], sections=sections)
            path = directory / f"{kind}_{index:02d}_{draft.domain}.{kind}"
            path.write_bytes(write(draft))
            characters = sum(len(p) for s in draft.sections for p in s.paragraphs)
            written.append(SampleFile(path, kind, characters))
    return written
