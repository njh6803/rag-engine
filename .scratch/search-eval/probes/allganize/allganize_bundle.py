"""공개 데이터셋 allganize/RAG-Evaluation-Dataset-KO를 평가 세트 묶음으로 바꾼다(티켓 search-eval
19).

하위 명령이 둘이다. 표준 라이브러리만 쓴다. 저장소 루트에서 돈다.

`fetch`는 데이터셋의 파일(`documents.csv`, `rag_evaluation_result.csv`)과 문서의 PDF를 `--out`
폴더에 내려받는다. 데이터셋은 PDF를 싣지 않고 출처 주소만 `documents.csv`에 적는다. 주소가 PDF를
바로 가리키면 그 주소에서 받고, 게시판 페이지를 가리키면 받지 않고 `landing`으로 기록한다. 받은
바이트가 `%PDF-`로 시작하지 않아도 받지 못한 것으로 센다. 결과는 `--out/fetch_report.tsv`(문서 순번,
도메인, 파일 이름, 상태, 바이트)에 적고, 받지 못했고 질문이 달린 문서는 `--out/missing.tsv`에도
적는다 (`fetch_landing.py`가 읽는다). 이미 있는 `pdf/NN.pdf`는 다시 받지 않는다.

    uv run python -I -X utf8 .scratch/search-eval/probes/allganize/allganize_bundle.py fetch --out
    <폴더>

`convert`는 `--out` 폴더의 내려받은 파일로 묶음 폴더 `--bundle`을 만든다. 질문은 사람이 만든 질문
목록 하나(`human`)로 옮기고, 기대 근거는 문서와 쪽 번호(`kind: page`)로 적는다. `context_type`이
`image`인 문항은 `figure`, `table`인 문항은 `table`로 표시한다. 내려받지 못한 문서가 기대 근거인
질문은 묶음에 넣지 않고 `--bundle/convert_report.json`에 수를 적는다. 쪽 번호가 문서 목록의 `pages`
칸(PDF를 열어 센 쪽 수가 아니다)을 넘는 문항도 같은 곳에 세어 뺀다. `--exclude <번호> ...`는
받았으나 그 문서가 아니라고 `verify_documents.py`의 후보를 사람이 읽고 판정한 문서의 번호이고, 그
문서와 질문을 묶음에서 빼고 `convert_report.json`의 `excluded_documents`에 번호를 적는다. 문서의
`updated_at`과 `downloaded_at`은 데이터셋이 날짜를 주지 않아 `convert`를 돌린 날(KST)이다.

    uv run python -I -X utf8 .scratch/search-eval/probes/allganize/allganize_bundle.py convert --out
    <폴더> --bundle <묶음 폴더> [--exclude <번호> ...]

문서의 `key`는 `<도메인>/<번호>-<파일 이름의 줄기에서 금지 문자를 `_`로 바꾼 뒤 앞 40자>.pdf`다.

내려받은 파일은 믿을 수 없는 데이터다. 파일은 읽고 바이트로 해시만 내며 실행하지 않는다. PDF와
질문은 저장소 밖의 폴더에만 두고 커밋하지 않는다.
"""

import argparse
import csv
import hashlib
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

DATASET: Final = "allganize/RAG-Evaluation-Dataset-KO"
# 카드를 읽은 판(2026-11-15). 다른 판이 올라와도 같은 파일을 받는다.
REVISION: Final = "35db50ff8739d78b11ee68b6f4ef04a95862a504"
_HF_FILE: Final = "https://huggingface.co/datasets/" + DATASET + "/resolve/" + REVISION + "/{name}"
_META_FILES: Final = ("README.md", "documents.csv", "rag_evaluation_result.csv")
_AGENT: Final = "Mozilla/5.0 (compatible; rag-engine-eval-probe)"
_TIMEOUT_SECONDS: Final = 60
_MAX_PDF_BYTES: Final = 60 * 1024 * 1024
_UNSAFE_NAME: Final = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DIRECT_HINTS: Final = (".pdf", "download", "filedownload")
_TAGS: Final = {"image": "figure", "table": "table"}
_KST: Final = timezone(timedelta(hours=9))


def _get(url: str) -> tuple[int, bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": _AGENT})  # noqa: S310
    try:
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=_TIMEOUT_SECONDS, context=ssl.create_default_context()
        ) as response:
            return (
                response.status,
                response.read(_MAX_PDF_BYTES + 1),
                response.headers.get("Content-Type", ""),
            )
    except urllib.error.HTTPError as error:
        return error.code, b"", ""
    except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as error:
        return 0, type(error).__name__.encode(), ""


def _is_direct(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _DIRECT_HINTS)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    return _UNSAFE_NAME.sub("_", stem).strip(" .")[:40].rstrip(" .")


def _key(index: int, row: dict[str, str]) -> str:
    return f"{row['domain']}/{index:02d}-{_safe_stem(row['file_name'])}.pdf"


def fetch(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / "pdf").mkdir(exist_ok=True)
    for name in _META_FILES:
        status, body, _ = _get(_HF_FILE.format(name=name))
        if status != 200:
            print(f"{name}: HTTP {status}", file=sys.stderr)
            return 1
        (out / name).write_bytes(body)
    rows = _read_rows(out / "documents.csv")
    lines = ["index\tdomain\tfile_name\tstatus\tbytes"]
    for index, row in enumerate(rows, start=1):
        target = out / "pdf" / f"{index:02d}.pdf"
        status_text = "landing"
        size = 0
        if target.exists():
            size = target.stat().st_size
            status_text = "ok"
        elif _is_direct(row["url"]):
            status, body, _ = _get(row["url"])
            if status == 200 and body.startswith(b"%PDF-") and len(body) <= _MAX_PDF_BYTES:
                target.write_bytes(body)
                size = len(body)
                status_text = "ok"
            else:
                status_text = f"failed:{status}" if status != 200 else "not_pdf"
        lines.append(f"{index}\t{row['domain']}\t{row['file_name']}\t{status_text}\t{size}")
    (out / "fetch_report.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_missing(out, rows, lines[1:])
    counts = Counter(line.split("\t")[3].split(":")[0] for line in lines[1:])
    print(dict(counts))
    return 0


def _write_missing(out: Path, rows: list[dict[str, str]], report: list[str]) -> None:
    """받지 못했고 질문이 달린 문서의 목록 `missing.tsv`를 쓴다. `fetch_landing.py`와 사람이
    읽는다."""
    asked = Counter(
        row["target_file_name"].strip() for row in _read_rows(out / "rag_evaluation_result.csv")
    )
    lines = ["번호\t도메인\t질문수\t쪽수\t파일 이름(데이터셋)\t출처 주소\t자동 결과"]
    for line, row in zip(report, rows, strict=True):
        index, _, _, status, _ = line.split("\t")
        if status != "ok" and asked[row["file_name"]] > 0:
            cells = [f"{int(index):02d}", row["domain"], str(asked[row["file_name"]])]
            cells += [row["pages"], row["file_name"], row["url"], status]
            lines.append("\t".join(cells))
    (out / "missing.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _page_number(text: str) -> int | None:
    stripped = text.strip()
    return int(stripped) if stripped.isdigit() and int(stripped) >= 1 else None


def convert(out: Path, bundle: Path, exclude: frozenset[int]) -> int:
    documents = _read_rows(out / "documents.csv")
    questions = _read_rows(out / "rag_evaluation_result.csv")
    outside = sorted(index for index in exclude if not 1 <= index <= len(documents))
    if outside:
        print(f"--exclude 번호가 1~{len(documents)} 밖이다: {outside}", file=sys.stderr)
        return 1
    if bundle.exists() and any(bundle.iterdir()):
        # 이미 든 옛 PDF가 남아 `validate`가 "목록에 없는 파일"로 거부하는 것을 막는다.
        print(f"--bundle 폴더가 비어 있지 않다. 새 폴더를 주거나 비운다: {bundle}", file=sys.stderr)
        return 1
    today = datetime.now(tz=_KST).date().isoformat()
    kept: dict[str, tuple[int, dict[str, str], bytes]] = {}
    for index, row in enumerate(documents, start=1):
        path = out / "pdf" / f"{index:02d}.pdf"
        if path.exists() and index not in exclude:
            kept[row["file_name"]] = (index, row, path.read_bytes())
    excluded_names = {documents[index - 1]["file_name"] for index in exclude}
    pages = _pages_of(kept)
    (bundle / "documents").mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    keys: dict[str, str] = {}
    for file_name, (index, row, data) in kept.items():
        key = _key(index, row)
        target = bundle / "documents" / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        keys[file_name] = key
        entries.append(
            {
                "key": key,
                "title": row["file_name"],
                "publisher": f"출처 사이트(allganize 문서 목록의 url): {_host(row['url'])}",
                "source_url": row["url"],
                "license": "미확인(출처 사이트의 이용 조건. 커밋하지 않는 참고 측정용 사본)",
                "license_evidence": (
                    f"데이터셋 카드(license: mit)는 질문과 정답에 걸리고 PDF에는 걸리지 않는다."
                    f" PDF는 저장소에 커밋하지 않는다. 받은 날 {today}"
                ),
                "downloaded_at": today,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "updated_at": today,
            }
        )
    listed = {row["file_name"] for row in documents}
    evidence, queries, skipped = _questions(questions, keys, pages, listed, excluded_names)
    _write_json(bundle / "documents.json", entries)
    _write_lines(bundle / "evidence.jsonl", evidence)
    _write_lines(bundle / "queries-human.jsonl", queries)
    _write_json(
        bundle / "eval-set.json",
        {
            "format_version": "1.0.0",
            "name": "allganize-rag-ko",
            "documents": "documents.json",
            "evidence": "evidence.jsonl",
            "query_lists": [{"name": "human", "style": "question", "file": "queries-human.jsonl"}],
            "local_only": True,
        },
    )
    _write_json(bundle / "config.json", _CONFIG)
    report = {
        "dataset": DATASET,
        "revision": REVISION,
        "documents_total": len(documents),
        "documents_kept": len(kept),
        "excluded_documents": sorted(exclude),
        "questions_total": len(questions),
        "questions_kept": len(evidence),
        "questions_skipped": skipped,
        "kept_by_domain": dict(Counter(str(item["id"]).split("-")[0] for item in evidence)),
    }
    _write_json(bundle / "convert_report.json", report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


_CONFIG: Final = {
    "embedding_model": "BAAI/bge-m3",
    "embedding_dimensions": 1024,
    "reranker_model": "BAAI/bge-reranker-v2-m3",
    "chunking": {"strategy": "structure_first", "max_tokens": 512, "overlap_tokens": 64},
    "search_candidates": 50,
    "tei_version": "1.9.4",
    "judge_model": "claude-opus-5-5",
    "judge_prompt_version": "1",
}


def _host(url: str) -> str:
    matched = re.match(r"https?://([^/]+)", url)
    return matched.group(1) if matched else url


def _pages_of(kept: dict[str, tuple[int, dict[str, str], bytes]]) -> dict[str, int]:
    """문서 목록의 `pages` 칸을 쪽 수로 쓴다. 그 칸이 숫자가 아니면 상한을 두지 않는다."""
    result: dict[str, int] = {}
    for file_name, (_, row, _) in kept.items():
        count = _page_number(row["pages"])
        if count is not None:
            result[file_name] = count
    return result


def _questions(
    rows: list[dict[str, str]],
    keys: dict[str, str],
    pages: dict[str, int],
    listed: set[str],
    excluded: set[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    evidence: list[dict[str, object]] = []
    queries: list[dict[str, object]] = []
    skipped: Counter[str] = Counter()
    per_domain: Counter[str] = Counter()
    for row in rows:
        file_name = row["target_file_name"].strip()
        page = _page_number(row["target_page_no"])
        if file_name not in listed:
            skipped["document_not_listed"] += 1
            continue
        if file_name in excluded:
            skipped["document_excluded"] += 1
            continue
        if file_name not in keys:
            skipped["document_not_fetched"] += 1
            continue
        if page is None:
            skipped["page_missing"] += 1
            continue
        if file_name in pages and page > pages[file_name]:
            skipped["page_out_of_range"] += 1
            continue
        per_domain[row["domain"]] += 1
        item_id = f"{row['domain']}-{per_domain[row['domain']]:03d}"
        tag = _TAGS.get(row["context_type"].strip())
        evidence.append(
            {
                "id": item_id,
                "evidence": [{"kind": "page", "document": keys[file_name], "page": page}],
                "tags": [tag] if tag else [],
            }
        )
        queries.append({"evidence_id": item_id, "query": row["question"].strip()})
    return evidence, queries, dict(skipped)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_lines(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="allganize 데이터셋을 평가 세트 묶음으로 바꾼다")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch_parser = sub.add_parser("fetch")
    fetch_parser.add_argument("--out", type=Path, required=True)
    convert_parser = sub.add_parser("convert")
    convert_parser.add_argument("--out", type=Path, required=True)
    convert_parser.add_argument("--bundle", type=Path, required=True)
    convert_parser.add_argument("--exclude", type=int, nargs="*", default=[])
    args = parser.parse_args(argv)
    if args.command == "fetch":
        return fetch(args.out)
    return convert(args.out, args.bundle, frozenset(args.exclude))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
