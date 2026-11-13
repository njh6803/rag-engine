# redirect-outside-worktree: 워크트리 세션의 Bash 리다이렉트가 `../` 상대 경로로 주 체크아웃에 파일을 만든다

**상태:** 열림
**어디로:** `tools/hook_bash_cd_outside.py`(`cd`뿐 아니라 리다이렉트 `>`·`>>`와 `tee`의 대상이 작업 폴더의 상위 `../`로 워크트리 밖을 가리키면 막는다. 새 훅이 더 나으면 `.claude/rules/tools.md`의 새 훅 절차를 따른다)
**승인:** 자체 승인 2026-11-13, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-13-2350-search-eval-02-eval-set-format-validate.md, ADR 불필요

search-eval 02 세션이 검사 출력을 파일로 보내려고 `../../../scratch_gate.log`를 리다이렉트 대상으로 적었다. 워크트리 `.claude/worktrees/<이름>`에서 세 단계를 올라가면 주 체크아웃이라, 그 파일이 주 체크아웃의 루트에 생겼다. 곧바로 지웠고 잃은 것은 없다. 기존 `hook_bash_cd_outside`는 `cd` 대상만 판정하므로 이 길은 막지 못했다. 같은 모양이 `tee`나 `-o <파일>` 옵션에도 있을 수 있어 처방을 정할 때 함께 본다.
