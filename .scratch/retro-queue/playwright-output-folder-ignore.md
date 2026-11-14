# playwright-output-folder-ignore: Playwright 플러그인이 작업 폴더에 `.playwright-mcp/`를 만들고 `.gitignore`에 없어 커밋에 실릴 수 있다

**상태:** 열림
**어디로:** `.gitignore`(`.playwright-mcp/` 한 줄)
**승인:** 자체 승인 2026-11-14, 1회차(더하는 것이라 다섯 번째에 반영한다. 지워서 커밋에 실리지 않았으므로 손상이 아니다), 일지 2026-11-14-2356-search-eval-09-public-docs-documents.md, ADR 불필요

search-eval 09에서 법령 내려받기에 Playwright 플러그인을 쓰자 작업 폴더에 `.playwright-mcp/`가 생겼다. `.gitignore`에 그 이름이 없어(`grep -n playwright .gitignore`가 맞는 줄 없이 끝났다) `git add -A`가 실을 수 있었다. 이 세션은 커밋 전에 그 폴더를 지웠고 스테이징을 경로로 좁혀 실리지 않았다.
