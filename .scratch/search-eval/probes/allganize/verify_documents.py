"""내려받은 PDF가 데이터셋이 가리킨 그 문서인지 글로 대 본다(티켓 search-eval 19).

게시판 페이지에서 받은 첨부는 "지금 올라 있는 파일"이라 지난 보도자료 대신 다른 문서일 수 있다. 쪽
수가 같다는 것만으로는 이를 거르지 못한다(문서 5는 6쪽으로 같았으나 다른 날의 보도자료였다). 이
스크립트는 문서마다 `image`가 아닌 질문의 정답 낱말(두 글자 이상)이 PDF의 어느 쪽에 얼마나 드는지
센다. 글층이 없는 `image` 질문은 대 볼 수 없어 뺀다.

    uv run python -I -X utf8 .scratch/search-eval/probes/allganize/verify_documents.py --out <폴더>

`--out` 폴더(`allganize_bundle.py fetch`가 만든 폴더)를 읽고 `--out/verify_report.tsv`에 문서마다 한
줄을 쓴다. 칸은 번호, 도메인, 쪽 수, 글자 수, 대 본 질문 수, 가장 겹치는 쪽의 겹침 중앙값
(`median_best`), 기대한 쪽의 겹침 중앙값(`median_at`), 판정이다. 판정은 다음과 같다. 기계가 가려
주는 것은 후보까지이고, 후보를 제외할지는 사람이 첫 쪽의 글과 질문을 읽고 정한다.

- `no_text_layer`: 글자가 0자다(스캔본). 파서가 읽을 수 없으므로 글로 대 볼 수 없다.
- `no_text_questions`: 대 볼 질문(`image`가 아닌 것)이 없다.
- `suspect`: `median_best`가 0.15 미만이다. 다른 문서이거나 글자가 깨진 문서다.
- `ok`: 그 밖이다.

내려받은 파일은 믿을 수 없는 데이터다. 읽기만 하고 실행하지 않는다.
"""

import argparse
import csv
import re
import statistics
import sys
from pathlib import Path
from typing import Final

import pdfplumber

_SUSPECT_BELOW: Final = 0.15
_WORD: Final = re.compile(r"[가-힣A-Za-z0-9]{2,}")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text))


def _verdict(chars: int, scored: int, median_best: float) -> str:
    if chars == 0:
        return "no_text_layer"
    if scored == 0:
        return "no_text_questions"
    return "suspect" if median_best < _SUSPECT_BELOW else "ok"


def verify(out: Path) -> int:
    documents = _read_rows(out / "documents.csv")
    questions = _read_rows(out / "rag_evaluation_result.csv")
    lines = ["번호\t도메인\t쪽수\t글자수\t질문수\tmedian_best\tmedian_at\t판정"]
    for index, row in enumerate(documents, start=1):
        path = out / "pdf" / f"{index:02d}.pdf"
        if not path.exists():
            continue
        with pdfplumber.open(path) as pdf:
            page_words = [_words(page.extract_text() or "") for page in pdf.pages]
            chars = sum(len(page.extract_text() or "") for page in pdf.pages)
        best: list[float] = []
        at_page: list[float] = []
        for question in questions:
            if question["target_file_name"] != row["file_name"]:
                continue
            if question["context_type"].strip() == "image":
                continue
            answer = _words(question["target_answer"])
            if not answer:
                continue
            scores = [len(answer & words) / len(answer) for words in page_words]
            best.append(max(scores, default=0.0))
            page = question["target_page_no"].strip()
            number = int(page) if page.isdigit() else 0
            at_page.append(scores[number - 1] if 1 <= number <= len(scores) else 0.0)
        median_best = statistics.median(best) if best else 0.0
        median_at = statistics.median(at_page) if at_page else 0.0
        verdict = _verdict(chars, len(best), median_best)
        lines.append(
            f"{index:02d}\t{row['domain']}\t{len(page_words)}\t{chars}\t{len(best)}"
            f"\t{median_best:.2f}\t{median_at:.2f}\t{verdict}"
        )
    (out / "verify_report.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="내려받은 PDF가 그 문서인지 글로 대 본다")
    parser.add_argument("--out", type=Path, required=True)
    return verify(parser.parse_args(argv).out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
