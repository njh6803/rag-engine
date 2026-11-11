# open-session-env-button: 인계 열기가 새 세션 화면의 폴더를 환경 버튼으로 고쳐 보낸다

**What to build:** agent-os 저장소의 PR 522(chore: 인계 열기가 새 세션 화면의 폴더를 환경 버튼으로 고쳐 보낸다)를 이 저장소에 옮긴다. 새 세션 화면의 폴더가 `-Folder`와 다르면 멈추고 사람에게 넘기던 것을, 입력창 아래 `환경: <이름>` 버튼에서 이름이 `-Folder`의 마지막 토막인 환경 하나를 스크립트가 골라 고친 뒤 보내게 바꾼다. `tools/open_session.ps1`은 agent-os origin/main의 판으로 통째로 바꾸고, `.claude/skills/open-session/SKILL.md`는 3단계의 폴더 문장과 오류 갈래, 6단계의 보고 칸만 agent-os의 같은 문장에 맞춘다.

**대기열:** 없음

**Status:** done

- [x] `tools/open_session.ps1`의 sha256이 246603e6911452af3ccc0c05969bce2b22dd559ec697e53222df6237ac7d0d7c 다(`sha256sum`으로 손으로 봤다)
- [x] SKILL.md 3단계의 폴더 문장과 오류 갈래, 6단계의 보고 칸이 agent-os의 같은 문장과 같다(agent-os origin/main 5f7e39ed9의 `--word-diff`에서 바뀐 문장을 골라 옮기고, 세 문장을 grep으로 대 봤다). 같은 PR이 서두 문단에서 바꾼 두 곳("고르지 못하면 멈춘다", "저장소나", "3에서 고치고")도 셀프 리뷰가 3단계와 어긋난다고 짚어 사용자의 답으로 함께 맞췄고, 서두의 폴더 문장을 agent-os 판과 grep으로 대 봤다
- [x] 앱의 환경 메뉴에서 이 저장소의 환경 이름이 폴더의 마지막 토막(rag-engine)과 같은지 봤다(agent-os의 `.scratch/harness/probes/composer_env_menu.ps1 -Leaf rag-engine`을 손으로 돌려 `rag-engine` 라디오 항목과 폴더 `C:\project\rag-engine`을 봤다)
- [x] 앱의 마지막 폴더를 다른 저장소로 둔 채 옮길 수 없는 슬래시 명령 프롬프트로 send를 쳐서 `folder-fixed=`, `folder=`, `held=`가 차례로 나왔고, 끝난 뒤 마지막 폴더를 이 저장소로 되돌렸다(2026-11-11 손으로 돌렸다. 프로브의 `-Pick agent`로 마지막 폴더를 agent로 두고 워크트리 사본의 스크립트에 `-Folder C:\project\rag-engine`을 줬다. 출력은 `folder-fixed=C:\project\agent -> C:\project\rag-engine`, `folder=C:\project\rag-engine`, `held=`였고, 스크립트가 고른 환경으로 마지막 폴더가 rag-engine이 된 것을 프로브로 다시 봤다)

## Comments

- 2026-11-11 셀프 리뷰. `tools/open_session.ps1`의 주석이 드는 프로브(`.scratch/harness/probes/composer_folder.ps1`, `composer_env_menu.ps1`), harness 티켓 `open-session-selects-repo-folder`, 대기열·일지 번호는 agent-os 저장소의 것이고 이 저장소에는 없다. 해시를 지키려고 스크립트는 고치지 않았다(스킬 사본은 머리 주석이 같은 말을 한다).
- 남긴 것(agent-os 원문과 같은 상태라 고치지 않았다): 읽은 경로에 `-Folder`가 섞이면 환경을 고르지 않고 멈추는 갈래를 3단계가 따로 적지 않는다. `held=`로 끝나면 6단계가 "부탁 한 줄이 곧 보고"라 `folder-fixed=`(앱의 마지막 폴더가 바뀐 것)가 보고에서 빠진다. 환경을 고친 뒤 `sent=`까지 가는 길은 이 티켓에서 돌려 보지 않았다.
