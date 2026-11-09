---
paths:
  - "tests/**"
---

# tests 규칙

원천은 `pyproject.toml`의 pytest 설정, `tests/conftest.py`, `docs/constitution/operations.md`의 검증 절이다. 코드와 다르면 코드를 고치거나 ADR을 남긴다. 테스트 이름의 규칙은 `CODING_STANDARDS.md`가 원천이다.

- 계약 시험은 `tests/contract/`에 둔다. 공식 MCP SDK의 클라이언트로 서버에 HTTP 접속해 본다(operations.md 검증, 원칙 VII). 앱 객체를 직접 부르거나 SDK의 메모리 안 연결로 대신하지 않는다. 클라이언트가 실제로 보는 HTTP 경로, Host 판정, 세션 관리자의 수명이 거기서만 드러난다.
- import 모드가 importlib이라 `__init__.py` 없이 같은 파일명이 여러 디렉터리에 공존한다. 새 테스트 디렉터리를 만들면 그 경로를 잡는 `.claude/rules/*.md`의 `paths`도 넓힌다. 지침 검사는 죽은 glob만 잡고 빠진 경로는 못 잡는다.
- 비동기 테스트는 `async def`로 쓴다. pytest-asyncio가 auto 모드라 데코레이터도 마커도 필요 없고 `asyncio.run()`을 직접 부르지 않는다.
- `RuntimeWarning`은 에러다. `await`를 빼먹은 코루틴이 경고만 내고 초록으로 지나가지 않게 하기 위해서다. 경고 전부를 올리지는 않는다.
- skip은 `conftest.py`가 세션 실패로 만든다(원칙 I). 환경이 없으면 skip이 아니라 실패하게 쓴다.
- `conftest.py`가 stdout을 UTF-8로 고정하고, 저장소를 가리키는 `GIT_*` 환경(`GIT_DIR` 등)을 벗긴다. pre-commit이 워크트리에서 훅을 돌리면 git이 그 값을 내보내, 임시 디렉터리에 `git init`하는 테스트가 저장소를 재초기화한 일이 agent-os에서 있었다. 그래서 테스트의 `git init`은 `tmp_path`에 해도 된다.
- `tools/`의 순수 함수는 `tests/tools/`에서 검증한다. `src/` 미러링의 유일한 예외다. 저장소 상태를 보는 검사에는 이 저장소가 지금 통과함을 재는 테스트(`test_이_저장소의_…`)와 위반을 잡는 변이 테스트(`test_…을_잡는다`)를 하나씩 둔다. 훑은 범위가 비면 실패하게 한다. 경로를 잘못 가리키면 위반 0으로 조용히 초록이기 때문이다.
- 실제 프로세스·스레드·기한을 재는 시간 단언은 상한을 그 시험만 홀로 돌린 시간의 넉넉한 배수로 둔다. pre-commit 러너는 pytest를 xdist로 나눠 돌리고 다른 세션의 커밋과 겹치기도 한다.
- 테스트는 CI의 리눅스에서도 돈다. 윈도에만 있는 것에 기대지 않고, 리눅스만 요구하는 것(시험이 쓰는 git 훅 스크립트의 실행 권한)을 빠뜨리지 않는다. 이 PC에서 초록인 것은 리눅스에서 돈다는 증거가 아니다.
- `tools/check_*.py`는 CLI 진입점(`main`)을 subprocess로 한 번 실제로 부르는 테스트를 둔다. 저장소 밖 픽스처로 알려진 빨강을 만들고 그 빨강이 출력에 있는지 본다. 순수 함수 테스트만 있으면 배관이 조용히 비어도 초록이다.
