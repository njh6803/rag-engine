# pyright-scratch-vacuous: `uv run pyright <.scratch 폴더>`가 기본 exclude(`**/.*`) 때문에 0개 파일을 보고 초록으로 지나간다

**상태:** 열림
**어디로:** 프로브의 타입 검사를 도는 도구(`tools/` 아래. `--outputjson`의 filesAnalyzed가 0이면 빨강이고, 프로브가 저장소 밖 패키지를 쓰면 그 가상환경의 python을 `--pythonpath`로 받는다) 또는 `docs/agents/issue-tracker.md` 프로브와 근거 절의 한 줄(`.scratch/core/probes/README.md` 끝 문단이 지금 길을 적는다)
**승인:** 자체 승인 2026-11-09, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-09-2125-core-design.md, ADR 불필요

저장소 pyright 설정은 include가 `src, tests, tools`이고 exclude를 적지 않아 기본 exclude `**/.*`가 산다. 그래서 `.scratch` 아래 폴더를 주면 "0 errors"가 나오지만 분석한 파일이 0개다. 프로브 이관 서브에이전트가 이를 발견했고, `sqlalchemy-async/probe.py` 독스트링의 "pyright 0 오류"는 exclude를 비운 임시 설정과 `--outputjson`(filesAnalyzed 1)으로 다시 돌려야 섰다. 같은 서브에이전트는 저장소 `.venv`로 그 프로브를 검사해 "오류가 남아 있다"고 적었는데, 네 패키지가 없어 import를 못 찾은 것이었다.
