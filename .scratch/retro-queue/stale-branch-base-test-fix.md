# stale-branch-base-test-fix: 기준 브랜치가 이미 고친 부하 시험이 뒤처진 브랜치의 pre-commit에서 빨개져 945초를 버렸다

**상태:** 열림
**어디로:** `tools/sibling_overlap.py`. 커밋 전에 치는 그 도구가 `origin/<기준 브랜치>`에만 있는 커밋 가운데 `tests/`나 `tools/run_checks.py`를 고친 것을 찍고, 커밋 전에 기준 브랜치를 합치라고 알린다(`CLAUDE.md` 환경 함정이 커밋 전에 그 도구를 치게 한다)
**승인:** 자체 승인 2026-11-13, 1회차(더하는 것이라 다섯 번째에 반영한다. 커밋이 만들어지지 않았을 뿐 잃은 작업이 없어 손상이 아니다), 일지 2026-11-13-1716-search-eval-tickets.md, ADR 불필요
