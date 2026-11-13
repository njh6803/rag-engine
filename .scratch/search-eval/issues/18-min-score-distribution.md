# 18: 최소 점수: 리랭크 점수의 분포를 보이고 구현을 정한다

**What to build:** 공공 문서 묶음의 전체 실행 보고서의 `score_distribution`을 사용자에게 보이고, 사용자가 `search`의 `min_score`를 구현할지 정한다(스토리 27, ADR 0017). 승인되면 ADR 0017에 측정의 요약과 승인을 이력으로 더하고 같은 PR에서 최소 점수의 구현 티켓을 쓴다. 승인 전에는 구현 티켓이 놓이지 않는다(명세 "최소 점수"). 이 티켓에는 사용자의 판정을 기다리는 지점이 있다.

**Blocked by:** 14 (리랭크 기록)

**Status:** ready-for-agent

- [ ] 리랭크 기록으로 `run --through rerank`를 돌려 `score_distribution`(닿은 조각과 그렇지 않은 조각의 구간별 수, 문턱별 상위 5·10 적중률, 결과가 비는 질의의 비율, 남는 조각 수의 평균)을 표로 사용자에게 보이고 **멈춘다**.
- [ ] 승인되면 `docs/adr/0017-…`에 이력(측정의 요약과 승인, 사용자의 글)을 더한다. ADR 이력을 쓰기 전에 `domain-modeling` 스킬을 부른다(`.claude/rules/adr.md`). 같은 PR에서 다음 번호의 구현 티켓을 `.scratch/search-eval/issues/`에 to-tickets의 형식으로 쓴다. 그 티켓은 명세 최소 점수 절의 구현 모양(리랭크 뒤·`top_k` 앞에서 거르기, 지식베이스의 기본값보다 요청 인자가 이기는 것, 범위 밖 값의 `invalid_argument`, 숫자가 아닌 값을 MCP SDK의 입력 검증이 기존 인자의 타입 오류와 같은 모양으로 거부하는 것, 리랭커 없는 지식베이스의 `invalid_argument`, 빈 결과, 지식베이스 행의 널 허용 칸과 `RAG_DEFAULT_MIN_SCORE`, `SCHEMA_VERSION`을 올리지 않는 마이그레이션, 리랭커가 빈 채 기본값이 있으면 `migrate` 거부, 그런 행에서 `search_unavailable`)과 스토리 34~38, 계약 시험(inputSchema에 `min_score`, 결과의 `format_version` `1.1.0`)을 수용 기준으로 든다. 그 티켓은 원칙 VII의 판을 올리는 계약 변경이지만 기능의 첫 티켓이 아니다(ADR 0017이 둔 예외).
- [ ] 두 분포가 한 문턱으로 잘 갈리지 않거나 사용자가 구현하지 않기로 하면 ADR 0017 이력에 그 결과와 사용자의 판정만 적고 구현 티켓은 쓰지 않는다.
- [ ] `uv run python tools/plan_table.py`로 전체 계획을 다시 만든다.
- [ ] 검사 넷이 초록이다.
