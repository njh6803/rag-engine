"""vector-store-comparison.md에 N·O·P 절을 끼우고 근거 표기·열린 사실을 갱신한다.

실행: uv run --no-project python -I -X utf8 .scratch/core/probes/vector-store/splice_nop.py \\
    <doc.md> <sections_nop.md>

측정 스크립트가 아니라 비교 문서를 한 번 고친 편집 스크립트다. 2026-11-09에
`.scratch/core/design/vector-store-comparison.md`에 적용했고, 끼운 본문 `sections_nop.md`는 문서에
들어갔으므로 옮기지 않았다. 다시 돌리면 첫 assert(N 절이 이미 있음)에서 멈춘다. 문자열 상수의
`S1/`·`S2/` 경로는 적용 당시 문서의 글이다(그 뒤 문서의 스크립트 경로는
`.scratch/core/probes/vector-store/`로 바꿨다).
"""

import pathlib
import sys

doc_path = pathlib.Path(sys.argv[1])
sections = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
text = doc_path.read_text(encoding="utf-8")

ANCHOR = "## 가장 갈리는 차원 다섯(요약)\n"
assert text.count(ANCHOR) == 1 and "### N. 채택도" not in text
text = text.replace(ANCHOR, sections + ANCHOR)

OLD_S2 = "(`dl/` 원문, `probe/` 스크립트와 출력, `wheel/` 휠)"
NEW_S2 = (
    "(`dl/` 원문, `dl2/` N·O·P 절 원문(관리형 PostgreSQL 확장 표, "
    "Weaviate·Qdrant·Milvus·Meilisearch·ParadeDB 문서, 가격 페이지, 라이선스·블로그, "
    "GitHub·Docker Hub·pypistats JSON), `probe/` 스크립트와 출력, `wheel/` 휠)"
)
assert text.count(OLD_S2) == 1
text = text.replace(OLD_S2, NEW_S2)

OLD_SCRIPTS = "`S1/probe/hub_sizes.py`(지난 조사의 이미지 크기)."
NEW_SCRIPTS = (
    "`S1/probe/hub_sizes.py`(지난 조사의 이미지 크기). N·O·P 절(2026-11-09): "
    "`S2/probe/github_stats.py`(gh api로 별·포크·이슈·기여자·90일 커밋·릴리스·LICENSE 커밋 이력, "
    "출력 `github_stats.txt`), "
    "`S2/probe/pulls_and_pypistats.py`(Docker Hub `pull_count`, pypistats `recent`, "
    "출력 `pulls_and_pypistats.txt`), "
    "`S2/probe/fetch_raw5.py`·`fetch_list.py`(+`items6.txt`~`items9.txt`; `dl2/` 원문 내려받기), "
    "`S2/probe/pdf_text.py`(pypdf로 PDF 텍스트)."
)
assert text.count(OLD_SCRIPTS) == 1
text = text.replace(OLD_SCRIPTS, NEW_SCRIPTS)

OLD_OPEN_TAIL = (
    "10. 공식 pgvector+PGroonga 결합 이미지 부재 → 자체 이미지 유지 비용(릴리스마다 재빌드).\n"
)
NEW_OPEN_TAIL = OLD_OPEN_TAIL + (
    "11. **DB-Engines 벡터 순위 원문**을 받지 못했다(인증서 검증 오류 두 번). "
    "N-4의 점수는 제3자 블로그의 2026-03 옮김이다.\n"
    "12. **pg_search(ParadeDB)가 바깥으로 사용 통계를 보내는지.** 저장소의 `telemetry.rs`는 "
    "EXPLAIN 통계 코드이고, 이미지 환경 변수나 문서는 확인하지 못했다.\n"
    "13. **OpenSearch·Milvus·Chroma의 텔레메트리 기본값 원문**(Chroma 문서 404). "
    "결선에는 OpenSearch만 걸린다.\n"
    "14. **pgvector 수천만~억 단위 규모의 독립 사례**가 없다. "
    "있는 것은 판매자 벤치와 블로그뿐(O 표).\n"
    "15. **Elasticsearch 구독 등급표**는 PDF 텍스트 추출에서 열이 사라져 기능별 등급을 "
    "대조하지 못했다(결선 밖 참고).\n"
    "16. **Weaviate EE 범위가 앞으로 넓어질지**(2026-08 분리 뒤 석 달, 기능 셋). "
    "지금은 CE에 검색·분산·RBAC가 다 있으나 변경 전력이 생겼다(P-3).\n"
)
assert text.count(OLD_OPEN_TAIL) == 1
text = text.replace(OLD_OPEN_TAIL, NEW_OPEN_TAIL)

doc_path.write_text(text, encoding="utf-8")
# 표의 파이프 수 검사
bad = 0
lines = text.splitlines()
i = 0
while i < len(lines):
    if (
        lines[i].startswith("|")
        and i + 1 < len(lines)
        and set(lines[i + 1].replace("|", "").strip()) <= {"-", " ", ":"}
        and lines[i + 1].startswith("|")
    ):
        n = lines[i].count("|")
        j = i
        while j < len(lines) and lines[j].startswith("|"):
            if lines[j].count("|") != n:
                print(f"PIPE MISMATCH line {j + 1}: {lines[j].count('|')} vs {n}")
                bad += 1
            j += 1
        i = j
    else:
        i += 1
print(f"lines={len(lines)} pipe_mismatches={bad}")
