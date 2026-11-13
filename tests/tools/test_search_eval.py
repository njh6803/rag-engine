"""평가 도구 `tools/search_eval.py`의 `validate` 하위 명령(티켓 search-eval 02).

임시 폴더에 작은 묶음을 짓고 도구의 `main(argv)`를 부른다(선례 `tests/test_ingest_command.py`).
거부 사례마다 종료 코드 1과 표준 오류의 까닭을 함께 본다. 코드만 보면 엉뚱한 까닭의 실패가 기대와
맞아 초록이 된다(`CODING_STANDARDS.md`). 링크 사례는 그 플랫폼에서 권한 없이 만들 수 있는 폴더
링크로 짓고 건너뛰지 않는다.
"""

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.support.eval_bundle import (
    BODY_A,
    BODY_B,
    EVIDENCE,
    KB,
    QUERIES_HUMAN,
    document_entry,
    edit_json,
    make_folder_link,
    read_json,
    write_bundle,
    write_json,
    write_jsonl,
)

from rag_engine.domain.entities import JsonValue
from tools import search_eval

MAX_DOCUMENT_BYTES = 30 * KB * KB


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return write_bundle(tmp_path / "bundle")


def _validate(bundle: Path) -> int:
    return search_eval.main(["validate", str(bundle)])


def _rejected(bundle: Path, capsys: pytest.CaptureFixture[str], *reasons: str) -> str:
    """종료 코드 1로 거부하고, 표준 오류가 까닭마다 그 글을 든다. 표준 오류를 돌려준다.

    `capsys`의 버퍼는 한 번 읽으면 비므로, 더 볼 글이 있는 시험은 돌려받은 글로 본다.
    """
    assert _validate(bundle) == 1
    err = capsys.readouterr().err
    for reason in reasons:
        assert reason in err, err
    return err


def _documents(bundle: Path) -> list[JsonValue]:
    documents = read_json(bundle / "documents.json")
    assert isinstance(documents, list)
    return documents


def test_문제가_없는_묶음은_종료_코드_0이다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _validate(bundle) == 0

    assert "문제 없음" in capsys.readouterr().out


def test_같은_major의_다른_minor_판은_받는다(bundle: Path) -> None:
    edit_json(bundle / "eval-set.json", {"format_version": "1.4.0"})

    assert _validate(bundle) == 0


def test_틀린_판의_묶음은_거부한다(bundle: Path, capsys: pytest.CaptureFixture[str]) -> None:
    edit_json(bundle / "eval-set.json", {"format_version": "2.0.0"})

    _rejected(bundle, capsys, "eval-set.json", "판", "2.0.0")


def test_판_칸이_판_모양이_아니면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit_json(bundle / "eval-set.json", {"format_version": "일점영"})

    _rejected(bundle, capsys, "eval-set.json", "판")


def test_인자가_없으면_종료_코드_2다(capsys: pytest.CaptureFixture[str]) -> None:
    assert search_eval.main([]) == 2

    assert "validate" in capsys.readouterr().err


def test_묶음_폴더를_주지_않으면_종료_코드_2다() -> None:
    assert search_eval.main(["validate"]) == 2


def test_모르는_하위_명령은_종료_코드_2다() -> None:
    assert search_eval.main(["fly", "somewhere"]) == 2


def test_없는_묶음_폴더는_종료_코드_1이다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _rejected(tmp_path / "없음", capsys, "묶음 폴더가 없다")


def test_머리_파일이_없는_폴더는_거부한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "빈").mkdir()

    _rejected(tmp_path / "빈", capsys, "eval-set.json", "없다")


def test_JSON이_아닌_파일은_까닭과_함께_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (bundle / "config.json").write_text("{깨진", encoding="utf-8")

    _rejected(bundle, capsys, "config.json", "JSON")


def test_구성의_칸이_빠지면_빠진_칸의_이름을_알린다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit_json(bundle / "config.json", {"search_candidates": None})

    _rejected(bundle, capsys, "config.json", "search_candidates")


def test_문서_목록의_칸이_빠지면_빠진_칸의_이름을_알린다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    documents = _documents(bundle)
    first = documents[0]
    assert isinstance(first, dict)
    del first["license_evidence"]
    write_json(bundle / "documents.json", documents)

    _rejected(bundle, capsys, "documents.json", "license_evidence")


def test_문서_목록의_날짜_꼴이_틀리면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    documents = _documents(bundle)
    first = documents[0]
    assert isinstance(first, dict)
    first["updated_at"] = "2026-1-5"
    write_json(bundle / "documents.json", documents)

    _rejected(bundle, capsys, "documents.json", "updated_at")


def test_모르는_종류의_기대_근거는_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_jsonl(
        bundle / "evidence.jsonl",
        [{"id": "q1", "evidence": [{"kind": "video", "document": "a.docx"}], "tags": []}],
    )

    _rejected(bundle, capsys, "evidence.jsonl:1", "kind")


def test_질의_목록의_유형이_모르는_낱말이면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header = read_json(bundle / "eval-set.json")
    assert isinstance(header, dict)
    header["query_lists"] = [{"name": "human", "style": "sentence", "file": "queries-human.jsonl"}]
    write_json(bundle / "eval-set.json", header)

    _rejected(bundle, capsys, "eval-set.json", "style")


def test_질의의_evidence_id와_짝인_기대_근거가_없으면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_jsonl(bundle / "queries-human.jsonl", [{"evidence_id": "q9", "query": "질문"}])

    _rejected(bundle, capsys, "q9", "기대 근거가 없다")


def test_한_질의_목록_안의_같은_evidence_id는_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_jsonl(
        bundle / "queries-human.jsonl",
        [{"evidence_id": "q1", "query": "처음"}, {"evidence_id": "q1", "query": "다시"}],
    )

    _rejected(bundle, capsys, "human", "q1", "한 번만")


def test_모르는_유형_표지는_거부한다(bundle: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_jsonl(
        bundle / "evidence.jsonl",
        [
            {
                "id": "q1",
                "evidence": [{"kind": "page", "document": "a.docx", "page": 1}],
                "tags": ["chart"],
            },
            EVIDENCE[1],
        ],
    )

    _rejected(bundle, capsys, "chart", "유형 표지")


def test_오프셋이_없는_필터_시각은_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_jsonl(
        bundle / "queries-human.jsonl",
        [
            {
                "evidence_id": "q1",
                "query": "질문",
                "filter": {"updated_after": "2026-01-01T00:00:00"},
            }
        ],
    )

    _rejected(bundle, capsys, "queries-human.jsonl:1", "updated_after", "오프셋")


def test_읽을_수_없는_필터_시각은_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_jsonl(
        bundle / "queries-human.jsonl",
        [{"evidence_id": "q1", "query": "질문", "filter": {"updated_before": "내일"}}],
    )

    _rejected(bundle, capsys, "queries-human.jsonl:1", "updated_before")


def test_groups가_든_필터는_거부한다(bundle: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_jsonl(
        bundle / "queries-human.jsonl",
        [{"evidence_id": "q1", "query": "질문", "filter": {"groups": ["팀"]}}],
    )

    _rejected(bundle, capsys, "groups", "그룹 필터")


def test_기대_근거의_문서를_거르는_기간_필터는_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # a.docx의 갱신일은 2026-01-15이므로 2026-01-15 00:00 +09:00가 경계다.
    write_jsonl(
        bundle / "queries-human.jsonl",
        [
            {
                "evidence_id": "q1",
                "query": "질문",
                "filter": {"updated_before": "2026-01-15T00:00:00+09:00"},
            }
        ],
    )

    _rejected(bundle, capsys, "a.docx", "updated_before")


def test_문서의_날짜가_updated_after와_같으면_받는다(bundle: Path) -> None:
    write_jsonl(
        bundle / "queries-human.jsonl",
        [
            {
                "evidence_id": "q1",
                "query": "질문",
                "filter": {"updated_after": "2026-01-15T00:00:00+09:00"},
            }
        ],
    )

    assert _validate(bundle) == 0


def test_기대_근거가_목록에_없는_문서를_가리키면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_jsonl(
        bundle / "evidence.jsonl",
        [
            {
                "id": "q1",
                "evidence": [{"kind": "page", "document": "없는.pdf", "page": 1}],
                "tags": [],
            },
            EVIDENCE[1],
        ],
    )

    _rejected(bundle, capsys, "없는.pdf", "목록에 없는 문서")


def test_목록의_문서_파일이_없으면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (bundle / "documents" / "a.docx").unlink()

    _rejected(bundle, capsys, "a.docx", "파일이 없다")


def test_문서_파일의_해시가_목록과_다르면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (bundle / "documents" / "a.docx").write_bytes(BODY_A + b"!")

    _rejected(bundle, capsys, "a.docx", "해시")


def test_해시를_대문자로_적어도_글자_그대로_견주어_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    documents = _documents(bundle)
    first = documents[0]
    assert isinstance(first, dict)
    sha = first["sha256"]
    assert isinstance(sha, str)
    first["sha256"] = sha.upper()
    write_json(bundle / "documents.json", documents)

    _rejected(bundle, capsys, "a.docx", "해시")


def test_목록에_없는_파일이_documents에_있으면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (bundle / "documents" / "sub" / "끼어든.docx").write_bytes(b"x")

    _rejected(bundle, capsys, "sub/끼어든.docx", "목록에 없는 파일")


def test_문서_파일의_합이_30MB를_넘으면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _add_filler(bundle, MAX_DOCUMENT_BYTES - len(BODY_A) - len(BODY_B) + 1)

    _rejected(bundle, capsys, "30MB")


def test_문서_파일의_합이_정확히_30MB이면_받는다(bundle: Path) -> None:
    _add_filler(bundle, MAX_DOCUMENT_BYTES - len(BODY_A) - len(BODY_B))

    assert _validate(bundle) == 0


def _add_filler(bundle: Path, size: int) -> None:
    """`filler.bin`을 `size` 바이트로 지어 문서 목록에 더한다."""
    data = bytes(size)
    (bundle / "documents" / "filler.bin").write_bytes(data)
    documents = _documents(bundle)
    documents.append(document_entry("filler.bin", data))
    write_json(bundle / "documents.json", documents)


def test_문서_key가_절대_경로이면_거부한다(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "밖.docx"
    outside.write_bytes(BODY_A)
    _replace_first_key(bundle, str(outside))

    _rejected(bundle, capsys, "절대 경로")


def test_문서_key에_점점이_들면_거부한다(bundle: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (bundle / "밖.docx").write_bytes(BODY_A)
    _replace_first_key(bundle, "../밖.docx")

    _rejected(bundle, capsys, "..")


def test_문서_key에_점점이_들면_안으로_돌아오는_경로도_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `sub/../a.docx`는 풀면 `documents/a.docx`로 안에 머문다. 그래도 `..`가 든 경로다.
    _replace_first_key(bundle, "sub/../a.docx")

    _rejected(bundle, capsys, "..이 들었다")


def test_문서_key가_점점으로_documents_밖의_파일을_가리켜도_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `config.json`은 묶음 폴더 안이지만 문서 폴더 `documents/` 밖이다. 글자 판정이 먼저 거른다.
    _replace_first_key(bundle, "sub/../../config.json")

    _rejected(bundle, capsys, "..이 들었다")


def test_documents_안의_링크가_묶음_안의_documents_밖을_가리키면_그_문서_key는_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 링크를 푼 곳은 묶음 폴더 안(`records/`)이라 묶음 기준으로는 받을 경로다. 문서는 `documents/`
    # 기준으로 풀어 그 밖이면 거부한다.
    (bundle / "records").mkdir(exist_ok=True)
    (bundle / "records" / "x.docx").write_bytes(BODY_A)
    make_folder_link(bundle / "documents" / "linked", bundle / "records")
    _replace_first_key(bundle, "linked/x.docx")

    _rejected(bundle, capsys, "linked/x.docx: ", "링크를 풀면 documents/ 밖을 가리킨다")


def test_records_폴더를_읽을_수_없으면_트레이스백_없이_알린다(
    bundle: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (bundle / "records").mkdir(exist_ok=True)
    real_iterdir = Path.iterdir

    def deny(self: Path) -> Iterator[Path]:
        if self.name == "records":
            raise PermissionError(13, "권한 없음")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", deny)

    _rejected(bundle, capsys, "records: 폴더를 읽을 수 없다")


def test_documents_폴더를_읽을_수_없으면_문제_없음으로_넘어가지_않는다(
    bundle: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    real_scandir = os.scandir

    def deny(path: Path) -> Iterator[os.DirEntry[str]]:
        if path.name == "documents":
            raise PermissionError(13, "권한 없음")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", deny)

    _rejected(bundle, capsys, "documents: 폴더를 읽을 수 없다")


@pytest.mark.parametrize(
    ("key", "reason"),
    [
        ("CON", "윈도 예약 장치 이름"),
        ("nul.txt", "윈도 예약 장치 이름"),
        ("sub/COM1.pdf", "윈도 예약 장치 이름"),
        ("lpt9", "윈도 예약 장치 이름"),
        ("a.docx:stream", "':'가 들었다"),
    ],
)
def test_문서_key의_마디가_윈도_예약_장치_이름이거나_콜론이_들면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str], key: str, reason: str
) -> None:
    # 윈도에서 `CON`을 열면 읽기가 돌아오지 않는다. 그래서 운영체제와 무관하게 글자로 거른다.
    _replace_first_key(bundle, key)

    _rejected(bundle, capsys, f"{key}: ", reason)


def test_장치_이름으로_시작할_뿐인_마디는_예약_이름으로_거부하지_않는다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _replace_first_key(bundle, "console.docx")

    err = _rejected(bundle, capsys, "console.docx: 문서 파일이 없다")

    assert "예약" not in err


def test_config_json_자리에_폴더가_있으면_일반_파일이_아니라고_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (bundle / "config.json").unlink()
    (bundle / "config.json").mkdir()

    _rejected(bundle, capsys, "config.json: 일반 파일이 아니다")


def test_글귀에_줄_경계_문자가_들어도_그_줄은_하나로_읽는다(bundle: Path) -> None:
    # JSON 문자열 안의 U+2028·U+0085는 올바른 글이다. `splitlines()`는 그 줄을 쪼갠다.
    row: JsonValue = {
        "id": "q1",
        "evidence": [
            {
                "kind": "passage",
                "document": "a.docx",
                "passage": "앞" + chr(0x2028) + "뒤" + chr(0x85) + "끝",
            }
        ],
        "tags": [],
    }
    write_jsonl(bundle / "evidence.jsonl", [row, EVIDENCE[1]])

    assert _validate(bundle) == 0


def test_판_칸의_수가_4300자리를_넘어도_트레이스백_없이_판_꼴이_아니라고_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit_json(bundle / "eval-set.json", {"format_version": "1" * 4400 + ".0.0"})

    _rejected(bundle, capsys, "eval-set.json", "판 꼴이 아니다")


def _replace_first_key(bundle: Path, key: str) -> None:
    documents = _documents(bundle)
    first = documents[0]
    assert isinstance(first, dict)
    first["key"] = key
    write_json(bundle / "documents.json", documents)


def test_머리가_가리키는_파일이_절대_경로이면_거부한다(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "evidence-밖.jsonl"
    write_jsonl(outside, EVIDENCE)
    edit_json(bundle / "eval-set.json", {"evidence": str(outside)})

    _rejected(bundle, capsys, "evidence", "절대 경로")


def test_머리가_가리키는_파일에_점점이_들면_거부한다(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copy(bundle / "documents.json", bundle.parent / "documents-밖.json")
    edit_json(bundle / "eval-set.json", {"documents": "../documents-밖.json"})

    _rejected(bundle, capsys, "documents", "..")


def test_질의_목록_파일이_묶음_밖을_가리키면_거부한다(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_jsonl(tmp_path / "밖-질의.jsonl", QUERIES_HUMAN)
    header = read_json(bundle / "eval-set.json")
    assert isinstance(header, dict)
    header["query_lists"] = [{"name": "human", "style": "question", "file": "../밖-질의.jsonl"}]
    write_json(bundle / "eval-set.json", header)

    _rejected(bundle, capsys, "query_lists", "..")


def test_밖을_가리키는_링크_폴더_안의_문서는_거부한다(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `documents/sub`를 묶음 밖의 폴더로 가는 링크로 바꾼다. 안의 파일은 해시까지 맞다.
    outside = tmp_path / "밖"
    outside.mkdir()
    (outside / "b.pdf").write_bytes(BODY_B)
    shutil.rmtree(bundle / "documents" / "sub")
    make_folder_link(bundle / "documents" / "sub", outside)

    _rejected(bundle, capsys, "sub/b.pdf", "밖")


def test_documents_폴더가_밖을_가리키는_링크이면_거부한다(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    moved = tmp_path / "문서-밖"
    shutil.move(str(bundle / "documents"), moved)
    make_folder_link(bundle / "documents", moved)

    _rejected(bundle, capsys, "documents", "밖")


def test_records_폴더가_밖을_가리키는_링크이면_읽지_않는_파일이어도_거부한다(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 쓰는 하위 명령(07의 `index --records write`)이 이 폴더로 쓰는 길을 막기 위해 `validate`가
    # 같은 판정을 한다.
    outside = tmp_path / "기록-밖"
    outside.mkdir()
    make_folder_link(bundle / "records", outside)

    _rejected(bundle, capsys, "records", "밖")


def test_묶음_안을_가리키는_링크_폴더는_받는다(bundle: Path) -> None:
    # 거르는 것은 풀린 경로가 묶음 밖인 링크다. 안으로 가는 링크는 같은 파일을 가리킬 뿐이다.
    make_folder_link(bundle / "records", bundle / "documents")

    assert _validate(bundle) == 0


def test_링크_폴더_안의_문서가_목록에_없으면_링크를_따라_내려가지_않고_링크를_알린다(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "밖"
    outside.mkdir()
    (outside / "숨은.docx").write_bytes(b"x")
    make_folder_link(bundle / "documents" / "linked", outside)

    err = _rejected(bundle, capsys, "linked", "링크")
    assert "숨은.docx" not in err
