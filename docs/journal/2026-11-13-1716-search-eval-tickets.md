# search-eval 티켓 일지 · 2026-11-13

명세 일지(`docs/journal/2026-11-13-0453-search-eval-spec.md`)의 `## 다음`대로 기능 search-eval의 명세를 spec-reviewer로 검토하고, 지적과 사용자의 답을 명세와 ADR 0018에 반영한 뒤 `/to-tickets .scratch/search-eval/spec.md`로 티켓 열아홉으로 쪼갠 기록이다. next-session 지시문이 연 새 세션(Opus 5.5 / xhigh)이고 브랜치는 `docs/search-eval-tickets`(티켓 없는 면제 PR, "기능의 티켓")다. 세션 도중 컨텍스트가 한 번 압축되었다. 준비, 명세 검토, 물은 것과 답, 명세와 ADR에 반영한 것, 티켓, 산출물, 검증, 셀프 리뷰, PR 직전 리뷰, 커밋과 다시 돌린 것, 회고, 다음을 차례로 둔다.

기록 규칙은 앞 일지들과 같다. 결정을 내린 사용자 프롬프트는 `> 사용자:` 인용으로 원문 그대로 남기고, 선택 화면에서 고른 것은 질문과 함께 적되 따옴표 안에는 고른 라벨만 두고 설명은 `— 설명:`으로 글자 그대로 붙인다. 에이전트의 말은 옮기지 않는다. 질문과 답, 검토 보고, 정리 스킬의 출력은 세션 기록(jsonl)에서 스크립트로 꺼내 옮겼다.

## 준비

- 읽은 것: 지시문, `.claude/skills/to-tickets/SKILL.md`, 명세 `.scratch/search-eval/spec.md`, 명세 일지의 `## 다음`, ADR 0007·0017·0018·0019, `GLOSSARY.md`, `docs/agents/issue-tracker.md`, 기능 계획 `.scratch/search-eval/plan.md`, core 티켓 일지와 티켓 몇 개(형식의 선례), 프로브 README.
- 지시문(세션의 첫 메시지. 붙여 넣은 것이라 원문 그대로):

> 사용자: .claude/skills/to-tickets/SKILL.md 를 읽어 그대로 따른다. 이 세션을 연 저장소는 `C:\project\rag-engine`이고 작업 폴더가 그곳이 아니면 따르지 말고 알린다. 스킬의 인자는 이 줄의 '인자:' 뒤부터 메시지 끝까지다. 인자: .scratch/search-eval/spec.md
>
> 다음 작업: 기능 search-eval. 명세 `.scratch/search-eval/spec.md`를 검토하고 티켓으로 쪼갠다
> 다음 단계: 티켓
> 어디서: 새 세션. 주 체크아웃 미갱신이라 Skill 도구로 tidy-checkouts를 먼저 돌고(그 스킬이 사람에게 넘기는 것은 보고만 하고 답을 기다리지 않는다) 그 뒤 주 체크아웃에서 브랜치를 따지 않고 EnterWorktree(name은 브랜치의 마지막 토막)로 새 워크트리에 먼저 들어가 거기서 브랜치를 바꾼다
> 시작 프롬프트: /to-tickets .scratch/search-eval/spec.md
> 브랜치: docs/search-eval-tickets
> 모델: Opus 5.5 / xhigh
> 읽을 것: docs/journal/2026-11-13-0453-search-eval-spec.md의 "다음"
> 이어받을 상태: 명세 검토(spec-reviewer)는 아직 돌지 않았다. PR #34의 마지막 커밋 a79af09(봇 셋째 회차의 반영: validate의 기간 필터 판정, index --records write의 빈 데이터베이스 조건, 푸시에서 경로를 보지 않고 늘 평가)는 CodeRabbit이 한도에 걸려 리뷰하지 않았고 claude-review만 봤다(지적 없음). 일지 "다음"의 "티켓을 쓰기 전에 사용자에게 물을 것"은 빠른 게이트의 티켓을 쓰기 전에 묻는다. 원격 브랜치 남음: docs/search-eval (분류기 거부: Git Destructive)
> 확인할 선행 조건: 주 체크아웃 미갱신: 루트는 main. 병합은 이 워크트리 사본의 next-session merge.md(없으면 SKILL.md)의 "워크트리에서 병합할 때"를 Read로 열어 따른다
> 이번 요청 범위: PR과 병합까지

- 작업 폴더는 `C:\project\rag-engine`이었다. 지시문대로 주 체크아웃에서 `/tidy-checkouts`를 먼저 돌았다.
  - 루트: main인데 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 깨끗하지 않았다. 당기지 않았다. `origin/main`보다 커밋 11개 뒤다(주 체크아웃 미갱신).
  - 지웠다: `search-eval-design` 워크트리와 브랜치 `chore/session-model-fable-5-2`. 쉬는 세션의 `claude.exe` 하나가 쥐고 있어 `end-holders`로 끈 뒤 지웠다.
  - 사람에게 넘겼다: `14-reindex-version-switch`(병합된 PR의 머리와 브랜치 끝이 다르다).
  - 남겼다: `16-search-latency-probe-f30c20`과 `relaxed-grothendieck-e892b9`(앱의 표지), `code-review-transition-crossing`(잠금 pid가 살아 있다), `gate-pipe-read-status`(병합된 PR이 없다), `search-eval-spec`(그 브랜치의 세션이 돈다), 브랜치 `worktree-code-review-transition-crossing`과 `worktree-gate-pipe-read-status`(병합된 PR이 없고 `origin/main`에 없는 커밋이 있다).
  - 휴지통: `.venv` 넷(`03-dev-base-skills-docs`, `04-dev-branch-create`, `05-dev-release-pr-step`, `search-eval-design`)이 다른 프로세스(python.exe)가 올린 모듈 때문에 지워지지 않고 남았다. 다음 정리가 다시 본다.
- 그 뒤 `EnterWorktree`로 워크트리 `search-eval-tickets`에 들어가 `origin/dev`의 끝 3c70184에서 `docs/search-eval-tickets`를 땄다(`origin/HEAD`가 `origin/dev`를 가리킨다).

## 명세 검토

spec-reviewer 서브에이전트를 백그라운드로 돌렸다(기준 3c70184). 검토는 명세와 추적 파일을 고치지 않았고, 근거를 코드 읽기, 손으로 봄, 어림으로 갈라 적었다. 손으로 본 것은 임시 측정 둘이다(스크래치패드 `tei_repeat/`. 셀프 리뷰 뒤 `.scratch/search-eval/probes/repeat/`에 커밋했다). 하나는 테스트 PostgreSQL(pgvector 0.8.7)에 같은 무작위 64차원 벡터 3,000개를 같은 순서로 넣은 표 둘의 HNSW 색인이 질의 100개 가운데 35개에서 다른 상위 50을 낸 것이고, 다른 하나는 TEI CPU 이미지(`cpu-1.9.4`, `BAAI/bge-m3`, `--cpus=4 --max-batch-tokens 4096`)가 약 900자의 글 8개(검토는 약 470토큰이라 했으나 토큰 수는 재지 않았다)를 여섯 가지 묶음으로 다시 임베딩해 돌려받은 값이 모두 같았던 것이다(JSON으로 받은 수를 `==`로 견줬다). 리랭커를 다시 재던 도중 Docker Desktop이 내려갔고(그 시각 NVIDIA 관련 설치가 이벤트 로그에 있었다), 검토는 Docker를 다시 띄우지 않았다. 보고의 끝 셈은 blocker 1 · should-fix 13 · nit 8이다.

체크리스트 일곱의 판정: 계약 영향은 부분 충족(첫 티켓의 규칙, `SCHEMA_VERSION`), 원칙 위반은 없음(원칙 I의 취지인 "조용히 초록"이 될 자리 둘), ADR 충돌은 ADR 0018 Consequences의 한 문장, 경로 실재는 지적 없음, 비목표 침범은 없음, 테스트는 덮이지 않은 스토리(9, 14, 18, 27, 28, 29, 34~38)와 스토리 31에 거꾸로 된 시험 문장, 자리표시자는 전체 게이트의 "필요하면 잡의 조건으로 가른다" 하나다. 질문 둘에는 박히는 열린 결정이 넷(날짜를 시각으로 바꾸는 규칙, 내용 해시에 드는 칸, `validate`가 데이터베이스를 보는 방식, HNSW 후보의 흔들림)이고, 티켓 사이에서 계약이 조용히 무효가 되는 가장 큰 자리가 그 흔들림이라고 답했다.

지적과 반영. 명세의 권한 안의 것은 추천안으로 정해 반영했고, 사용자 승인이 필요한 것(ADR 이력, 기록의 변조를 막는 길, 내용 해시의 칸)은 아래 `## 물은 것과 답`에서 물었다.

- blocker(HNSW 후보의 흔들림): 개발 PC의 색인으로 GPU에서 만든 리랭크 기록이 CI가 새로 지은 색인의 후보 쌍을 덮지 못해, 전체 게이트가 코드와 무관하게 실패할 수 있다. 사용자가 평가만 정확 스캔으로 뽑는 길을 골랐다(질문 1).
- 날짜와 시각: 문서 목록의 `updated_at`을 `YYYY-MM-DD`로 두고 `adapters`의 함수 하나로 그날 00:00 `+09:00`으로 바꾸며, 필터 시각은 오프셋이 필수이고, 1.0.0에서 `groups`는 세트의 오류다.
- `write`가 1로 끝나면 주인 파일을 바이트 그대로 둔다.
- ADR 0018 Consequences의 "목록에서 빠진 경로의 변경은 전체 게이트에서야 잡힌다"에 이력과 포인터를 달았다(질문 4).
- 경로 판정 함수가 이벤트 셋을 받는다(PR은 diff, 푸시와 수동 실행은 늘 평가, diff를 못 읽으면 평가). 체크아웃의 역사 깊이를 적었다.
- 전체 게이트의 자리표시자를 코드를 읽은 답(수동 실행에서 `ticket`은 지나가고 `python`과 `image`는 끝까지 돈다)과 "가를 일이 생기면 잡의 조건(`if`)이 아니라 스텝의 조건으로 가른다"로 바꿨다.
- 내용 해시와 `compare`의 구성 비교에서 판정 칸 둘을 뺐다(질문 3).
- `validate --indexed`를 두어, 그 인자가 있으면 모든 문서가 색인되어 있어야 하고 글귀를 본문에서 본다. 데이터베이스가 있는지로 가르면 글귀 검사가 조용히 빠지기 때문이다.
- 판정의 시험을 둘로 나눴다(설정도 파일도 없으면 `null`, 설정이 없어도 파일이 있으면 숫자). 스토리 31과 맞춘 것이다.
- 덮이지 않은 스토리와 판정은 받는 티켓의 수용 기준으로 넘긴다는 `[정함]` 항목을 더했다. 판이 바뀌는 시험의 걸이는 그 티켓이 정한다.
- 첫 티켓은 포트 둘이고, `operations.md`는 게이트 티켓이 판 patch와 함께 고치는 예외로 두고 까닭을 적었다.
- CPU에서 다시 계산한 임베딩의 값이 같았다는 것을 "손으로 봤다"로 명세에 적었다. 장치 사이의 차와 리랭커를 프로브로 재는 일은 14가 받는다. 검토가 쓴 두 스크립트는 셀프 리뷰 뒤 `.scratch/search-eval/probes/repeat/`에 커밋했다(아래 `## 셀프 리뷰`).
- 기록의 변조를 묻는 때: 검토는 run·compare 티켓을 쓰기 전에 물으라고 했다. 이 세션은 티켓을 하나도 쓰기 전에 물었다(질문 2).
- 도구가 제품의 설정 객체를 지을 때 환경과 `.env`를 읽지 않게 하고, `.env`의 `RAG_PARSE_MAX_PAGES=1` 시험을 더했다.
- nit: 자리와 층의 `[넘겨받음]`을 ADR 0018의 말(채점, 지표, 보고서)에 맞추고 나머지를 `[정함]`으로 갈랐다. CI 게이트의 `[넘겨받음]` 끝에 푸시를 더한 이력을 가리키는 문장을 붙였다. `run`의 질의 임베딩은 `RAG_EVAL_EMBEDDING_URL`로 한다. Testing Decisions에 허용하는 관찰(alembic 판 표가 없음, 관리 유스케이스로 읽은 값, 파일 바이트)을 적었다. 최소 점수 마이그레이션이 `SCHEMA_VERSION`을 올리지 않는다(마이그레이션 0002가 선례). 수동 실행은 dev가 아닌 브랜치에서 띄운다(concurrency 그룹). `eval-set.json`의 판이 덮는 범위와 `records.json`의 판을 갈라 적었다. junction과 심볼릭 링크 시험을 플랫폼마다 skip하지 않게 짓는 것은 02의 수용 기준으로 넘겼다.

검토가 확인하지 못했다고 적은 것과 간 곳.

- 리랭커를 다시 계산한 값이 같은지, CPU와 GPU 사이의 차: 14의 값의 차 프로브.
- 실제 bge-m3 벡터에서 HNSW 상위 50이 흔들리는 크기: 정확 스캔을 골라 게이트의 숫자에는 들지 않는다. 필터 질의의 HNSW 부족 비율(06)이 그 몫을 따로 본다.
- 개발 PC와 CI 러너의 CPU 사이에 임베딩 값이 같은지: 재는 티켓이 없다. 11의 흔들림 측정은 `read` 모드라 기록된 값을 다시 계산하지 않고, 14는 개발 PC에서만 잰다. 한계로 남는 몫은 `read`가 기록에 없는 글을 상한 안에서 CI에서 계산해 기록의 값과 섞을 때의 차다(처음에는 11과 14가 함께 본다고 적었는데, 셀프 리뷰 표준 축이 짚어 고쳤다).
- 같은 SHA에서 수동 실행의 `verify`가 빨갛게 남을 때 PR의 필수 검사가 그것을 보는지: 11이 수동 실행을 실제로 띄워 확인한다.
- GitHub 표준 러너의 메모리: 11이 TEI 4096이 뜨는지 실제 실행으로 본다.

## 물은 것과 답

명세 검토를 본 뒤 사용자 승인이 필요한 넷을 한 화면으로 물었다. 넷 다 추천안을 골랐다. 일지 `## 다음`은 기록의 변조를 "빠른 게이트의 티켓을 쓰기 전에" 물으라고 했는데, 검토의 지적대로 그 답이 보고서 형식과 `compare`를 바꾸므로 티켓을 하나도 쓰기 전에 물었다.

- 질문 1(글 그대로): search-eval 명세 검토에서 나온 blocker입니다. PostgreSQL의 HNSW 색인은 지을 때마다 벡터 후보 상위 50이 조금씩 달라질 수 있습니다(검토가 무작위 벡터 3,000개로 손으로 본 결과, 질의 100개 가운데 35개의 상위 50이 달랐습니다). 그러면 개발 PC에서 GPU로 만든 리랭크 기록에 CI가 새로 지은 색인의 후보 쌍이 빠져서, 전체 게이트가 코드 변경과 무관하게 실패할 수 있습니다. 어떻게 막을까요? (선택지 3: 평가만 정확 스캔, CI가 빠진 쌍만 CPU 계산, 리랭크 기록을 넓게 만든다)

> 사용자: "평가만 정확 스캔 (Recommended)" — 설명: 평가의 진단용 검색만 HNSW 색인을 끄고 정확 스캔으로 후보를 뽑습니다. SQL 글은 같고 실행 계획만 다릅니다. 실행마다 후보가 같아서 리랭크 기록이 늘 맞고 빠른 게이트의 흔들림도 줄어듭니다. 대신 HNSW 근사로 잃는 몫은 숫자에 들지 않고, 필터 질의의 후보 부족 비율만 HNSW 계획으로 따로 잽니다.

- 질문 2(글 그대로. 여럿 고를 수 있었다): CI는 저장소에 커밋된 추론 기록(임베딩 벡터, 리랭크 점수)을 다시 계산하지 않아서 한계가 둘 남습니다. 첫째, 누가 기록 파일을 손으로 고치면 게이트가 알아채지 못합니다. 둘째, TEI 어댑터가 서버 응답을 다루는 코드가 바뀌어도 기록에 가려 숫자에 드러나지 않습니다. 어떤 장치를 둘까요? 여럿 고를 수 있습니다. 아무것도 두지 않으려면 Other에 그렇게 적어 주세요. (선택지 4: 기록 해시 승인, CI 임베딩 표본 재계산, write 때 표본 대조, CI 리랭커 표본 재계산)

> 사용자: "기록 해시 승인 (Recommended)" — 설명: 보고서에 기록 파일마다 해시를 싣고, compare가 기준 보고서와 해시가 다르면 기준 갱신처럼 사용자 승인을 받게 합니다. 변조를 막고 CI 시간은 늘지 않습니다. 기록을 다시 만드는 PR(청킹·모델 변경, 출시 전 리랭크 기록 맞추기)마다 승인이 하나 늘고, 응답 쪽 회귀는 막지 못합니다.

- 질문 3(글 그대로): search-eval 명세는 묶음의 내용 해시와 compare의 구성 비교에 config.json 전체를 넣습니다. 그러면 검색과 무관한 판정 모델(judge_model)이나 판정 지시문의 판(judge_prompt_version)을 바꾸기만 해도 기준 보고서 둘이 모두 거부되어, 사용자 승인과 전체 게이트의 수동 실행이 필요해집니다. 어떻게 둘까요? (선택지 2: judge 칸을 해시에서 뺀다, 그대로 두고 처음부터 채운다)

> 사용자: "judge 칸을 해시에서 뺀다 (Recommended)" — 설명: 내용 해시와 구성 비교에서 judge_model과 judge_prompt_version을 뺍니다. LLM 판정 숫자는 게이트가 보지 않는 참고값이라 기준 보고서를 묶을 까닭이 없습니다.

- 질문 4(글 그대로): search-eval 명세가 PR #34의 마지막 커밋에서 'dev·main 푸시에서는 바뀐 경로를 보지 않고 빠른 게이트를 늘 돌린다'로 바뀌면서, ADR 0018 Consequences의 문장 '목록에서 빠진 경로의 변경은 전체 게이트에서야 잡힌다'가 사실과 달라졌습니다. 이제는 병합 뒤 푸시의 빠른 게이트가 잡습니다. ADR 0018에 이력 한 줄과 그 문장의 포인터를 더해도 될까요? (선택지 2: 이력과 포인터 추가, 더하지 않는다)

> 사용자: "이력과 포인터 추가 (Recommended)" — 설명: ADR 0018에 2026-11-13 이력 하나(푸시에서는 경로를 보지 않고 늘 평가한다)를 더하고, 본문 문장 끝에 '(바뀜: 이력 …)' 포인터를 답니다. 결정 자체는 명세가 이미 정했고 ADR을 사실에 맞추는 일입니다.

`domain-modeling` 스킬을 부른 뒤 ADR 0018에 이력 둘을 더했다. 질문 4의 답이 승인한 것은 푸시 이력 하나다. 정확 스캔과 기록 해시의 이력은 질문 1·2의 결정을 옮긴 것이지만 ADR 초안을 보이지 않았고, 셀프 리뷰 명세 축이 이를 짚어 초안을 보이고 따로 물었고, 사용자가 이대로 승인했다(아래 `## 셀프 리뷰`의 `### 이력 초안의 승인`). 용어집은 고칠 말이 없었다("정확 스캔"은 명세와 ADR에서 풀어 쓰는 말이고 용어집의 다른 말과 부딪히지 않는다).

## 명세와 ADR에 반영한 것

- ADR 0018: 이력 `### 2026-11-13 평가는 후보를 정확 스캔으로 뽑고, 추론 기록의 해시가 바뀌면 승인을 받는다`(검토가 손으로 본 HNSW 흔들림, 세 길 가운데 첫째, 기록 해시의 승인, 고르지 않은 셋, 응답 쪽 한계)와 `### 2026-11-13 푸시에서는 바뀐 경로를 보지 않고 빠른 게이트를 늘 돌린다`(concurrency의 취소, 푸시와 수동 실행은 늘 평가). 본문 포인터는 단계별 측정 항목의 "같은 SQL 뼈대"와 Consequences의 "전체 게이트에서야 잡힌다" 둘이다.
- 명세: 위 `## 명세 검토`의 반영 전부를 실었다. 머리의 근거 줄에 이 세션과 ADR 0018 이력 둘을 적고, 표시 수를 `[넘겨받음]` 17, `[사용자 선택]` 10, `[정함]` 82, `[이력]` 3, `[거절]` 8로 고쳤다(본문 항목 머리를 `grep -o`로 다시 셌다). 새 `[사용자 선택]` 셋은 정확 스캔, 판정 칸을 뺀 해시, 기록 해시의 승인이다.
- 티켓을 쓰며 고친 명세의 사실 문장 셋: NVIDIA 드라이버가 같은 날 621.24로 올랐다는 것(이 세션이 `nvidia-smi`로 손으로 봤다)을 "전체 게이트와 리랭커" 절과 Further Notes 두 곳에 적었고, Further Notes의 변조 문단 첫머리가 현재형으로 "게이트가 보지 못한다"라고 남아 있던 것을 명세를 처음 쓸 때의 사실로 고쳤다(그 문단이 "전체 게이트와 리랭커" 절에서 가리키던, 기록만 맞추는 커밋에는 승인이 필요 없다는 문장은 이 세션이 지웠다).

## 티켓

분해안 열아홉을 보여 주고 물었다.

- 질문(글 그대로): search-eval 티켓 분해안 19개(01 포트 둘 → 02 형식과 validate → 03 index → 04 빠른 실행 → 05 전체 실행 → 06 놓친 까닭·inspect → 07 추론 기록 → 08 compare, 09 문서(03 뒤) → 10 질문과 기록 → 11 빠른 게이트, 12 판정기 → 13 첫 판정 실행, 14 GPU 리랭크 기록 → 15 전체 게이트, 16 리랭커 없는 실험, 17 리랭커 켬·끔 실험, 18 최소 점수 분포, 19 공개 데이터셋)를 이대로 .scratch/search-eval/issues/에 티켓 파일로 쓸까요? (선택지 3: 이대로 승인, 더 굵게 합친다, 더 잘게 쪼갠다)

> 사용자: "이대로 승인 (Recommended)" — 설명: 19개를 01~19 파일로 씁니다. 프론티어는 01 하나이고, 09(문서)는 03 뒤에 04~08과 나란히 돌 수 있습니다. 최소 점수의 구현 티켓은 18이 승인을 받은 뒤 같은 PR에서 씁니다.

`.scratch/search-eval/issues/`에 열아홉을 썼다(모두 ready-for-agent). 프론티어는 01 하나다.

| 번호 | 티켓 | Blocked by | 멈추는 지점 |
|---|---|---|---|
| 01 | 포트 둘: `diagnose_candidates`와 `RelevanceJudge` | 없음 | |
| 02 | 묶음 형식과 `validate`의 파일 검사 | 01 | |
| 03 | `index`와 `validate --indexed`, `compose.eval.yml` | 02 | |
| 04 | 빠른 실행: `run --through fused`와 보고서 | 01, 03 | |
| 05 | 전체 실행: 리랭크 뒤 줄과 `score_distribution` | 04 | |
| 06 | 놓친 까닭과 나눠 본 숫자, `inspect`, `--config` | 05 | |
| 07 | 추론 기록과 요청 지문 | 05 | |
| 08 | `compare` | 07 | |
| 09 | 공공 문서 묶음의 문서 | 03 | 후보 목록의 확정 |
| 10 | 질문과 기대 근거, 임베딩 기록 | 07, 09 | 질문의 검수 |
| 11 | 빠른 게이트 | 08, 10 | 첫 기준 보고서, 흔들림, 15분 |
| 12 | Claude 판정기와 `judge` | 05 | 실제 API 한 번의 비용 승인, ADR 0007 이력의 가름 |
| 13 | 첫 판정 실행과 사람 표본 | 06, 10, 11, 12 | 비용 승인, 사람의 가름, 놓친 까닭의 확인, LLM 보강의 결정 |
| 14 | GPU 리랭크 기록과 값의 차 | 10 | 값의 차 문턱, 2시간 |
| 15 | 전체 게이트 | 11, 14 | 첫 `baseline-full.json` |
| 16 | 리랭커 없는 설정 실험 | 06, 11 | 기본값의 승인 |
| 17 | 리랭커 켬·끔 실험 | 14 | 리랭커 기본의 선택 |
| 18 | 최소 점수의 분포 | 14 | 구현의 승인 |
| 19 | 공개 데이터셋의 참고 측정 | 06, 07 | 이용 조건 |

- 첫 티켓이 계약(포트 둘)이고 01을 뺀 모든 티켓을 사슬로 막는다(`docs/agents/issue-tracker.md`의 계약 규칙, ADR 0007 Consequences). 헌법 파일 `operations.md`를 고치는 11과 계약을 바꾸는 최소 점수의 구현 티켓은 명세 Further Notes가 적은 예외다.
- 값을 내는 쪽과 대 보는 쪽을 한 티켓에 묶었다. 날짜를 시각으로 바꾸는 함수와 경로 판정은 02가 짓고 03, 07, 08, 12가 쓴다. 요청 지문은 TEI 어댑터의 한 자리와 `validate`의 기록 검사를 07 하나에 두었다. 기록 형식(`records.json`의 모든 칸)이 기록을 처음 커밋하는 10보다 앞이다. `config.json`의 모든 칸은 09가 처음부터 커밋한다.
- 명세의 시험 목록(Testing Decisions)과 "덮는 스토리와 판정"의 사례마다 받는 티켓을 정해 수용 기준에 옮겼다. 시험 문장을 옮길 때 지금 이음매로 잴 수 있는지 봤다(to-tickets 5단계). EXPLAIN 시험은 어댑터가 시험용으로 계획을 글로 내는 메서드(`explain_search`, `tests/adapters/test_vector_index_chunks.py`)가 선례이고, 스텁의 요청 횟수 시험은 TEI 스텁의 `requests`와 `count`가 이음매다. 판이 바뀌는 시험의 걸이는 지금 없어 04가 정하고 그 방법을 티켓의 `## Comments`에 적게 했다. HNSW가 후보를 모자라게 내는 경우는 결정적으로 만들기 어려워, 06은 정확 스캔도 후보를 채우지 못하는 몫이 비율에 들지 않는 것을 보게 했다.
- 14의 선행 조건이던 드라이버 갱신은 이미 끝나(621.24), 14는 명세 세션의 우회 없이 GPU 이미지가 뜨는지를 첫 수용 기준으로 본다. 15는 출시 PR 앞의 맞추는 절차를 `next-session` `merge.md`의 "출시 PR" 절에 적는다.
- 티켓에 적은 경로는 규칙 문서, ADR, 테스트 선례, 명세가 정한 자리(`tools/search_eval.py`, `evals/`, `compose.eval.yml`, `.github/workflows/ci.yml`, 프로브 폴더)다. 처음 쓴 02와 12에 선례로 든 `src/` 경로 셋은 이름으로 바꿨다(to-tickets의 경로 규칙).

## 산출물

- `.scratch/search-eval/issues/01`~`19` 신설.
- `.scratch/search-eval/spec.md`: 위 `## 명세와 ADR에 반영한 것`.
- `docs/adr/0018-search-evaluation-in-app-and-baseline-gate.md`: 이력 둘과 본문 포인터 셋(게이트 문장의 포인터는 셀프 리뷰에서 더했다).
- `.scratch/search-eval/probes/repeat/` 신설(명세 검토의 스크립트 둘과 출력 둘), `.scratch/search-eval/probes/README.md`에 행 둘(셀프 리뷰에서 더했다).
- 이 일지.

## 검증

2026-11-13 셀프 리뷰 전, 브랜치 `docs/search-eval-tickets`에서 손으로 쳤다.

- `uv run python tools/plan_table.py` 0, `--check` 0. `.scratch/plan.md`는 바뀌지 않았다(티켓이 생긴 것만으로는 todo다).
- 바뀐 md 스물둘에 `uv run python tools/check_md_tables.py` 0, `uv run python tools/check_line_separators.py` 0, `uv run python tools/check_adr_pointers.py` 0.
- `uv run python tools/check_quotes.py --all-lines`(같은 스물둘)는 경고 하나였다. 이 일지가 이 세션이 명세에서 지운 문장을 따옴표로 들었는데 저장소에 없는 문장이라, 따옴표를 떼고 풀어 썼다. 다시 돌려 경고가 없었다.
- `uv run ruff check .` 0, `uv run ruff format --check .` 0(564 파일). 검사 러너 `uv run python tools/run_checks.py`: 열 검사(test-db, zizmor, check-ticket, lint-imports, check-instructions, check-type-escapes, pyright, pyright-linux, run-hooks, pytest 361.1초) 모두 Passed. 출력을 `tail`로 줄여 종료 코드는 파이프의 것이라, 판정은 Passed 줄 열로 했다.
- `uv run python tools/sibling_overlap.py` 0: 형제 origin/dev 11313d8과 열린 PR #37, 형제의 가장 높은 헌법 판 1.3.1, 이 브랜치의 새 번호 없음, 번호 겹침 없음, 함께 고친 파일 없음.
- 옛 말의 잔존: 색인된 데이터베이스가 있을 때 글귀를 본다는 옛 조건, 기록만 맞추는 커밋에는 승인이 필요 없다는 문장, 다시 `validate`를 색인된 데이터베이스로 돈다는 옛 차례, 드라이버 560.94를 현재형으로 적은 문장이 명세·ADR·티켓에 0이다(이 일지의 설명 자리만 남았다).
- Docker가 다시 떠 있어, 명세 검토가 남긴 컨테이너 `spec-review-tei-repeat-rerank`와 이미지 `alpine:latest`를 지웠다.

## 셀프 리뷰

`code-review` 스킬로 두 축을 나란히 돌렸다. 범위는 기준 3c70184, 바뀐 추적 파일 둘(명세, ADR 0018), 미추적 스물(티켓 열아홉, 이 일지), 커밋 0개다. 표준 축은 sonnet·high, 명세 축은 이 세션의 모델이다. 명세 출처는 `.scratch/search-eval/spec.md`와 사용자의 답 다섯(위 `## 물은 것과 답`과 `## 티켓`)이다.

### 표준 축(원문)

> 표준 축 리뷰 (문서만 변경, 코드 없음). 고치지 않고 보고만 한다. Critical·Major 없음. Minor 6, Nit 5.
>
> **Minor**
> 1. `.scratch/search-eval/spec.md` 127행 `[정함]`은 "내용 해시는 머리, 구성, … 파일의 바이트로 계산한다"고 적는다. 바로 아래 128행 `[사용자 선택]`(이번 변경)은 구성이 "파일의 바이트가 아니라" 판정 칸 둘을 뺀 JSON으로 들어간다고 적는다. 계약을 바꿨는데 옛 문장이 현재형으로 남았다. 티켓 04·08은 새 쪽을 따른다.
> 2. spec 173행(전체 게이트와 리랭커)에 "설치된 드라이버가 … 낡은 것으로 본다. 드라이버를 올리는 일은 사용자가 한다. 그 티켓은 드라이버가 오른 뒤에 집고"가 현재형으로 남았다. 같은 날 621.24로 올랐다는 괄호는 더했지만 이 문장들은 그대로다. 237행은 고쳤으나 173행은 놓쳤다.
> 3. 명세 시험 문장 가운데 받는 티켓이 없는 것이 있다.
>    - "`index`가 목록과 해시가 다른 문서 파일이 있으면 `--records write`에서도 기록 파일을 쓰지 않고 1": 03에는 `--records`가 없고 07의 시험 목록에도 없다.
>    - `run`·`judge`·`inspect`가 데이터베이스 판정(03)을 지난다는 기준은 04·06·12에 있으나 그 시험은 없다. 명세의 시험 목록은 `index`·`run`·`judge`를 든다.
> 4. 일지 61행은 "CI 러너와 개발 PC의 CPU 사이 임베딩 값이 같은지"를 "11의 흔들림 측정과 14의 프로브가 함께 본다"고 적는다. 티켓에는 그런 기준이 없다. 11의 흔들림은 `read` 모드라 기록된 임베딩을 다시 계산하지 않고, 14는 개발 PC에서만 잰다.
> 5. 티켓 11이 든 `docs/constitution/history.md`는 이 트리와 `origin/dev`에 없다. `tools/check_ticket.py`와 그 시험은 이 이름을 안다. 헌법 판 patch를 어디에 적는지 확인이 필요하다.
> 6. spec 238행(변경 밖)은 import 금지 목록과 `CLAUDE.md` "열여섯"을 "판정기 포트를 넣는 티켓"이 고친다고 적는다. 티켓에서는 포트가 01이고 SDK와 pyproject·`CLAUDE.md` 수정은 12다. 12의 `anthropic` 의존성 추가는 일관된 쪽이므로 명세 문장을 맞추면 된다.
> 7. 근거 규칙(`docs/agents/issue-tracker.md` 26행: 손으로 본 것은 "그 명령과 함께"). HNSW 35/100과 CPU 임베딩 비트 일치는 "임시 스크립트로 손으로 봤다"고만 적었고 명령이 없다. 스크립트는 스크래치패드(일지의 `tei_repeat/`)에 있다. 결정(blocker)을 떠받치는 근거라 명령이나 프로브 여부를 적는 편이 낫다. 621.24는 `nvidia-smi`를 밝혀 괜찮다.
>
> **Nit**
> - 일지 46행의 따옴표 인용 "가를 일이 생기면 스텝의 조건으로"는 글자 그대로가 아니다. 명세는 "가를 일이 생기면 잡의 조건(`if`)이 아니라 스텝의 조건으로"다.
> - 일지 표의 12행 멈추는 지점에 ADR 0007 이력 질문(티켓 12 수용 기준)이 빠졌다.
> - 일지 126행은 경로 판정을 쓰는 티켓을 "03, 07, 12"라 적지만 08도 기준 보고서 읽기에 쓴다.
> - 티켓 01의 "메모리 안 가짜 `VectorIndex`가 있으면"은 허공이다. 저장소에 그런 가짜는 없다(`class .*VectorIndex`는 어댑터와 포트뿐).
> - 명세 `[이력]` 수 3은 그대로인데 ADR 0018에 이력이 둘 늘었다. 새 이력은 `[사용자 선택]` 항목과 머리 근거 줄이 가리킨다. 표시 정의("`[이력]`은 ADR에 이력을 더한 것")와는 어긋난다.
>
> **smell baseline**
> - Shotgun Surgery(경미): 푸시·수동 실행 항상 평가 규칙이 spec 3곳(CI 게이트 `[넘겨받음]`, 경로 목록, Testing)과 티켓 11에 같은 문장으로 퍼져 있다. 다음에 바뀌면 다시 다 고쳐야 한다.
> - Duplicated Code: 티켓 07·08·12의 시험 문장이 명세 Testing Decisions 문장을 그대로 옮긴 것이라, 명세가 바뀌면 둘이 갈라진다.
>
> **확인해서 이상 없음**
> - 표시 수: `[넘겨받음]` 17, `[사용자 선택]` 10, `[정함]` 82, `[이력]` 3, `[거절]` 8이 항목 머리 수와 일치한다. 머리 정의 줄 외에 본문 중간에 표시가 따로 있지도 않다.
> - ADR 0018 포인터 둘: 새 `###` 제목과 글자 그대로 같다. `tools/check_adr_pointers.py` 종료 0. 이력이 인용한 일지 경로는 실제 파일명과 같다.
> - 일지 표의 번호와 Blocked by: 19개 티켓 파일 머리·`Blocked by`와 전부 일치한다.
> - 티켓이 든 경로: 요청한 목록은 모두 실재한다(`explain_search`, `tei_stub.py`, `tei_server.py`, `docx_files.py`, `merge.md` "출시 PR" 절, `probe_out.txt`, `gpu_turing_start_server_log.txt` 포함). 구현 파일 `src/` 경로는 없고, 11의 `src/`는 명세가 정한 경로 목록이다.
> - 명세 절 이름: 따옴표 인용한 절 이름은 명세에 그대로 있다. 스토리 번호도 맞는다.
> - 옛 결정 잔존: 승인이 필요 없다는 문장, 데이터베이스가 있을 때 글귀를 본다는 문장, 옛 `validate` 차례는 0이다. 승인 불필요 취지는 명세 243행에만 "처음에는 그랬다"는 기록 문장으로 남았고, 드라이버 잔존은 위 2번이다.
> - GLOSSARY `_Avoid_`: 새 문장에서 걸린 말이 없다.

### 명세 축(원문)

> ## 명세 축 리뷰: docs/search-eval-tickets (3c70184 이후의 작업 트리, 커밋 없음)
>
> **Major**
>
> 1. **(c) ADR 0018에 이력이 사용자가 승인한 것보다 하나 더 붙었다.** 질문 4의 답은 "ADR 0018에 2026-11-13 이력 하나(푸시에서는 경로를 보지 않고 늘 평가한다)를 더하고"였다. 그런데 diff에는 이력이 둘이다. 하나 더 붙은 것은 `### 2026-11-13 평가는 후보를 정확 스캔으로 뽑고, 추론 기록의 해시가 바뀌면 승인을 받는다`와, 단계별 측정 항목에 단 그 포인터다. 질문 1·2는 결정만 물었고 ADR 초안은 보이지 않았다(CLAUDE.md 작업 규약 5). 일지의 "답대로 … 이력 둘을 더했다"도 답과 맞지 않는다. 병합 전에 초안을 보이고 승인을 받아야 한다(merge.md 4).
> 2. **(a) 명세의 결정 둘을 받는 티켓이 없다.** "사람 판정의 초벌은 Claude Code 세션이 하고 사용자가 확인한다"와 "색인 시점의 LLM 보강을 더할지는 `no_context`의 비율을 본 뒤 사용자가 정한다"(놓친 까닭 절)다. 06은 `miss-review.jsonl`을 세기만 한다. 공공 문서 묶음의 초벌 판정을 쓰는 티켓도, 사용자에게 묻는 티켓도 없어서 `human_causes`는 계속 빈다.
>
> **Minor**
>
> 3. **(a) 넘긴 것 가운데 빠진 것.**
>    - 명세 일지 `## 다음`의 "취소된 실행이 `verify`를 어떻게 끝내는지"가 11에 없다.
>    - 명세는 "`index`, `run`, `judge`는 `--config`로"라고 하는데, 06은 `index`와 `run`에만 두고 12에는 없다.
> 4. **(a) 시험 문장의 일부가 빠졌다.**
>    - "`index`·`run`·`judge`가 묶음 밖의 문서가 든 데이터베이스…"에서 `run`(04)과 `judge`(12)는 수용 기준만 있고 시험이 없다. `judge` 쪽은 원칙 V를 지키는 시험이다.
>    - "키워드만 단계에서 놓친 것으로 세어지고"를 시험하는 티켓이 없다(04에도 06에도 없다).
>    - "`--records write`에서도 … 기록 파일을 쓰지 않으며"의 경우가 07에 없다.
>    - 15에는 "숫자를 일부러 떨어뜨린 커밋에서 빨강"이 없다.
> 5. **(c) 어떤 구현이든 통과하는 시험.**
>    - 06의 스토리 9 대체 시험은 늘 0을 내는 구현도 통과한다.
>    - 06의 스토리 18 시험 "보고서가 그 구성을 싣는다"는 `--config`가 평가에 쓰이지 않아도 통과한다.
> 6. **(c) 고칠 티켓이 명세와 다르다.** 명세는 `pyproject` 금지 목록과 `CLAUDE.md`의 수를 "판정기 포트를 넣는 티켓이 고친다"고 했는데, 포트는 01이 넣고 이 둘은 12가 고친다. 어느 한쪽으로 맞춰야 한다.
> 7. **(c) 없는 파일을 가리킨다.** 11이 적은 `docs/constitution/history.md`는 `git ls-files`에 없다.
> 8. **(c) 13의 Blocked by에 11이 없다.** 그런데 13의 수용 기준은 기준 보고서를 갱신하고(기준 보고서는 11이 만든다), What to build는 "CI … LLM 숫자"를 말한다.
> 9. **(c) 19가 지나지 못할 수 있다.** 02의 `validate`는 30MB 상한을 어느 묶음에나 걸고, 09는 `license` 값을 둘로 정한다. 19는 "바꾼 묶음이 `validate`를 지나고"를 요구한다. 명세는 이 둘이 공공 문서 묶음에만 걸리는지 정하지 않았다. allganize의 용량은 확인하지 않았다.
> 10. **근거의 종류.** HNSW 35/100과 CPU 재계산이 비트까지 같았다는 것은 "임시 스크립트로 손으로 봤다"고만 적혀 있고 명령이 없다(issue-tracker의 "그 명령과 함께"). HNSW 쪽은 ADR 이력의 근거인데, 다시 재는 티켓이 없다.
>
> **Nit**
>
> - 15가 맞추는 절차를 적을 자리를 `merge.md`의 "출시 PR"로 정했다. 명세는 자리를 정하지 않았다.
> - 17은 15에 막혀 있다. 명세는 "그 티켓(14) 뒤"만 요구한다.
> - 명세 173행의 "설치된 드라이버가 … 낡은 것으로 본다. 드라이버를 올리는 일은 사용자가 한다"가 현재형으로 남았다. 일지의 "잔존 0"과도 다르다.
> - ADR 0018 17행의 "…바뀐 PR에서만 돌고"에 푸시 이력의 포인터가 이어 달려 있지 않다(adr.md 규칙).
> - 18의 목록에 "요청 인자가 이긴다"와 숫자가 아닌 값을 거부하는 모양이 빠졌다. 12에는 "작업 단위 밖에서 부른다"가 빠졌다. `pyproject`의 계약 이름 "sixteen"과 주석 "열여섯"도 언급이 없다.
> - 명세의 "마이그레이션 0002가 같은 선례다"에서 0002는 jobs 표의 색인을 더한 것이다. 또 `SCHEMA_VERSION`의 주석("alembic이 올리는 형식을 바꾸면 함께 올린다")과 어긋난다.
>
> **확인해서 맞은 것**
>
> - Blocked by 사슬은 모두 01까지 이어진다.
>   - 04 → 01·03
>   - 07 → 05(끝점 필수를 07이 바꾼다)
>   - 12 → 05 → 04 → 03 → 02
>   - 16 → 11 → 08 → 07(`--records off`)
>   - 15 → 11·14
> - 일지의 티켓 표와 파일이 같다.
> - 표시 수 17/10/82/3/8이 맞다.
> - 따옴표 인용은 원문과 같다.
> - 사용자의 답 1~3과 5의 반영이 맞다.
> - 01의 EXPLAIN 시험은 잴 수 있다. 테스트 PG18(pgvector 0.8.7)에 40행 임시 표를 지어 손으로 봤다. `enable_seqscan=off`만 걸면 HNSW 색인 스캔을 쓰고, `enable_indexscan=off`를 더하면 순차 스캔이 된다. 롤백했다.
> - 정리 스킬의 결과는 주 체크아웃을 읽지 말라는 지시대로 확인하지 않았다.
>
> 참고 파일: `C:\project\rag-engine\.claude\worktrees\search-eval-tickets\.scratch\search-eval\issues\`, `...\docs\adr\0018-search-evaluation-in-app-and-baseline-gate.md`, `...\.scratch\search-eval\spec.md`

요약: 표준 축은 Critical·Major 0, Minor 7(보고의 머리는 6이라 적었다), Nit 5, smell 2이고 가장 무거운 것은 근거의 명령이 없는 것(Minor 7)이다. 명세 축은 Major 2, Minor 8, Nit 6이고 가장 무거운 것은 승인받지 않은 ADR 이력(Major 1)이다.

### 판정과 반영

두 축이 같은 것을 짚은 곳이 여럿이라 묶어 적는다. 판정의 근거는 지적마다 파일을 열어 봤다.

- 표준 Minor 1(명세의 내용 해시 문장): 유효. 계약을 바꾸고 옛 문장을 남긴 것이다. 내용 해시는 머리, 문서 목록, 기대 근거, 질의 목록 파일의 바이트와 구성(바로 아래 항목이 정한 JSON)으로 계산한다고 고쳤다.
- 표준 Minor 2, 명세 Nit(드라이버의 현재형 문장): 유효. 명세를 쓸 때의 판단과 미룬 것은 과거로, 그 티켓이 지금 할 일(GPU 이미지가 우회 없이 뜨는지 보기)은 현재로 갈랐다. `## 검증`의 잔존 0은 드라이버 판을 숫자로 찾아, 숫자가 없는 이 문장을 놓친 것이다.
- 표준 Minor 3, 명세 Minor 4(받는 티켓이 없는 시험): 유효. 07에 해시가 다른 문서 파일이 있을 때의 `index --records write`, 04에 `run`의 데이터베이스 판정과 키워드만 단계에서 놓친 것으로 세기, 12에 `judge`의 데이터베이스 판정(원칙 V), 15에 리랭크 뒤 숫자를 일부러 떨어뜨린 커밋의 빨강을 더했다. `inspect`는 명세의 시험 목록에 없어 06의 수용 기준(데이터베이스 판정을 지난다)에 그대로 둔다.
- 표준 Minor 4(CI 러너와 개발 PC의 CPU): 유효. 위 `## 명세 검토`의 문장을 재는 티켓이 없다는 한계로 고쳤다. 재는 일을 더 할지는 남긴다. 기록이 덮는 글은 CI가 다시 계산하지 않아, 섞이는 몫은 `read` 상한 안의 새 글뿐이기 때문이다.
- 표준 Minor 5, 명세 Minor 7(`history.md`가 없다): 유효. `docs/constitution/`에는 README, operations, principles, tech 넷뿐이다. 11을 README의 `**Version**` 줄로 고치고, 판을 올린 까닭은 그 README가 정한 대로 ADR 이력이나 일지에 적게 했다. `tools/check_ticket.py`가 면제 목록에 그 이름을 둔 것은 없는 파일을 허용할 뿐 해가 없어 남긴다.
- 표준 Minor 6, 명세 Minor 6(판정기를 넣는 티켓): 유효. 명세를 "Claude 판정기 어댑터와 SDK를 넣는 티켓"으로 고치고, 포트를 넣는 첫 티켓은 SDK를 들이지 않는다고 덧붙였다.
- 표준 Minor 7, 명세 Minor 10(근거의 명령): 유효. `docs/agents/issue-tracker.md`의 프로브와 근거 절은 명세·ADR이 근거로 드는 스크립트를 `probes/`에 커밋하라고 한다. 검토가 친 명령과 출력을 검토 서브에이전트의 기록에서 꺼내, 두 스크립트를 `.scratch/search-eval/probes/repeat/`에 커밋하고 README에 행 둘을 더했다. HNSW 프로브는 커밋할 파일로 다시 돌렸고 27·5·99가 나왔다(검토 때는 35·4·98). TEI 프로브는 Docker와 모델이 들어 다시 돌리지 않고 검토의 도구 출력을 옮겼다. 그러며 검토가 "약 470토큰"이라 한 글이 처리량 프로브의 글에서 `(정의)`가 빠진 900~918자이고 토큰 수는 잰 적이 없다는 것을 찾아, 명세를 "약 900자"로 고쳤다.
- 표준 Nit 다섯: 일지의 인용을 명세 원문 그대로 고쳤고, 표의 12행에 ADR 0007 이력의 가름을 더했고, 경로 판정을 쓰는 티켓에 08을 더했고, 01의 허공을 가리킨 기준을 지웠다. `[이력]` 수 3은 남긴다. 표시는 항목마다 하나이고(명세 머리의 표시 정의), 새 항목 셋은 사용자가 고른 것이라 `[사용자 선택]`이다. ADR 이력은 그 결정을 옮긴 것이고 명세 머리의 근거 줄이 가리킨다.
- 표준 smell 둘(Shotgun Surgery, Duplicated Code): 남긴다. 판단 항목이고, 티켓이 명세의 시험 문장을 옮겨 수용 기준으로 삼는 것은 to-tickets 5단계의 방식이다.
- 명세 Major 1(ADR 0018 이력 하나가 승인 범위 밖): 유효. 질문 4의 설명은 이력 하나(푸시)를 말했고, 질문 1·2의 설명에는 ADR이 없다. 정확 스캔과 기록 해시의 이력은 결정을 옮긴 것이지만 `CLAUDE.md` 작업 규약 5는 초안을 보이고 승인받으라고 하고, `next-session` `merge.md` 4는 그 승인을 병합 전에 받으라고 한다. 초안을 보이고 물었다(아래 `### 이력 초안의 승인`).
- 명세 Major 2(명세의 결정 둘을 받는 티켓이 없다): 유효. 사람 판정의 초벌과 확인, 색인 시점의 LLM 보강을 정하는 일을 13의 수용 기준 둘로 더했다. 13은 이미 사람의 가름을 기다리는 티켓이고 06(`human_causes`)과 10(공공 문서 묶음) 뒤에 선다. 새 티켓을 내지 않아 승인받은 분해의 수는 그대로다.
- 명세 Minor 3: 유효. 11에 취소된 실행에서 `verify`가 어떻게 끝나는지를 더했다. `--config`는 06과 12 둘 다에 적어, 나중에 들어오는 쪽이 `judge`에 더하게 했다(12는 06을 기다리지 않는다).
- 명세 Minor 5(어떤 구현이든 지나는 시험): 유효. 06의 스토리 9 시험에 `exact` 거짓일 때만 후보를 줄이는 시험용 대역에서 비율에 드는 경우를, 스토리 18 시험에 후보 수가 실제로 쓰였는지를 더했다.
- 명세 Minor 8(13의 Blocked by): 유효. 11을 더했다.
- 명세 Minor 9(19와 `validate`): 반만 유효. 02의 거부 목록에 `license` 값이 없어 `validate`는 그 값을 보지 않는다(02를 읽었다). 30MB 상한은 걸릴 수 있어, 19에 걸리면 멈춰 묻는 기준을 더했다.
- 명세 Nit(15가 정한 `merge.md`의 자리): 남긴다. 명세가 자리를 정하지 않은 것을 티켓이 정했고, 출시 PR의 절차는 `merge.md`의 "출시 PR" 절이 원천이다.
- 명세 Nit(17은 14 뒤면 된다): 유효. Blocked by를 14로 고쳤다.
- 명세 Nit(ADR 0018 게이트 문장의 포인터): 유효. 그 문장도 푸시 이력이 바꾼 범위라, `.claude/rules/adr.md`대로 포인터를 이어 달았다. 질문 4가 승인한 이력의 포인터다.
- 명세 Nit(18과 12의 빠진 모양, `pyproject`의 이름과 주석): 유효. 18에 요청 인자가 이기는 것과 숫자가 아닌 값의 거부 모양을, 12에 작업 단위 밖에서 부르는 것과 계약의 `name`·주석의 수를 더했다.
- 명세 Nit(마이그레이션 0002의 선례): 남긴다. 0002도 스키마를 바꾸고(작업 표의 색인) `SCHEMA_VERSION`을 1로 둔 마이그레이션이라 선례로 맞다. 주석의 "형식"은 `SCHEMA_VERSION`이 색인 판의 요소인 자리의 말이라 색인 형식으로 읽는다.

반영으로 새로 쓴 사실 문장(PR 직전 리뷰에 밀 주장으로 넘긴다).

1. 명세 단계별 측정 절: 티켓 세션이 커밋하며 다시 돌린 출력 `hnsw_repeat_out.txt`에서는 27개였다. ADR 0018 이력에도 같은 문장.
2. 명세 추론 기록 절: 약 900자의 글 8개를 임베딩해 보니 … 모두 비트까지 같았다(프로브 `.scratch/search-eval/probes/repeat/tei_repeat.py`로 손으로 봤다. 출력 `tei_repeat_out.txt`).
3. 명세 전체 게이트와 리랭커 절: 명세를 쓸 때는 … 그 티켓을 사용자가 드라이버를 올린 뒤로 미뤘다. 드라이버가 오른 지금, 그 티켓은 첫머리에 GPU 이미지가 우회 없이 뜨는지 보고 …
4. 명세 Further Notes: 판정기 포트를 넣는 첫 티켓은 SDK를 들이지 않는다.
5. 프로브 README: 벡터가 같은데 수가 달라, 색인을 지을 때의 난수가 실행마다 다른 것으로 본다(어림). 글은 처리량 프로브의 글에서 `(정의)`를 뺀 꼴이다. 검토는 `mixed`를 `importlib`로 모듈을 올려 불렀다.
6. 일지: 11의 흔들림 측정은 `read` 모드라 기록된 값을 다시 계산하지 않고, 14는 개발 PC에서만 잰다.
7. 티켓 06: 후보 수를 1로 준 실행의 합친 뒤 줄이 기본 구성의 실행과 달라지는 작은 묶음으로 본다.
8. 티켓 13: 명세는 LLM 보강을 이 기능의 티켓으로 두지 않았다.

### 이력 초안의 승인

명세 축 Major 1에 따라 ADR 0018의 첫 이력 초안(전문과 본문 포인터를 미리보기로)을 보이고 물었다.

- 질문(글 그대로): 셀프 리뷰가 짚은 것입니다. 티켓 세션 초반에 고르신 두 결정(평가는 정확 스캔으로 후보를 뽑는다, 추론 기록의 해시가 바뀌면 기준 갱신처럼 승인을 받는다)을 ADR 0018에 이력 한 항목으로 적었는데, 그때 ADR 초안은 보여 드리지 않았습니다(승인받은 ADR 이력은 푸시 이력 하나였습니다). 이 이력과 본문 '단계별 측정' 문장 끝의 포인터를 이대로 ADR 0018에 넣어도 될까요? 초안 전문은 미리보기에 있습니다. (선택지 2: 이대로 승인, ADR에서 뺀다)

> 사용자: "이대로 승인 (Recommended)" — 설명: ADR 0018에 이력 '평가는 후보를 정확 스캔으로 뽑고, 추론 기록의 해시가 바뀌면 승인을 받는다'와 본문 단계별 측정 문장의 포인터를 넣습니다. 결정은 이미 고르신 것이고, ADR 본문의 '같은 SQL 뼈대'가 실제 검색의 근사 후보를 잰다고 읽히는 것을 바로잡습니다.

미리보기의 초안은 지금 ADR 0018의 그 이력과 같은 글이다. 미리보기에서는 경로와 식별자의 백틱을 뺐고, 마지막 문장의 명세 경로 괄호(`.scratch/search-eval/spec.md`)를 뺐다. 승인 뒤 이력의 글을 고치지 않았다.

### 반영 뒤 다시 돌린 것

2026-11-13, 브랜치 `docs/search-eval-tickets`에서 손으로 쳤다. 판정 명령은 파이프 없이 출력을 파일로 돌려 종료 코드를 봤다.

- `uv run python tools/plan_table.py` 0, `--check` 0. `.scratch/plan.md`는 바뀌지 않았다.
- 바뀐 md 스물셋(명세, ADR 0018, 프로브 README, 티켓 열아홉, 이 일지)에 `check_md_tables.py` 0, `check_quotes.py --all-lines` 0(인용 26건, 경고 없음). `check_adr_pointers.py`는 ADR 폴더를 인자로 받으므로 인자 없이(`docs/adr/` 전체) 쳐서 0. 같은 스물셋과 프로브 폴더의 네 파일에 `check_line_separators.py` 0.
- 프로브 `tei_repeat.py`에 `uv run ruff check`와 `uv run ruff format --check`가 통과했다.
- 고친 옛 문장(판정기 포트를 넣는 티켓, 없는 헌법 이력 파일, 임시 스크립트 근거, 드라이버를 사용자가 올린다는 현재형, 허공의 가짜, 470토큰, 구성의 바이트로 계산하는 해시, 17의 옛 Blocked by)이 명세·티켓·ADR 0018·프로브 README에 0이다(grep 종료 1).
- 테스트, 린트, 포맷 검사, 타입체크, import 경계는 커밋이 부르는 pre-commit으로 갈음한다(`CLAUDE.md` 검증 명령). 결과는 커밋 뒤 아래에 적는다.

## PR 직전 리뷰

### CodeRabbit CLI(원문)

`coderabbit-review` 서브에이전트에게 작업 트리 전체(기준 3c70184, 커밋 전)와 셀프 리뷰 반영으로 새로 쓴 사실 문장 여덟을 밀 주장으로 넘겼다.

> **CodeRabbit CLI: 리뷰가 끝나지 못했다. findings는 0건이고 이슈 없음이 아니다.**
> - CLI 0.7.5가 설치돼 있고 로그인은 되어 있다(`Plan: Free`, `Seat: not assigned`). 그래서 3단계로 가서 `coderabbit review --agent --include-untracked`를 돌렸다.
> - 연결, 설정, 분석(`reviewing`)까지 가서 heartbeat 세 번을 받았다. 그다음 `{"type":"error","errorType":"connection","message":"Connection failed: WebSocket closed","recoverable":true}`로 비정상 종료했다. `review_completed`는 나오지 않았다.
> - 재실행은 시간당 한도를 하나 더 써서 하지 않았다. 출력은 `C:\Users\User\AppData\Local\Temp\claude\e659c78be23187d6\130964ad-d5c9-48c0-982b-022a71d6ade6\scratchpad\cr.txt`에 있다.
> - 본 세션이 대체 둘(`/security-review`, `bug-perf-review` 서브에이전트)을 돌린다. 일지를 쓰는 세션이면 두 보고도 받은 턴에 일지로 옮긴다.
>
> **요청하신 사실 문장 검증.** 저는 아무것도 고치지 않았다.
>
> 1. **상위 50이 다른 질의 27개: 맞다. 프로브 출력을 읽어 확인했다.** `hnsw_repeat_out.txt`는 `lists_differ_a_b 27 / top10_differ_a_b 5 / lists_differ_a_exact 99`다. 명세, ADR 0018, README의 27·5·99와 같다. 출력 첫 줄의 pgvector도 0.8.7이다. 이전 값 35·4·98은 검토 서브에이전트의 도구 출력이라 저는 확인하지 못했다.
> 2. **900자 글 8개가 비트까지 같았다: 글 길이는 확인했고 출력은 옮겨 온 값이다.**
>    - `texts()`를 `uv run --no-project python -I`로 불러 보니 길이는 `[900, 918, 918, 918, 918, 918, 918, 918]`이다. "900~918자"가 맞다.
>    - `tei_repeat_out.txt`의 비교 아홉 줄은 모두 `identical True`, `max_abs_diff 0.0`이다.
>    - 이 출력을 이 세션이 다시 만든 것은 아니다. README도 검토의 도구 출력을 옮겼다고 적는다. Docker와 모델이 필요해서 저도 다시 돌리지 않았다.
>    - "비트까지"는 JSON으로 받은 float이 `==`로 같다는 뜻이다. 서버의 부동소수 비트와 같다는 것까지는 말하지 못한다. 문구를 "반환값이 같았다"로 낮추면 더 정확하다.
> 3. **티켓 14와 명세: 맞다. 명세와 티켓을 읽어 확인했다.** 14의 첫 수용 기준이 우회 없이 `--gpus all`로 뜨는지 본다. 뜨지 않으면 로그를 남기고 멈춘다. 명세 173행도 560.94에서 621.24로 올랐다고 적는다.
> 4. **Further Notes와 티켓 12: 맞다. 코드를 읽어 확인했다.** 명세 238행과 12의 첫 수용 기준이 `anthropic`을 더해 열일곱으로 만들고, `pyproject.toml`의 이름과 주석, `CLAUDE.md`의 "열여섯"을 고친다. 현재 `pyproject.toml`에는 `sixteen`이, `CLAUDE.md`에는 열여섯이 있다. 티켓 01에는 SDK나 `anthropic` 언급이 없다.
> 5. **README 새 행 둘:**
>    - 난수 추정은 README가 스스로 어림이라고 적었고 SQL 머리 주석도 같다. 이것은 어림이다.
>    - `tei-cpu/embed_throughput.py`의 문장은 `제{n}조(정의) 이 규정에서…`다. `tei_repeat.py`는 `제{n}조 이 규정에서…`라서 `(정의)`를 뺀 꼴이 맞다. 다만 `embed_throughput.py`는 `SENTENCE`를 여러 줄로 이어 붙인 문자열이다. 뒤 문장까지 같은지는 제가 끝까지 대조하지 않았다.
> 6. **일지의 11과 14: 맞다.**
>    - 티켓 11은 `read` 모드에서 CI에 세 번 돌리고 흔들림을 잰다.
>    - 티켓 14는 개발 PC의 GPU에서만 돌린다.
> 7. **티켓 06의 `--config` 시험: 구현을 가를 수 있다.**
>    - 후보 수를 1로 주면 합친 뒤 줄이 달라진다. 구성을 싣기만 하고 쓰지 않는 구현은 이 시험을 지나지 못한다.
>    - 조건이 하나 있다. 작은 묶음에서 기본 구성의 합친 뒤 줄이 질의 하나당 조각 둘 이상이어야 한다. 아니면 두 실행이 같아진다. 수용 기준에 그 조건을 적어 두면 좋다.
> 8. **티켓 13: 맞다. 명세를 읽어 확인했다.** 명세 120행이 `no_context` 비율을 본 뒤 사용자가 LLM 보강 여부를 정한다고 적는다. 13은 정하는 데까지만 하고 받는 기능을 따로 정하라고 한다. 명세 205·228행에도 이 기능의 구현 티켓으로 두는 문장은 없다.
>
> **Blocked by 사슬: 어긋난 곳은 찾지 못했다.** 14는 10에만 막혀 있는데, `run --through rerank --records write`가 05·07에 기대는 것은 10→07→05로 이어져 있다. 17과 18은 14에, 15는 11과 14에 막혀 있고 둘 다 수용 기준과 맞는다. 13은 06, 10, 11, 12에 막혀 있고 수용 기준이 쓰는 `inspect`, `judge`, `baseline-fast.json`을 덮는다.
>
> 받는 본 세션에게: 일지를 쓰는 세션이면 이 보고를 받은 이 턴에 일지로 옮긴다. 고친 것과 남긴 것은 지적마다 판정한 턴에 옮긴다(code-review 6단계 끝).

판정과 반영.

- CLI가 끝나지 못했다: 리뷰로 세지 않는다. `docs/constitution/operations.md` 리뷰 파이프라인대로 버그·성능 축은 `bug-perf-review`가, 보안 축은 내장 `/security-review`가 본다. `/security-review`는 커밋된 범위를 보므로 커밋 뒤에 돌린다.
- 2의 "비트까지": 유효. 프로브는 JSON으로 받은 수를 `==`로 견줬을 뿐이라, 명세의 그 문장을 응답의 값이 모두 같았다는 말로 낮추고 견준 방법을 괄호에 적었다. 같은 말을 쓴 티켓 14의 수용 기준과 이 일지의 앞 절(명세 검토의 요약과 지적 반영)도 낮췄다. 인용한 보고 원문과 새로 쓴 사실 문장 목록은 그때의 글이라 그대로 둔다.
- 5의 뒤 문장: 이 세션이 두 모듈을 올려 처리량 프로브의 `SENTENCE`에서 `(정의)`를 지운 값이 `tei_repeat.py`의 `SENTENCE`와 같은지 불러 봤고 참이었다. README 문장은 그대로 둔다.
- 7의 조건: 유효. 06의 그 시험에 기본 구성에서 기대 근거가 합친 순위 둘째 이후에 닿는 질의가 있어야 두 실행이 갈린다는 조건을 적었다.
- 1, 3, 4, 6, 8과 Blocked by 사슬: 확인한 것이라 고칠 것이 없다.

반영으로 새로 쓴 사실 문장(PR 직전 `bug-perf-review`에 밀 주장으로 넘긴다).

1. 명세 "추론 기록" 절: "컨테이너를 다시 띄운 뒤에 돌려받은 값이 모두 같았다(JSON으로 받은 수를 `==`로 견줬다."
2. 티켓 14: "CPU 임베딩의 반복(JSON으로 받은 값이 `==`로 같았다)"
3. 티켓 06: "기본 구성에서 기대 근거가 합친 순위 둘째 이후에 닿는 질의가 있어야 두 실행이 갈린다."

반영 뒤 다시 돌린 것. 2026-11-13, 같은 브랜치에서 손으로 쳤다.

- 바뀐 md 스물셋에 `check_md_tables.py` 0, `check_quotes.py --all-lines` 0(인용 26건, 경고 없음). `check_adr_pointers.py`(인자 없이) 0. `plan_table.py --check` 0.
- `check_line_separators.py`는 처음에 1이었다. 프로브 폴더를 글롭으로 넘겨, SENTENCE를 대 보려고 모듈을 올릴 때 생긴 `__pycache__`(무시되는 폴더)를 읽지 못했다. 그 폴더를 지우고 파일 넷을 이름으로 넘겨 0.
- 명세, 티켓 열아홉, ADR 0018, 프로브 README에 "비트까지"가 0이다(grep 종료 1).

### 보안 축: 내장 `/security-review`(원문)

커밋 9820faf 뒤에 돌렸다. 스킬이 보여 준 커밋 목록에는 dev에 이미 병합된 c0c8727, 11313d8이 섞여 있었다(대칭 범위로 뽑은 목록이다). 그래서 식별 하위 작업에 범위를 `git diff 3c70184 9820faf`로 못 박아 넘겼다. 하위 작업의 보고 원문이다.

> No candidate vulnerabilities.
>
> Scope: I reviewed `git diff 3c70184 9820faf` (27 files) and nothing else. No `src/`, `tests/`, `tools/` or workflow file changed. I did not modify any files.
>
> **Probe files (the only executable content):**
>
> 1. `.scratch/search-eval/probes/repeat/tei_repeat.py`
>    - **Untrusted input:** none. The TEI base URL, model name, kind and output and input paths all come from `sys.argv`, which counts as trusted CLI input. Request bodies are built from hardcoded Korean sentence constants. Responses are parsed with `json.loads`, and saved runs are read back with `json.load`; both are safe deserialization. There is no pickle, eval, subprocess or shell.
>    - **Connects to:** the URL from argv. The docstring uses `http://127.0.0.1:18091` with `/health`, `/v1/embeddings` and `/rerank`. Its `docker run` example publishes the port on loopback only (`-p 127.0.0.1:18091:80`).
>    - **Files:** writes the argv-named JSON output (`run1.json`/`run2.json`) and reads two argv-named JSON files in `compare`.
>
> 2. `.scratch/search-eval/probes/repeat/hnsw_repeat.sql`
>    - **Untrusted input:** none. It is fully static SQL with no parameters or string building; vectors come from `setseed(0.42)` plus `random()`.
>    - **Connects to:** nothing itself. Per its header comment it is piped through `docker exec ... psql -U rag_test` into the existing test container `rag-engine-test-postgres-1`, into a throwaway database `probe_hnsw_repeat` that is then dropped.
>    - **Files and side effects:** only tables and an extension inside that throwaway database. It uses the existing test-only `rag_test` account (defined in `compose.test.yml`, not changed by this PR) and adds no new credential.
>
> 3. `.scratch/search-eval/probes/repeat/tei_repeat_out.txt`: static output (timings and equality and diff numbers). Nothing reads or executes it, and it holds no secrets or document content beyond the synthetic test sentences.
>
> 4. `.scratch/search-eval/probes/repeat/hnsw_repeat_out.txt`: static psql output (pgvector version and three counts). Same as above: not read by anything, no sensitive data.
>
> **Markdown (19 tickets, `spec.md`, ADR 0018, journal, `probes/README.md`):** documentation only, which is excluded from findings by the review rules. A grep of the added lines for secret, key, token, DSN, eval, pickle and subprocess patterns found no hardcoded credentials. Judge settings are referenced only by name (`RAG_JUDGE_API_KEY`), and the spec requires that the key and request/response bodies stay out of logs (principle V).
>
> **Design notes that are not findings (no code exists yet):**
> - Ticket 11 already plans to confirm, from GitHub's official docs, whether fork PRs can poison the CI model cache.
> - ADR 0018's new history entry adds a hash check on the stored inference records (`추론 기록`), so a hand-edited record cannot pass the gate unapproved.
>
> Both should get a security check when the CI workflow and eval code are actually written.

판정. 후보가 없어 스킬의 2단계(후보마다 거짓 양성 거르기)는 돌 것이 없었고, 보고할 취약점은 0이다. 끝의 두 설계 메모는 지적이 아니고, 받는 티켓(11의 캐시 확인, 07·08의 해시 검사)에 이미 적혀 있어 더할 것이 없다.

### 버그·성능 축: `bug-perf-review`(원문)

커밋 9820faf 뒤에 범위 `3c70184..HEAD`와 밀 주장(셀프 리뷰의 새 사실 문장 여덟과 CodeRabbit 반영의 셋)을 넘겼다. 보고 원문이다.

> 기준 커밋 3c70184, 범위 파일 약 30개(명세 1, 티켓 19, ADR 1, 프로브 README 1, 프로브 repeat/ 4, 일지 1, 그 밖에 llm-sdk/ 등 프로브 출력 몇 개). 마지막 [호출 6].
>
> tei_repeat.py와 hnsw_repeat.sql은 실행하지 않고 읽기만 했다(Docker·모델·PostgreSQL 필요).
>
> ## 지적
> - [Minor] .scratch/search-eval/spec.md:83, docs/adr/0018-search-evaluation-in-app-and-baseline-gate.md:64, .scratch/search-eval/probes/README.md:13 — "상위 50이 다른 질의 27개(35개)"는 순서까지 견진 수라서, 후보 집합이 다른 질의의 수가 아니다.
>   - 시나리오: 두 문서는 이 수를 "리랭크 기록이 CI 색인의 후보 쌍을 덮지 못한다"는 근거로 쓴다. 리랭크 기록이 덮어야 하는 것은 후보 집합이다.
>   - 근거: hnsw_repeat.sql:35의 `ra.ids <> rb.ids`는 정렬된 배열 전체를 비교한다. 순서만 바뀌고 집합은 같은 질의도 센다. 출력의 lists_differ_a_b 27이 그렇게 센 값이다.
>   - 제안: 문장에 "순서까지 포함해"를 적거나, 집합 비교(정렬한 배열)로 다시 잰다. 결정(정확 스캔)이 뒤집힐 만한 오차는 아니다.
> - [Nit] .scratch/search-eval/probes/repeat/hnsw_repeat.sql:15-16, probes/README.md:13 — 설명이 실제 SQL과 조금 다르다.
>   - 근거: SQL 22~27행은 빈 표에 HNSW 색인을 먼저 만들고 행을 나중에 INSERT한다. 그래서 CREATE INDEX의 일괄 빌드가 아니라 증분 삽입으로 지은 색인이다.
>   - 영향: README와 SQL의 "색인을 지을 때의 난수"는 "삽입 때의 레벨 난수"로 읽어야 한다. 프로젝트의 실제 색인이 어느 방식인지에 따라 대표성이 달라진다. 이미 "어림"으로 적혀 있어 사실 문장은 아니다.
> - [Nit] .scratch/search-eval/probes/repeat/tei_repeat.py:119-122와 tei_repeat_out.txt 1·5번째 줄 — `in-process same_1 vs same_1`과 `restart same_1 vs same_1`은 자기 자신과의 비교라 항상 identical True다.
>   - 영향: README의 "비교 아홉 줄 모두 identical True"에서 두 줄은 정보가 없다. 실제로 견준 것은 일곱 줄이다. 수를 틀리게 적은 것은 아니다. "자기 비교 둘 포함"을 한 줄 적으면 된다.
>
> ## 밀 주장 대조 (문제 없음)
> - spec.md:83의 "27개", README의 "27·5·99"와 hnsw_repeat_out.txt: 출력 값 27, 5, 99와 같다. pgvector 0.8.7도 맞다. ADR 64행의 27도 같다. 35·4·98은 검토의 도구 출력을 옮긴 것이고 README가 그렇게 적었다.
> - spec.md:148의 "컨테이너를 다시 띄운 뒤에 돌려받은 값이 모두 같았다(JSON으로 받은 수를 `==`로 견줬다.":
>   - tei_repeat.py 106행이 `a == b`로 견준다. json.loads로 받은 float을 견주는 것이다.
>   - 출력의 아홉 줄은 모두 identical True, max_abs_diff 0.0이다. 문장은 출력과 맞는다.
>   - 묶음 구성도 맞다. 같은 묶음 두 번, 뒤집기, 4+4로 나눈 묶음("둘로 나눈"), 짧은 글을 섞은 묶음(mixed), 재시작 뒤 같은 넷이다.
>   - 닫는 괄호가 문장 안에서 빠져 있는데, 뒤의 "프로브 …"와 이어지는 구성이라 비문 수준이다.
> - 티켓 14(issues/14-gpu-rerank-records.md:11)의 "JSON으로 받은 값이 `==`로 같았다": 위와 같은 근거로 맞다. 같은 글에 "비트까지"는 남아 있지 않다.
> - 티켓 06(issues/06-miss-causes-and-breakdowns.md:16)의 "기본 구성에서 기대 근거가 합친 순위 둘째 이후에 닿는 질의가 있어야 두 실행이 갈린다.":
>   - 후보 수 1로 줄이면 합친 뒤 줄이 1개가 된다. 둘째 이후에 닿던 질의만 줄이 달라진다. 논리는 맞다.
>   - 수용 기준이 "구성을 싣기만 하고 쓰지 않는 구현"을 거르도록 닫혀 있다.
> - 약 900자 글 8개: texts() 구조로 계산하면 900자(n이 한 자리인 s=0)와 918자(나머지 7개)다. README의 "900~918자"와 명세의 "약 900자"가 모두 맞다.
> - README의 "(정의)를 뺀 꼴": 일지에 이 세션이 불러 대 본 기록이 있다. 서브에이전트 보고도 `제{n}조(정의)` 대 `제{n}조` 차이를 확인했다.
> - tei_repeat.py 독스트링의 명령:
>   - `uv run --no-project python -I tei_repeat.py` 방식은 스크립트 폴더에서 치면 돈다. -I는 스크립트 경로를 sys.path에 넣지 않지만 표준 라이브러리만 쓰므로 문제없다.
>   - docker restart는 포트·옵션을 유지한다. --max-batch-tokens 4096에 8글자 약 3,760토큰과 mixed의 11글자는 한 배치에 들어간다.
>   - mixed의 순서 복원(`together[len(short):] + together[:len(short)]`)은 alone의 `items + short` 순서와 맞는다.
>   - reversed의 두 번 뒤집기도 맞다.
> - Blocked by 사슬(issues/*.md의 5행 전부): 어긋난 곳은 없다.
>   - 14는 10에만 막혀 있지만 10→07→05가 이어진다.
>   - 17·18은 14에, 15는 11과 14에, 13은 06·10·11·12에 막혀 있다.
>   - 16은 06과 11에, 19는 06과 07에 막혀 있다.
>   - 받는 쪽이 보내는 쪽보다 먼저 도는 자리는 못 찾았다.
> - 명세 "단계별 측정" 문장의 exact 기본 설계와 ADR 0018 이력 본문(:64)의 "같은 SQL 뼈대는 글의 뜻으로만 남는다" 설명은 서로 어긋나지 않는다.
>
> ## 요약
> - 총 3건(Minor 1, Nit 2). 모두 유효하고 오탐은 0건이다.
> - 즉시 수정 권장: 첫째 지적 하나뿐이다. 문장에 "순서까지 견준 수"를 더하거나 집합 비교로 재측정한다.
> - 따라가지 못한 것: 티켓 01~05, 07~19의 수용 기준 내용 대조와 일지의 나머지 사실 문장은 목록의 밀 주장 밖이라 Blocked by와 인용 대조만 했다. 실행으로 확인한 것은 없다.
>
> 받는 본 세션에게: 일지를 쓰는 세션이면 이 보고를 받은 이 턴에 일지로 옮긴다. 고친 것과 남긴 것은 지적마다 판정한 턴에 옮긴다(code-review 6단계 끝).

판정과 반영.

- Minor(순서까지 견준 수): 유효. 문구만 고치지 않고 다시 쟀다. SQL 끝에 순서를 지운 집합으로 견주는 줄(두 표의 상위 50이 함께 가진 수의 최솟값과 평균 포함)을 더하고, 테스트 PostgreSQL의 임시 데이터베이스에서 한 번 더 돌려 출력 `hnsw_repeat_set_out.txt`를 더했다. 순서로 25·6·99, 집합으로 25·99, 함께 가진 수는 최소 43, 평균 49.55다. 이 실행에서 순서로 다른 질의와 집합으로 다른 질의가 같았으므로, 리랭크 기록이 CI 색인의 후보 쌍을 덮지 못한다는 추론은 선다. 갈리는 폭(평균 0.45개, 많아야 7개)은 작다. 명세 83행, 프로브 README, PR 본문에 "순서까지 견줘"와 새 출력의 수를 적었다. ADR 0018 이력의 문장("상위 50이 다른 질의가 35개였다")은 사용자가 승인한 글이고 글자대로 참이며(목록이 달랐다), 새 실행이 그 추론을 받치므로 고치지 않는다. 옛 출력 `hnsw_repeat_out.txt`는 ADR과 명세가 든 27의 근거라 그대로 두었다.
- Nit(색인을 지을 때의 난수): 유효. SQL 머리 주석과 README를 "행을 색인에 넣을 때의 난수"로 고치고, 빈 표에 색인을 먼저 짓는 순서가 제품과 같다는 것을 적었다. 제품은 `PostgresVectorIndex.create_version_index`가 판의 색인을 만들고 `replace_chunks`가 그 뒤에 조각을 넣는다(`src/rag_engine/adapters/postgres/vector_index.py`를 읽었다).
- Nit(자기 비교 둘): 반만 유효. `compare`는 첫 실행의 `same_1`을 기준으로 첫 실행의 묶음 넷과 다시 띄운 실행의 묶음 넷을 견준다(`tei_repeat.py`의 `compare`를 읽었다). 자기 비교는 `in-process same_1 vs same_1` 한 줄이고, `restart same_1 vs same_1`은 다시 띄우기 전과 뒤의 비교라 정보가 있다. README에 그 두 줄을 풀어 적었다.
- 밀 주장 대조: 모두 문제없다고 확인됐다. 명세 148행의 괄호는 여러 문장을 담은 하나의 괄호라 고치지 않는다.

반영으로 새로 쓴 사실 문장(PR 봇 회차가 겨냥할 자리).

1. 명세 83행: "상위 50이 순서까지 견줘 다른 질의가 35개였다", "집합 비교를 더해 한 번 더 돌린 출력 `hnsw_repeat_set_out.txt`에서는 순서로도 집합으로도 25개였고, 두 표의 상위 50이 함께 가진 후보는 최소 43개, 평균 49.55개였다."
2. 프로브 README `repeat/hnsw_repeat.sql` 행: 빈 표에 색인을 먼저 짓는다, 둘째 결과 줄의 설명, 셋째 실행의 수, "행을 색인에 넣을 때의 난수", "처음 검토가 같은 SQL(머리 주석, 판을 찍는 줄, 집합 줄만 다르다)".
3. 프로브 README `repeat/tei_repeat.py` 행: "첫 비교 줄 `in-process same_1 vs same_1`은 같은 값끼리의 자기 비교라 늘 참이다. `restart same_1 vs same_1`은 다시 띄우기 전과 뒤를 견준다."
4. `hnsw_repeat.sql` 머리 주석: 제품의 순서와 같다(코드를 읽었다), 둘째 결과 줄의 설명.

## 커밋과 다시 돌린 것

- 커밋 9820faf(셀프 리뷰와 CodeRabbit 반영까지)의 pre-commit: ruff check, ruff format, 검사 러너(test-db, check-ticket, zizmor, lint-imports, check-instructions, check-type-escapes, pyright, pyright-linux, run-hooks, pytest 377.0초)가 모두 Passed. markdown tables, line separators, mutation tables, quotes(경고 없음), commit message도 Passed이고 constitution version은 고친 헌법 파일이 없어 Skipped였다. 커밋 전에 `tools/sibling_overlap.py`는 새 ADR 번호 없음, 번호 겹침 없음, 함께 고친 파일 없음이었다(origin/dev는 c0c8727로 이 브랜치의 기준보다 두 커밋 앞이고, 그 두 커밋은 이 PR의 파일을 건드리지 않았다).
- `bug-perf-review` 반영 뒤 손으로 친 것: 고친 md 셋(명세, 프로브 README, 이 일지)에 `check_quotes.py --all-lines` 0(인용 23건, 경고 없음), `check_md_tables.py` 0. 그 셋과 `hnsw_repeat.sql`, `hnsw_repeat_set_out.txt`에 `check_line_separators.py` 0. 나머지 검사는 다음 커밋의 pre-commit으로 갈음한다.
- 리뷰 반영분의 첫 커밋 시도는 pre-commit의 pytest에서 하나가 실패해 커밋되지 않았다(1 failed, 3824 passed, 935.85초. 첫 커밋 때의 377초보다 크게 느렸다). 실패한 것은 이 PR이 건드리지 않은 `tests/adapters/test_parse_runner.py`의 `test_메시지를_보내다_멈춘_자식이_있어도_수신이_영영_막히지_않는다`로, 윈도에서 `parse_failed`를 기대했는데 `parse_timeout`이 났다(기한 2초). dev의 11313d8(#36)이 부하에서 자식의 기동이 기한을 넘는 바로 이 경우를 고쳐 윈도 기한을 30초로 늘렸고, 이 브랜치는 그 앞(3c70184)에서 땄다. 시험을 손으로 고치지 않고 스테이징을 푼 뒤 origin/dev를 병합했다(3db82a9. 두 쪽이 함께 고친 파일은 없다). 그 뒤 같은 변경을 다시 커밋한다.

## 회고

PR을 열기 전에 `retro` 스킬로 돌았다. 읽은 것은 이 일지(`uv run python tools/sibling_overlap.py --journal`이 찍은 경로)와 이 세션이고, 이 일지에는 "번복"과 "갈린 곳" 절이 없다. 후보 아홉 가운데 승인 셋, 넘김 하나(사용자가 대기열에 두기로 답했다), 기각 다섯이다. 이 세션에서 반영한 것은 없다. 만료는 `uv run python tools/queue_open_rows.py`의 "만료할 항목"이 없어(열린 항목 38개) 닫은 것이 없다. 첫 출력이 비어 `--ref origin/main`으로 다시 돌린 교집합도 비므로 그 실행은 하지 않았다.

1. **재지 않은 것을 잰 것처럼 적었다.** 승인(회차로 세는 것. `docs/agents/issue-tracker.md` 프로브와 근거 절을 어겨 리뷰가 잡았다). 명세 검토 서브에이전트가 보고한 셋을 명세에 옮겼다. 글의 크기를 "약 470토큰"이라 했으나 토큰 수는 잰 적이 없었고(셀프 리뷰 표준 축이 잡았다), JSON으로 받은 수를 `==`로 견준 결과를 "비트까지 같았다"로 적었고(PR 직전 CodeRabbit 에이전트가 잡았다), 순서까지 견준 배열의 차이를 후보 집합의 차이로 읽었다(PR 직전 `bug-perf-review`가 잡았다. 집합 줄을 더해 다시 재니 그 실행에서는 둘이 같았다). 열린 항목 `measured-claim-beyond-probe`에 6회차를 더했다. 이번 출처는 서브에이전트 보고의 수치라, 처방이 닿아야 할 자리가 명세를 쓰는 스킬과 독스트링에 더해 서브에이전트 보고를 옮기는 자리까지다. 반영 자리(`.claude/skills/to-spec/SKILL.md`)는 이 면제 PR이 바꿀 수 있는 경로가 아니라 chore에 둔다.
2. **ADR 이력을 초안 없이 썼다.** 승인(회차로 세는 것. 항상 실리는 `CLAUDE.md` 작업 규약 5를 어겨 셀프 리뷰 명세 축이 Major로 잡았다). 질문 1·2의 답은 결정만 골랐고 ADR을 말하지 않았는데, 그 결정을 ADR 0018 이력으로 쓰며 초안을 보이지 않았다. 리뷰 뒤 초안을 보이고 승인받았다(`### 이력 초안의 승인`). 헌법 문서를 다룬 열린 항목 `constitution-edit-beyond-approval`과 같은 일(승인이 필요한 문서를 사용자 답이 허락한 범위 밖에서 고쳤다)이지만 그 처방(헌법 파일을 고치는 편집의 계기 훅)이 ADR을 덮지 못해, 새 항목 `adr-history-without-draft`(1회차)를 쓰고 두 항목이 서로 가리키게 했다.
3. **뒤처진 브랜치에서 dev가 이미 고친 부하 시험이 커밋을 막았다.** 승인(사건: 위 `## 커밋과 다시 돌린 것`의 실패한 커밋 시도. pre-commit이 945초를 돈 뒤 실패했다. 층: 커밋 전에 치는 `tools/sibling_overlap.py`의 출력. 되돌림: PR 하나). 그 도구는 origin/dev가 앞선 것(c0c8727)을 찍었으나 그 앞선 커밋이 시험을 고쳤다는 것은 알리지 않았다. 더하는 것이라 새 항목 `stale-branch-base-test-fix`(1회차)로 다섯 번째를 기다린다. 부하에서만 빨간 시간 시험의 새 사례는 아니다. dev의 #36이 고친 같은 시험이다.
4. **문서만 바꾼 커밋도 전체 pytest를 돈다.** 넘김(게이트를 좁히는 것). 이 세션에서 pytest가 네 번(361.1초, 377.0초, 935.85초, 650.9초) 돌았다. 361.1초는 셀프 리뷰 전에 손으로 친 검사 러너이고, 377.0초의 커밋(9820faf)은 프로브 스크립트 `tei_repeat.py`도 담았으며, 935.85초와 650.9초의 두 커밋 시도가 문서, SQL, 프로브 출력만 바꿨다. 사용자에게 보인 질문은 이 넷을 모두 문서만 바꾼 커밋의 값처럼 적었다. `tests/test_plan_status.py` 같은 저장소 상태 시험이 `.scratch`와 `docs`를 읽어 통째로 뺄 수는 없다. 사용자의 답으로 새 항목 `docs-only-commit-full-pytest`(1회차)를 썼다. 질문(글 그대로의 끝 두 문장): 이 후보를 '문서만 바꾼 커밋은 저장소 상태 시험만 돌게 좁힌다'는 처방으로 회고 대기열에 둘까요? 게이트를 좁히는 일이라 제가 스스로 승인할 수 없는 판정입니다.

> 사용자: "대기열에 둔다 (Recommended)" — 설명: 사용자 승인으로 회고 대기열에 1회차 항목을 만듭니다. 어떤 시험을 남길지와 ADR이 필요한지는 그 항목을 반영하는 chore가 정합니다. 지금은 아무 검사도 바꾸지 않습니다.

5. **`check_adr_pointers.py`에 파일을 넘겼다.** 기각(도구가 그 자리에서 "ADR 파일이 하나도 없다"로 알렸다). 셀프 리뷰 뒤 검증 줄이 그 검사를 바뀐 md에 돌린 것처럼 적었던 것은 고쳤다.
6. **65줄 heredoc으로 일지를 붙이려 했다.** 기각(훅이 막고 Write 도구로 쓰라고 알렸다).
7. **스크래치 폴더로 `cd`했다.** 기각(훅이 막았다).
8. **CodeRabbit CLI가 WebSocket이 닫혀 끝나지 못했다.** 기각(`docs/constitution/operations.md` 리뷰 파이프라인의 대체 길인 `bug-perf-review`와 `/security-review`가 받았다).
9. **`/security-review`가 대칭 범위의 diff(287KB, dev에 병합된 두 커밋 포함)를 냈다.** 기각(내장 스킬이라 저장소에 고칠 자리가 없고, 식별 하위 작업에 범위를 `git diff 3c70184 9820faf`로 못 박아 넘겨 비용이 작았다).

## 다음

- **다음 단계는 티켓 01의 구현이다**(`/implement .scratch/search-eval/issues/01-diagnose-and-judge-ports.md`). 티켓 열아홉 가운데 `Blocked by`가 없는 것은 01 하나라 나란히 여는 묶음이 아니다. 01 뒤에 열리는 것은 02 하나이고, 그 뒤는 03, 04, 05로 이어지는 사슬이다(티켓마다의 `Blocked by` 줄).
- **앞 일지의 "다음"이 넘긴 확인 일은 티켓에 실었다.** 판정기의 SDK가 예외와 디버그 로그에 무엇을 싣는지와 ADR 0007 이력의 넷째 플러그인 자리 한 줄은 12, 포크 PR의 모델 캐시는 11, 묶음 경로의 junction과 심볼릭 링크는 02의 수용 기준이다. 면제 PR이 고칠 수 없어 구현 티켓이 고치는 파일은 명세 Further Notes에 그대로 있다.
- **사람의 판단을 기다리는 지점은 티켓마다 "멈춘다"로 적었다.** 후보 문서의 확정(09), 질문의 검수(10), 첫 빠른 기준 보고서와 흔들림·CI 시간의 상한(11), 첫 판정의 비용과 사람 판정, 색인 시점의 LLM 보강(13), GPU 이미지가 우회 없이 뜨지 않을 때와 장치 사이의 값의 차(14), 첫 전체 기준 보고서(15), 청킹·후보 수 실험의 결과(16), 리랭커의 기본(17), 최소 점수(18), 공개 데이터셋의 크기 상한(19)이다(`**멈`을 grep해 열 티켓을 셌다).
- **재는 티켓이 없는 한계.** 개발 PC와 CI 러너의 CPU 사이에 임베딩 값이 같은지는 어느 티켓도 재지 않는다(명세 "추론 기록" 절과 위 `## 셀프 리뷰`의 판정). 실제 bge-m3 벡터에서 HNSW 후보가 흔들리는 크기도 재지 않았다(정확 스캔을 골라 게이트의 숫자에는 들지 않는다).
- **PR #27 봇 첫 회차에서 남겨 사용자가 정할 것**(원칙 VII 아래나 헌법 README에 ADR 0015의 판 해석을 가리키는 포인터를 둘지)은 그대로 남아 있다.
- **회차 5 이상인 열린 대기열 항목은 하나다**(`measured-claim-beyond-probe`, 이 세션에서 6회차). 결정표의 chore 줄은 기능의 마지막 티켓 뒤에 연다. 이 세션이 새로 쓴 항목은 `adr-history-without-draft`, `stale-branch-base-test-fix`, `docs-only-commit-full-pytest`(사용자 승인)이고 모두 1회차다(위 `## 회고`).
- **이 브랜치에는 origin/dev를 합친 커밋이 하나 있다**(3db82a9, 위 `## 커밋과 다시 돌린 것`). squash 병합이라 dev의 이력에는 남지 않는다.
- **원격 브랜치 `docs/search-eval`이 남아 있다.** 앞 세션에서 분류기가 삭제를 거부했고(Git Destructive) 이 세션도 건드리지 않았다.
- **사람에게 넘긴 정리.** `tidy-checkouts`가 워크트리 `14-reindex-version-switch`를 넘겼고(병합된 PR의 머리와 브랜치 끝이 다르다), `.claude/worktrees/.tidy-trash/`에 `.venv` 넷이 남았다(다른 프로세스가 올린 모듈 때문이다. 다음 정리가 다시 본다).
- **Docker에 남은 것.** 이미지 `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4`와 `turing-1.9.4`, 볼륨 `search-eval-tei-probe-data`와 `rag-latency-probe_tei-data`는 앞 세션들의 것이고 리랭크 기록을 만드는 티켓(14)이 다시 쓴다. 이 세션이 만든 컨테이너와 임시 데이터베이스는 지웠다.
