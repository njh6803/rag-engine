"""이 브랜치가 새로 매긴 번호와 고친 파일을 형제와 대조한다.

커밋 직전에 대조한다(대기열 48·115).

형제는 셋이다. 이미 병합된 기준 ref(`tools/base_rule.py`: `hotfix/*` 는 `origin/main`, 그 밖은
`origin/dev` 가 있으면 그것, 없으면 `origin/main`. 기준이 아닌 쪽 오래 사는 브랜치도 형제로 함께
견준다), 아직 병합되지 않은 열린 PR의 head, 아직 커밋되지 않은 같은 저장소의 다른 워크트리다.
기준 ref와 워크트리만 보던 손 대조는
아직 열린 PR이 먼저 가져간 번호와 다섯 번 부딪혔다(대기열 115). 클라우드 세션에서는 형제가
워크트리가 아니라 다른 세션의 열린 PR이라 손 대조가 보는 것이 main뿐이다(일지 2026-10-07-09).

번호는 둘이고, 형제가 새로 매긴 번호를 이 브랜치도 새로 매겼으면 겹침이다.

- ADR 번호: `docs/adr/NNNN-*.md`의 `NNNN`. 같은 번호에 다른 파일이면 겹침이다.
- 헌법 판: `docs/constitution/README.md`의 `**Version**: X.Y.Z`.
  둘이 같은 판으로 올렸으면 겹침이다.

harness 티켓(`.scratch/harness/issues/<slug>.md`)은 번호가 아니다. 세션이 영어 소문자로 시작하는
이름을 직접 지어, 형제와 나눠 쓰는 순번이 없다(retro-queue-per-item 07, ADR 0037 "번호"의 개정).
이 도구가 harness 티켓에서 읽던 세 자리 번호와 다음 빈 번호는 그 전환으로 뺐다. 옛 45장의 파일
이름(`NNN-<slug>.md`)도 읽지 않는다. 이름을 짓는 규약은 `docs/agents/issue-tracker.md`가 원천이다.

일지는 번호가 아니다. 이름이 `docs/journal/<날짜>-<HHMM>-<슬러그>.md`이고 앞부분은 그 세션이
일지를 만든 로컬 시분이라 형제와 나눠 쓰는 순번이 없다(ADR 0045 결정 7). 옛 이름
`<날짜>-<NN>-<슬러그>.md`는 전환일까지 만든 일지의 것이다. 이 도구가 일지에서 보는 것은 둘이다.
이 브랜치가 더한 줄의 일지 인용이 가리키는 파일이 있는가(`dangling_cites`)와, `--journal`이 내는
이 브랜치의 일지다. 같은 분의 겹침과 전환일 뒤의 순번 꼴은 `tests/test_journal_names.py`가 본다.

회고 반영 대기열(`.scratch/retro-queue/<ID>.md`)은 번호가 아니라 항목의 이름이 식별자라 번호로
읽지 않는다. 항목 파일도 다른 파일처럼 함께 고친 파일에는 든다.

"새로"는 이 브랜치와 기준 ref의 merge-base에 없다는 뜻이다. 열린 PR과 워크트리는
그 merge-base와 기준 ref 어디에도 없는 번호만 그 형제의 것으로 본다. 그래서 기준 ref가
이미 가진 번호는 그 줄에만 한 번 나온다. 이 브랜치의 새 번호에서는 기준 ref에 같은 번호·같은
파일로 이미 든 것도 뺀다. 쌓아 올린 아래 PR이 squash로 병합된 뒤 main을 들이지 않은
브랜치에서 그 번호는 공유한 이력인데, 새 번호로 세면 main에 있는 파일을 옮기라고 한다. 헌법 판은
내용을 가를 수 없어 빼지 않는다. 합치기를 커밋하기 전(`MERGE_HEAD` 가 있다)에는 합칠 머리(main 이
아니어도, octopus 면 모두)의 번호를 이 브랜치 밖의 번호로 세고, 그와 같은 파일을 이 브랜치의 새
번호에서 뺀다. merge-base 를 `git merge-base <기준 ref> HEAD MERGE_HEAD`(`tools/check_ticket.py` 의
꼴)로 구하면 합칠 머리가 main 일 때 main 자체가 되어, 그 겹침과 main 이 함께 고친 파일까지 사라져
그러지 않는다 (그 꼴로 바꾼 판에서 이 도구의 시험 둘이 빨개진 것을 손으로 봤다, harness 티켓 024).
이 브랜치는 작업 트리(커밋하지 않은 변경과 미추적 파일)를 읽는다. merge-base에서 두 자리(ADR,
헌법 판) 가운데 하나라도 비면 경로가 어긋난 것으로 보고 2로 끝난다(조용히 겹침 없음이 되지 않게).
일지는 그 자리에 들지 않는다. 번호를 읽지 않아 비어도 겹침 없음이 되는 일이 없고, 일지 폴더가
비었거나 순번 일지가 하나도 없는 merge-base에서도 대조가 멈추지 않는다. 대기열도 그 자리에 들지
않는다. 대기열이 폴더가 된 뒤에는 옛 표 (`.scratch/retro-queue.md`)가 어느 브랜치의 merge-base에도
없어, 넣으면 그 뒤에 딴 모든 브랜치에서 대조가 2로 멈춘다.

열린 PR은 GitHub REST(`gh api repos/<owner>/<repo>/pulls?state=open`)로 읽는다. `origin`이
github.com이 아니거나 `gh`가 없거나 실패하면 `refs/pull/N/merge`가 있는 PR을 열린 것으로 본다.
2026-10-07에 이 클라우드 컨테이너에서 손으로 봤다. `gh pr list`는 GraphQL이 막혀 HTTP 403이었고
`gh api`의 REST는 열렸다. `git ls-remote origin 'refs/pull/*'`에는 PR 160개의 head ref와 merge
ref 하나(열린 #158)가 있었고, #158은 main과 충돌한 뒤에도(`mergeable_state: dirty`) 옛 base의
merge ref가 남아 있었다. 로컬 Windows에서는 아직 돌리지 않았다. head가 이 브랜치의 HEAD에 이미
들었거나 원격의 같은 이름 브랜치와 같은 PR은 이 브랜치 자신의 PR이라 형제가 아니다(앞의 것은
푸시 전의 새 커밋, 뒤의 것은 amend·rebase 뒤 아직 밀지 않은 때).

함께 고친 파일도 알린다. 이 브랜치가 merge-base 뒤에 고친 파일과 형제가 자기 merge-base
뒤에 고친 파일이 겹치면, 나중에 병합하는 쪽에서 글자 충돌이 날 수 있다. 이것은 종료
코드를 바꾸지 않는다. 형제와 main의 merge-base가 이 클론에 없으면(얕은 클론) 그 형제의 고친
파일만 "알 수 없다"로 두고 번호는 그대로 대조한다. 형제 워크트리의 고친 파일에서는 디스크 사본이
기준 ref와 같은 파일을 뺀다. main을 합치고 커밋하기 전인 형제의 작업 트리에는 main의 변경이
보여, 그 형제의 커밋이 바꾸지 않은 두 파일을 함께 고친 파일로 냈다(대기열 294, 일지 2026-10-16-20).

열린 PR의 head는 원격에 `refs/pull/<N>/head`가 있는 것만 그 ref로 받는다. gh가 열린 PR로 읽어도
PR을 연 지 몇 분 안에는 그 ref가 아직 없어, 그 ref를 받는 fetch가 128로 끝나 대조 전체가 2로
멈췄다(대기열 288, 일지 2026-10-16-18). 그 뒤에도 head 커밋이 이 클론에 없는 PR은 커밋을 sha로
받는다(`git fetch origin <sha>`). 같은 저장소에서 연 PR이면 head 브랜치의 끝이라 받아진다. 로컬
원격에서 ref 없이 브랜치만 민 PR을 sha로 받는 것과, 원격에 객체가 없는 커밋을 받지 못해 그 PR만
빠지는 것은 시험이 밟는다. GitHub 원격에서는 재지 않았다. 그래도 받지 못한 PR만 형제에서 빼고
출력의 "받지 못해 대조에서 뺀 열린 PR" 줄로 알린다. 종료 코드는 남은 형제로 정한다.

이 브랜치가 고친 파일(함께 고친 파일, 헌법 판, 카나리아, `--move` 가 쓰는 것)은 merge-base 뒤에
고친 파일 가운데 main 과 내용이 다른 것과 미추적 파일이다. main 을 합치다 충돌을 풀고 커밋하기
전에는 merge-base 가 옛 자리에 머물러, merge-base 와의 차이만 세면 main 이 들여온 파일이 모두
섞인다. 그 상태에서 친 대조가 main 의 규칙과 스킬을 카나리아 누락으로 알리고 1로 끝났다(일지
2026-10-15-15). 헌법 README 가 이 브랜치가 고친 파일이 아니면 디스크의 판도 이 브랜치의 새 판으로
세지 않는다. 같은 상태에서 main 이 올린 판을 이 브랜치의 판으로 읽어 main 과 같은 판으로 겹쳤다고
1로 끝났다.

HEAD가 닫힌 PR의 head와 같은 형제 워크트리는 커밋하지 않은 변경(그 HEAD 뒤의 변경과 미추적
파일)만 고친 파일로 견주고, 형제 줄에서는 그 수만 접어 찍는다(대기열 194). 함께 고친 파일 서른여덟
줄 가운데 서른다섯 줄이 형제 워크트리의 것이라 열린 PR의 줄이 묻혔다(일지 2026-10-13-18). 이 판을
들일 때 같은 꼴로 다시 친 대조에서는 형제 워크트리의 줄 서른일곱 가운데 서른여섯이 PR이 닫힌
워크트리의 것이었다(손으로 봤다, 일지 2026-10-13-30). 그 커밋은 이미 병합됐거나, 병합 없이 닫혀
앞으로도 병합되지 않아 충돌 후보가 아니다. 그래서 병합과 닫힘을 가리지 않는다. 닫힌 PR은 열린
PR을 읽으려고 이미 치는 `ls-remote`의 `refs/pull/*/head` 가운데 열린 PR이 아닌 것이다. 병합 여부를
따로 물으면 `gh api …/pulls?state=closed --paginate`가 2.2~3.5초, `gh pr list --state merged`가
1.6~2.0초를 더 썼고, 그 `ls-remote`는 0.6~0.7초였다(2026-10-13 이 저장소의 PR 217개에서 세 번씩,
`.scratch/harness/probes/sibling_overlap_merge_cost.sh`). 병합 없이 닫힌 PR은 그때 0개였다.
번호는 접지 않고 그대로 대조한다.

다음 빈 번호는 찍지 않는다. 찍던 것은 harness 티켓의 세 자리 번호뿐이었고(대기열 157·182),
티켓이 번호 없는 이름이 되며 뺐다. ADR 번호는 겹친 뒤 "옮길 번호"로 받고, 일지의 번호는 없다(위).

형제가 쓴 가장 높은 헌법 판은 늘 찍는다(대기열 199). 판을 올리기 전의 대조는 겹침을 알리지
못해, 올린 뒤 다시 친 대조가 형제가 먼저 매긴 같은 판을 알렸다. main은 가진 판, 다른 형제는
새로 매긴 판이 후보이고, 판은 글자가 아니라 수로 견준다. 다음 판은 고르지 않는다(아래).

헌법 파일(`principles.md`·`tech.md`·`operations.md`)을 merge-base 뒤에 고쳤는데 이 브랜치가
판을 새로 매기지 않았으면 알린다(대기열 224). `principles.md` 거버넌스는 원칙 변경을 major, 절
추가를 minor, 문구 수정을 patch로 올리고, 판을 올리지 않은 변경은 뒤에 소급했다. 2.4.0과 2.5.1이
그런 PR 열셋을 묶었고(`docs/constitution/README.md`), `operations.md`를 고치고 올리지 않은 것을 셀프
리뷰가 잡았다(일지 2026-10-13-18).

main 이 이 브랜치 몫으로 비워 둔 헌법 판은 이 브랜치가 올린 판으로 센다(대기열 279). 함께 돌던
형제가 이 브랜치가 매긴 판을 건너뛰어 더 높은 판으로 먼저 병합하면, 그 형제는 헌법 README 에
"<판>은 함께 돌던 형제 브랜치(<백틱으로 감싼 이 브랜치의 이름>)가 먼저 매겨 비워 두었다" 를 한 줄에
하나씩 적는다. 그 뒤 main 을 합친 이 브랜치는 판 줄을 main 의 판으로 두고 그 문장을 지운다. 그 판
줄은 합치기를 커밋한 뒤 merge-base 와 같아 판을 올리지 않고 헌법 파일을 고쳤다고 1로 끝났고(합칠
때마다, 두 번. 일지 2026-10-15-19), 합친 main 이 판 줄을 바꿨으면 커밋하기 전에는 main 과 같아 main
과 같은 판으로 겹쳤다고 1로 끝난다. 그래서 판 줄이 merge-base 나 main 의 것이고 헌법 README 를
고쳤을 때, 이 브랜치의 판 줄이 main 의 판 줄과 같고 main 의 README 에 지금 브랜치의 이름으로 비워
둔 판의 문장이 있는데 이 브랜치의 README 에는 없으면 그 판을 이 브랜치의 새 판으로 센다. 판을 올린
까닭은 헌법 README 가 아니라 그 변경의 ADR 이력이나 일지에 적는다(retro-queue-per-item 06. 헌법
README 의 이력 문단을 더하던 옛 신호는 그 문단이 `docs/constitution/history.md` 로 옮겨 가 기록이
되면서 없어졌다). 판 줄을 비워 둔 판으로 낮추는 길은 두지 않는다. 병합하면 main 의 판이 내려간다.

바꾼 하네스 파일의 카나리아도 본다(대기열 235). 이 브랜치가 merge-base 뒤에 고친 스킬 본문
(`.claude/skills/*/*.md`. `SKILL.md` 가 Read 로 열게 하는 하위 파일도 카나리아의 하위 파일 갈래가
원천으로 받는다, harness 027), 규칙(`.claude/rules/*.md`), 서브에이전트(`.claude/agents/*.md`)
가운데 지금 있는 것마다, 그 경로를 `source` 로 든 카나리아
명세(`.scratch/**/probes/canary/*.toml`)를 이 브랜치가 하나도 고치지 않았으면 알린다. 바꾼 하네스는
새 `claude -p` 세션에서 불러 보고 그 명세의 `# 최신 결과:` 줄을
고친다(`docs/constitution/operations.md` 환경 규약 상세). `next-session` 의 병합 절차(지금
`merge.md`)를 바꾸고 카나리아를 돌리지 않은 채 셀프 리뷰 두 축과 PR 직전 리뷰를 지났고, 회고에서 그
절을 다시 읽다 찾았다(일지 2026-10-13-38). 헌법 판처럼 커밋 전에 고칠 누락이라 이것도 1로 끝난다.
다만 계정 한도로 카나리아를 돌리지 못하면 결과 줄을 고칠 수 없다. 그 갈래는 같은 절의 계정 한도
항목대로 사전 확인만 돌리고 이 알림이 남은 채 커밋한다고 출력이 함께 말한다(셀프 리뷰 명세 축, 일지
2026-10-15-15).
rag-engine 에서는 카나리아 명세(`CANARY_SPECS`)가 하나도 없으면 이 판정을 끈다. 카나리아 도구와
명세를 복사하지 않아(킥오프 7단계), 알림이 시키는 일(불러 보고 결과 줄 고치기)을 할 길이 없다. 첫
명세가 생기면 그 저장소의 규칙(명세가 없는 하네스 파일도 알린다)대로 다시 돈다.

이 브랜치가 더한 줄의 일지 인용도 본다(대기열 254). 이 브랜치가 고친 파일에서 merge-base 와 main 의
판에 글자 그대로 있는 줄을 뺀 줄의 `일지 <날짜>-<NN 또는 HHMM>`(목록 꼴 `일지 A·B` 는 하나하나)이
merge-base, main, 형제(열린 PR, 형제 워크트리의 커밋하지 않은 일지까지), 이 브랜치의 작업 트리
어디에도 없는 일지를 가리키면 알린다. 인용은 `docs/journal/<인용>-*.md` 로 푼다. 접두 뒤의
하이픈이 `2026-11-06-14` 와 `2026-11-06-1432-…` 를 가르고, 옛 인용 `2026-10-19-21` 과 새 인용
`2026-11-06-1432` 이 같은 규칙 하나로 풀린다. 번호를 이 도구로 받기 전에 짐작한 번호를 런북
파일에 적었다가 손으로 고쳤고(일지 2026-10-13-66), 짐작한 번호(60)를 카나리아 명세에 인용한 채
셀프 리뷰까지 갔다(일지 2026-10-13-67). 뒤의 것은 그때 열린 PR #233 의 일지 번호와 같아 이 판정도
지나갔을 것이고(못 보는 것의 뜻이 다른 일지), 그 PR 이 번호를 64로 옮긴 뒤에야 없는 번호가 되어
걸린다. 판을 올리지 않은 헌법 파일처럼 커밋 전에 고칠 것이라 1로 끝난다. 인용 블록(`>` 로 시작하는
줄)은 사용자 프롬프트의 원문이고, 코드 스팬과 펜스 안은 옮기기 전의 옛 번호를 적은 기록이나 도구의
출력이라 보지 않는다. `origin/main`(`df705c17`)의 추적 파일 전체에서 `일지` 인용의 번호 1389 가운데
없는 번호는 일곱이었다. 코드 스팬 둘과 인용 블록 하나를 빼면 일지가 큰따옴표 안에 옮긴 도구 출력
하나와 이 도구의 시험 데이터 셋이 남았고, 모두 main 의 줄이라 이 판정에 걸리지
않는다(`.scratch/harness/probes/journal_cite_scan.py`). 줄을 가르는 git 호출은 없는 번호가 든
파일에서만 친다.

`--move` 는 "옮길 번호" 를 실제로 옮긴다(대기열 249). 형제가 더 높은 번호를 들고 먼저 병합해, 한
세션에서 받은 번호를 두 번 옮기고 그때마다 그 번호의 인용(다섯에서 아홉)을 손으로 고쳤다(일지
2026-10-13-59·2026-10-13-61). ADR 은 파일 이름을 바꾸고, 이 브랜치의 변경과 미추적 파일 안의
인용을 바꾼다. 인용의 꼴은 `ADR NNNN` 과 목록 속 `·NNNN`, ADR 의 파일 이름(`NNNN-…`)과 색인의
`[NNNN]`이다. 일지는 번호를 옮기지 않는다. `대기열 N` 인용과
대기열 항목은 번호가 아니라 이름이라 옮기지 않는다. ADR 의 꼴은 `.claude/rules/adr.md` 의 번호
항목과 같다. 모든 꼴을
한 번에 바꿔, 차례대로 옮기는 사슬(03→05, 05→07)의 03 이 07 까지 가지 않는다. 인용 블록(`>` 로
시작하는 줄)은 옮기지 않는다. 일지는 사용자 프롬프트를 원문으로 인용하는데(`> 사용자:`), 이
브랜치의 일지를 옮긴 첫 실행이 그 원문의 일지 번호까지 바꿨다(일지 2026-10-15-15). merge-base 나
main 의 판에 글자 그대로 있는 줄도 옮기지 않는다. 그 줄의 같은 번호는 상대를 가리킨다
(`.claude/rules/adr.md`). main 을 합치다 같은 번호의 줄 둘을 남긴 채 옮기면 main 의 색인
행까지 바뀌었다(PR 직전 버그 축). BOM 으로 시작하는 파일은 BOM 을 떼고 바꾼 뒤 다시 붙인다. UTF-8
로 읽지 못하는 파일은 두고, 옮길 자리에 무엇이 있으면 아무것도 고치지 않고 2로 끝난다. 고치다 멈추면
고친 것을 거꾸로 되돌리고 2로 끝난다. 되돌리지 못한 것이 있으면 그것을 들고 `--move` 를 다시 치지
말라고 한다(다시 치면 이미 옮긴 인용이 사슬을 따라 한 번 더 옮겨진다). 글을 먼저 고치고 이름을
바꾸며 인덱스는 건드리지 않는다. 그래서 출력은 이름을 바꾼 파일을 `옛 → 새` 로 따로 찍고, 옛 이름의
지움까지 스테이지하라고(`git add -A`) 말한다. 옮기지 못한 꼴(아래 못 보는 것)도 함께 말한다.
origin 이 GitHub 이고 브랜치 위이면 이 브랜치를 head 로 든 열린 PR 의 본문을 `gh api`(REST)로 읽어
같은 꼴로 대 보고, 인용이 바뀌는 PR 마다 옮긴 본문을 임시 파일에 쓴 뒤 그 파일을 올리는 명령 한
줄을 찍는다(대기열 376). 본문은 올리지 않는다. 번호를 옮긴 뒤 열린 PR 본문에 옛 일지 경로가 남아
claude-review 가 짚은 것이 세 번이었다(일지 2026-10-13-01·2026-10-13-64·2026-10-20-01). 옮긴
뒤에는 다시 대조해 찍고 그 종료 코드로 끝난다.

`-h`·`--help` 는 쓰임과 종료 코드를 찍는다. 2로 끝나면 stderr 에 할 일(번호를 손으로 고르지
않는다)을 함께 싣는다(대기열 251). 시작 경로만 받던 때 `--help` 를 경로로 읽어 2로 끝났고, 2일 때
할 일은 번호를 받는 두 스킬 가운데 `code-review` 에만 있었다(일지 2026-10-12-32·2026-10-13-61).

쓰임: `uv run python tools/sibling_overlap.py [저장소 안의 경로] [--move | --journal]`. 먼저
`origin`의 main·dev(이 클론이 dev 추적 ref를 가졌을 때)와 열린 PR의 head를 fetch한다
(기준 ref가 움직인다). 종료 코드는 번호 겹침도,
판을 올리지 않고 고친 헌법 파일도, 카나리아 명세를 고치지 않고 바꾼 하네스 파일도, 어디에도 없는
일지를 가리킨 인용도 없으면 0, 있으면 1, 대조나 옮기기를 끝내지 못하면(git 실패, 원격을 읽지
못함, 번호의 자리가 빔, 옮길 자리에 무엇이 있음, 인자가 틀림) 2다. 1이면 출력대로 고친다. 겹쳤으면
이 브랜치가 비켜 간다. 출력의 "옮길 번호"는 겹친 종류의 이 브랜치 새 번호 전부를 차례를 지켜
형제들의 최대값 뒤로 붙인 것이다. 헌법 판은 고르지 않는다. 올림의 종류(major·minor·patch)는 바뀐
내용이 정하고, 형제가 쓴 가장 높은 판보다 높으면 된다.

`--journal` 은 대조하지 않고(fetch 도 하지 않는다) 이 브랜치의 일지 경로를 한 줄로 찍는다.
merge-base 뒤에 더한
일지(`git diff --merge-base <기준 ref> --name-only --diff-filter=A -- docs/journal/`)와 커밋하지
않은 새 일지(미추적 파일과 스테이지한 새 파일) 가운데 날짜·시각이 가장 늦은 것이다. 같은 날 옛
꼴(`-12-`)과 새 꼴(`-0930-`)이 섞였으면 새 꼴이 늦다. 이름순으로 고르면 `-12-` 가 `-0930-` 보다 뒤에
서서 옛 일지가 걸린다. 없으면 stderr 에 까닭을 싣고 1로 끝난다. main 을 합친 뒤에는 merge-base 가
main 의 끝으로 옮겨, main 에서 들어온 남의 일지는 들지 않는다.

못 보는 것:
- 이 클론에 `origin/dev` 의 추적 ref 가 없으면 원격에 dev 가 있어도 main 만 대조한다. 받은 적 없는
  클론은 dev 가 없는 저장소와 같다(`test_dev의_추적_ref가_없으면_…`가 고정한다).
- merge ref로 가릴 때(`gh`를 쓰지 못할 때), 열 때부터 main과 충돌한 PR. 웹 검색 요약이
  그런 PR에는 merge ref가 없고 merge ref는 GitHub이 문서로 약속하지 않은 기능이라고 했다
  (drone 포럼 글, 원문은 이 컨테이너의 egress가 막아 열지 못했다). 재지 않았다. 재려면 이
  저장소에 충돌하는 PR을 하나 열어야 한다. 그 PR의 head에 있는 워크트리는 닫힌 PR의 것으로 접혀
  커밋한 변경을 견주지 않는다.
- PR이 닫힌 워크트리 가운데 HEAD가 그 head와 다른 것. head 뒤에 커밋을 더한 워크트리는 새 일이라
  접지 않는 것이 맞지만, head까지 따라가지 않은(head의 조상에 남은) 워크트리도 접지 않아 이미
  병합된 커밋이 함께 고친 파일에 나온다.
- 헌법 판을 merge-base의 판에서 바꿨는지만 본다. 그보다 낮게 고쳐도, 올림의 종류가 바뀐 내용에
  맞지 않아도(원칙을 바꾸고 patch로 올려도) 지나간다. 헌법 README의 판 줄 밖 문장(색인)과 세 파일
  밖의 새 헌법 파일은 고쳐도 알리지 않는다.
- main 이 비워 둔 헌법 판은 위의 꼴 그대로 적은 문장만 읽는다. 지금 브랜치의 이름이 그 문장의 이름과
  다르면(이름을 바꿔 달았거나 분리 HEAD) 판을 올리지 않은 것으로 본다. 이 브랜치가 문장을 지우지
  않고 그 꼴이 깨지게 고쳐도 그 판을 가져간 것으로 센다. 문장을 지운 까닭이 판을 가져가려는 것인지는
  보지 않는다. main 을 합치기 전이라 판 줄이 main 과 다른 브랜치는 이 신호를 쓰지 않는다.
- 일지 인용 가운데 `일지` 낱말 없이 든 번호, 목록의 줄인 꼴(`일지 2026-10-13-66·67` 의 67), 코드
  스팬·펜스·인용 블록 안의 인용, merge-base 나 main 의 판에 글자 그대로 있는 줄(옮겨 오거나 되돌린
  줄), 지운 파일과 UTF-8 로 읽지 못하는 파일, 커밋 메시지와 PR 본문의 인용. 파일이 있으면 뜻이 다른
  일지를 가리켜도 지나간다. 같은 분의 일지 둘이 인용 하나를 둘로 푸는 것도 여기서는 지나간다
  (`tests/test_journal_names.py` 가 본다). 거꾸로 일부러 없는 일지를 쓴 시험 데이터(문자열)도
  인용으로 읽어 알린다. 그래서 이 도구의 시험은 임시 저장소에 없고 이 저장소에 있는 일지를 쓴다.
- 푸시했지만 PR을 열지 않은 브랜치, 다른 기계·다른 클라우드 세션의 커밋하지 않은 변경.
- main을 이미 들여 작업 트리 안에서 같은 번호가 둘이 된 것. 둘 다 merge-base에 있거나 merge-base에
  든 번호와 같아 "새로"가 아니다. ADR은 `tools/check_adr_pointers.py`가 본다. 일지는 번호가 없고
  같은 분의 겹침을 `tests/test_journal_names.py`가 본다.
- `--move` 가 옮기지 못하는 인용. 줄인 꼴("일지 03"), 꼴의 낱말 없이 든 번호("새로 연 것은
  250·251"), 커밋 메시지와 PR 제목, 번호 뒤의 조사(받침에 따라 갈리는 을·를), 심볼릭 링크인
  파일(따라가 쓰지 않는다)은 그대로다. PR 본문은 옮긴 판과 명령만 내고 올리지 않는다. 인용 블록에서
  `>` 없이 이어지는 줄은 옮긴다. 거꾸로 같은 꼴이면 뜻을 가리지 않고 이 브랜치의 번호로 읽어 옮긴다.
  코드 스팬과 펜스 안도 옮긴다. 파일 이름 인용(`docs/journal/…`)이 대개 그 안에 있어서다. 그래서
  이 브랜치가 더하거나 고친 줄에서 형제의 같은 번호를 가리킨 인용도 옮긴다. 거꾸로
  이 브랜치의 번호를 가리켰어도 merge-base 나 main 의 판에 같은 글자의 줄이 있으면 둔다.
- `--move` 의 PR 본문 확인. origin 이 GitHub 이 아니거나 분리 HEAD 면 묻지 않고, 포크에서 연 PR(head
  의 owner 가 다르다)은 걸리지 않아 아무것도 찍지 않는다. gh 가 없거나 실패하면 읽지 못했다는 한
  줄만 낸다. 클라우드 세션에서 REST 가 된다는 것(`.claude/rules/tools.md`)에 기댈 뿐 그 길로 돌려
  보지는 않았다. PR 본문에는 merge-base·main 의 줄을 두는 판정이 없어, 같은 꼴이면 형제를 가리킨
  번호도 옮긴 판에 든다. PR 제목은 읽지 않는다. 옮긴 판은 읽은 때의 본문이라 그 뒤의 고침이 들지
  않고, 올리기 전에 지금 본문과 견주는 것은 출력 줄의 말일 뿐 도구는 견주지 않는다.
- 인덱스. 대조는 작업 트리를 읽으므로, `--move` 뒤 옛 이름의 지움을 스테이지하지 않고 커밋해 옛
  파일이 커밋에 남아도 0으로 끝난다.
- 카나리아 명세가 고친 단락을 묻는지. 그 하네스 파일을 원천으로 든 명세 하나를 이 브랜치가
  고쳤으면 지나가고, 명세를 고친 뒤 하네스를 다시 고친 것도 지나간다. `CLAUDE.md`, 스킬 폴더의
  `SKILL.md` 밖 파일, 훅 설정(`.claude/settings.json`)은 보지 않는다. 읽지 못한 명세(TOML 오류,
  글자가 아닌 `source`)는 원천이 없는 것으로 보아, 그 명세만 고친 하네스 파일도 알린다.
- 함께 고친 파일의 어느 줄이 겹치는지. 파일 이름만 견준다.
- 형제 워크트리의 미추적 파일이 기준 ref의 같은 경로와 글자가 같은 것. 미추적 파일은 main과
  견주지 않고 늘 고친 파일로 센다. main을 합치는 중에 main이 들여온 파일은 인덱스에 올라 추적
  파일이라 빠진다. 미추적으로 같은 것은 손으로 옮겨 둔 것, 합친 뒤 `git restore --staged`로 내린
  것, 형제가 새로 쓴 파일을 main이 뒤에 같은 글자로 더한 것 같은 경우다.
- head 커밋을 받지 못해 뺀 열린 PR. 그 PR과의 번호 겹침과 함께 고친 파일을 보지 않고, 남은 형제로
  0으로 끝날 수 있다. 기다렸다 다시 받지 않는다. 다시 치는 것은 출력을 읽은 사람이다. 포크에서
  연 PR은 head 브랜치가 origin에 없어, ref가 생기기 전에 sha로 받아지는지 재지 않았다. 받지 못하면
  이 갈래로 간다. sha로 받는 fetch가 시간 제한을 넘기면 그 PR만 빼지 않고 대조 전체가 2로 끝난다.
  `ls-remote`에 있던 `refs/pull/<N>/head`가 fetch 전에 사라지면(그 사이 PR이 닫히거나 원격이 잠깐
  실패하면) 그 ref를 main과 한 번에 받는 fetch가 실패해, sha 길로 내려가지 않고 대조 전체가 2로
  끝난다. 다시 치면 그 PR은 열린 PR이 아니거나 ref 없는 PR의 길로 간다.
- 이 브랜치가 고쳤어도 main 과 내용이 같아진 파일(main 의 같은 변경을 손으로 옮긴 것). 이 브랜치가
  고친 파일로 세지 않는다.
- 가장 높은 헌법 판을 받은 뒤에 다른 세션이 같은 판을 쓰는 것. 그 순간의
  형제만 본다. 그 뒤의 겹침은 커밋 직전의 대조가 잡는다. 이 브랜치의 판이 형제가 쓴 판보다 낮은
  것은 그 줄에 찍히기만 하고 종료 코드를 바꾸지 않는다. 그 형제가 판을 새로 올렸으면 둘이 같은 판
  줄을 고쳐, 나중에 병합하는 쪽에서 글자 충돌로 드러난다.
- harness 티켓의 이름. 번호가 아니라 이름이라 겹침을 읽지 않는다. 같은 이름의 티켓을 두 세션이
  짓는 것은 함께 고친 파일로만 나온다. 기능 폴더(`.scratch/<slug>/issues/`)의 두 자리 번호도 한 기능
  안에서 한 세션이 매겨(`to-tickets`) 보지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import NoReturn, Protocol
from urllib.parse import quote

if __package__ in (None, ""):  # 스크립트로 부르면 저장소 루트가 import 경로에 없다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import base_rule  # noqa: E402

REMOTE = base_rule.REMOTE
JOURNAL_DIR = "docs/journal"
ADR_DIR = "docs/adr"
CONSTITUTION = "docs/constitution/README.md"
# 판을 올려야 하는 헌법 파일. 어느 변경이든 판을 올린다(`principles.md` 거버넌스의 semver)
CONSTITUTION_TEXTS = frozenset(
    f"docs/constitution/{name}.md" for name in ("principles", "tech", "operations")
)

# 일지 파일 이름. 날짜 뒤가 시각 네 자리(`2026-11-06-1432-…`)이거나 옛 순번 두 자리
# (`2026-10-19-21-…`)다. 규약 전의 이름(`2026-09-19-kickoff.md`)은 어느 쪽도 아니다
JOURNAL_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(?:(\d{4})|(\d{2}))-.+\.md$")
# 일지 폴더의 파일 가운데 일지로 세는 것. 규약 전의 이름도 든다. `README.md` 와 `.txt` 는 아니다
JOURNAL_ANY = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
ADR_NAME = re.compile(r"^(\d{4})-.+\.md$")
VERSION = re.compile(r"\*\*Version\*\*: (\d+\.\d+\.\d+)")
PULL_REF = re.compile(r"^refs/pull/(\d+)/(head|merge)$")
GITHUB_URL = re.compile(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
GH_PULL = re.compile(r"^(\d+) ([0-9a-f]{40})$")
GH_JQ = r'.[] | "\(.number) \(.head.sha)"'
GH_BODY_JQ = r".[] | [.number, .body] | @json"  # 줄마다 JSON 하나. 본문의 줄바꿈은 이스케이프된다

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None

# 일지 인용. 날짜 뒤가 두 자리(순번)부터 네 자리(시각)다. 목록 꼴(`일지 A·B`)의 인용을 함께 잡는다
# (대기열 254). 세 자리는 어느 꼴도 아니라 없는 일지로 읽힌다
JOURNAL_CITE = re.compile(r"일지 (\d{4}-\d{2}-\d{2}-\d{2,4}(?:·\d{4}-\d{2}-\d{2}-\d{2,4})*)(?!\d)")
CODE_SPAN = re.compile(r"`[^`\n]+`")
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
# main 의 헌법 README 가 함께 돌던 형제 브랜치 몫으로 비워 둔 판(대기열 279)
RESERVED = re.compile(
    r"(?<![\d.])(\d+\.\d+\.\d+)[은는] 함께 돌던 형제 브랜치\(`([^`]+)`\)가 먼저 매겨 비워 두었다"
)

CANARY_SPECS = ".scratch/**/probes/canary/*.toml"
# 새 `claude -p` 세션에서 불러 보는 하네스 파일(`docs/constitution/operations.md` 환경 규약 상세)
HARNESS = re.compile(r"^\.claude/(?:skills/[^/]+|rules|agents)/[^/]+\.md$")

# `--move` 가 옮기는 인용의 꼴. 갈래 하나로 묶어 한 번에 바꾼다(차례대로 옮기는 사슬이 두 번 가지
# 않게). 맨 앞 갈래는 인용 블록의 줄을 통째로 먹어, 그 안의 번호가 다른 갈래에 걸리지 않고
# `rewrite` 의 마지막 줄에서 그대로 돌아간다
_CITATIONS = (
    r"^(?P<quote>>[^\n]*)"
    r"|(?<=ADR )(?P<adrs>\d{4}(?:·\d{4})*)(?!\d)"
    r"|(?<![\w.])(?<!\d{4}-\d{2}-\d{2}-)(?P<adr>\d{4})(?=-[a-z0-9]|\])"
)
CITATION = re.compile(_CITATIONS, re.MULTILINE)
BOM = chr(0xFEFF)

NETWORK_TIMEOUT = 120
LOCAL_TIMEOUT = 30
SHALLOW_HINT = "얕은 클론이면 `git fetch --unshallow origin` 뒤 다시 친다"

USAGE = (
    "이 브랜치가 새로 매긴 번호(ADR, 헌법 판)와 고친 파일을 형제(기준 ref,"
    " 열린 PR, 형제 워크트리)와 대조한다. 바꾼 하네스 파일의 카나리아 명세를"
    " 고치지 않았거나, 이 브랜치가 더한 줄의 일지 인용이 어디에도 없는 일지를 가리키면 알린다."
    " 먼저 origin 의 오래 사는 브랜치(main, 있으면 dev)와 열린 PR 의 head 를 fetch 한다."
    " `--journal` 은 대조하지 않고"
    " 이 브랜치의 일지 경로를 찍는다. 판정의 근거와 못 보는 것은 이 파일의 독스트링에 있다."
)
EXITS = (
    "종료 코드: 0 고칠 것이 없다(함께 고친 파일은 알리기만 한다)."
    " 1 출력대로 고친다(번호 겹침, 판을 올리지 않고 고친 헌법 파일, 카나리아 명세를 고치지"
    " 않고 바꾼 하네스 파일, 어디에도 없는 일지를 가리킨 인용). `--journal` 에서는 이 브랜치가"
    " 더한 일지가 없다."
    " 2 대조하거나 옮기지 못했거나 인자가 틀렸다(stderr 의 할 일을 따른다)."
)
# 2로 끝날 때 stderr 에 함께 싣는 할 일(대기열 251)
ON_FAILURE = (
    "할 일: 번호(ADR, 헌법 판)를 손으로 고르지 않는다. 형제를 넘은 번호인지 알 수"
    " 없다. 원인을 고쳐 다시 친다. 번호를 쓸 파일이 아직 없으면 그동안 옮길 것은 스크래치 파일에"
    " 적어 두고, 번호를 받은 뒤 옮긴다. 일지는 번호가 없어 기다리지 않고 만든다"
)
# 옮기다 멈추고 다 되돌리지 못했을 때의 할 일. 다시 치면 이미 옮긴 인용이 한 번 더 옮겨진다
ON_STUCK = (
    "할 일: `--move` 를 다시 치지 않는다. 이미 옮긴 인용이 한 번 더 옮겨진다. 위에 든 것을 손으로"
    " 되돌리거나 마저 옮긴 뒤 `--move` 없이 다시 대조한다"
)


class SurveyError(Exception):
    """대조를 끝내지 못했다. git 이 실패했거나, 원격을 읽지 못했거나, 번호의 자리가 비었다."""


class MoveError(Exception):
    """번호를 옮기지 못했고 디스크는 옮기기 전 그대로다. 원인을 고쳐 다시 치면 된다."""


class StuckMoveError(MoveError):
    """번호를 옮기다 멈췄고 고친 것을 다 되돌리지 못했다. 메시지가 남은 것을 든다."""


@dataclass(frozen=True)
class Numbers:
    # 일지 파일 이름 전체. 번호가 아니라 이름이라 새로 매긴 것을 가르지 않는다(`fresh`·`unshared` 는
    # 비운다). 일지 인용이 가리키는 파일이 있는지 보는 데(`dangling_cites`)만 쓴다
    journals: frozenset[str]
    adrs: dict[str, str]  # 번호 → 파일 이름
    version: str | None


@dataclass(frozen=True)
class Clash:
    kind: str
    key: str
    ours: str
    theirs: str


@dataclass(frozen=True)
class Move:
    kind: str
    old: str
    new: str


@dataclass(frozen=True)
class Sibling:
    label: str
    commit: str
    numbers: Numbers  # 이 형제만 새로 매긴 번호
    changed: frozenset[str] | None  # None 이면 merge-base 가 없어 알 수 없다
    # 가장 높은 헌법 판의 후보. `latest` 와 같은 까닭으로 main 은 가진 판, 다른 형제는 새로 매긴 판
    version: str | None
    # HEAD 가 닫힌 PR 의 head 인 워크트리면 그 PR 번호. `changed` 는 커밋하지 않은 변경뿐이다
    closed: int | None = None


@dataclass(frozen=True)
class Survey:
    ours: Numbers  # 이 브랜치가 새로 매긴 번호
    changed: frozenset[str]
    main: Sibling
    others: list[Sibling]  # 열린 PR 과 형제 워크트리
    taken: list[Numbers]  # 이 브랜치 밖의 모든 자리(merge-base, main, 형제)의 번호 전체
    pulls_from: str  # 열린 PR 을 읽은 길(FROM_GH 또는 FROM_MERGE_REF)
    harness: list[str]  # 이 브랜치가 고친 하네스 파일 가운데 지금 있는 것
    specs: dict[str, str | None]  # 카나리아 명세 → 그 `source`
    base: str  # 이 브랜치와 main 의 merge-base. `--move` 가 둘 줄도 이 판에서 읽는다
    # main 의 헌법 README 가 이 브랜치 몫으로 비워 둔 판의 문장을 이 브랜치가 지웠으면 그 판
    reserved: str | None
    # 이 브랜치가 고친 파일 → 이 브랜치가 더한 줄에서 어디에도 없는 일지 번호를 가리킨 인용의 번호
    dangling: list[tuple[str, list[str]]]
    unfetched: tuple[int, ...] = ()  # head 커밋을 받지 못해 형제에서 뺀 열린 PR(대기열 288)

    @property
    def siblings(self) -> list[Sibling]:
        return [self.main, *self.others]


def read_numbers(
    journal_names: list[str],
    adr_names: list[str],
    constitution: str,
) -> Numbers:
    journals = frozenset(name for name in journal_names if JOURNAL_FILE.match(name))
    adrs = {m.group(1): name for name in adr_names if (m := ADR_NAME.match(name))}
    version = VERSION.search(constitution)
    return Numbers(journals, adrs, version.group(1) if version else None)


def fresh(numbers: Numbers, *known: Numbers) -> Numbers:
    """`known` 어디에도 없는 번호만 남긴다. 일지는 번호가 아니라 비운다."""
    version = numbers.version
    if version is not None and any(version == other.version for other in known):
        version = None
    adrs = {k: v for k, v in numbers.adrs.items() if all(k not in n.adrs for n in known)}
    return Numbers(frozenset(), adrs, version)


def unshared(numbers: Numbers, other: Numbers) -> Numbers:
    """`other` 와 같은 번호에 같은 파일인 것(공유한 이력)을 뺀다. 일지는 번호가 아니라 비운다.

    헌법 판은 판 줄로는 가를 수 없어 둔다. 같은 판이 공유한 이력인지 따로 올린 겹침인지는 헌법
    README 가 main 과 같은지로 `survey` 가 가른다.
    """
    adrs = {k: v for k, v in numbers.adrs.items() if other.adrs.get(k) != v}
    return Numbers(frozenset(), adrs, numbers.version)


def clashes(ours: Numbers, theirs: Numbers) -> list[Clash]:
    """둘 다 새로 매긴 번호 가운데 같은 번호를 다른 것에 쓴 것.

    같은 파일은 겹침이 아니라 공유한 이력이다(쌓아 올린 브랜치).
    """
    found: list[Clash] = []
    for key in sorted(ours.adrs.keys() & theirs.adrs.keys()):
        if ours.adrs[key] != theirs.adrs[key]:
            found.append(Clash("ADR", key, ours.adrs[key], theirs.adrs[key]))
    if ours.version is not None and ours.version == theirs.version:
        found.append(Clash("헌법", ours.version, ours.version, ours.version))
    return found


def journal_order(name: str) -> tuple[str, int, str]:
    """일지 파일 이름의 시각순 열쇠. 날짜가 앞서고, 같은 날이면 옛 순번 꼴(`-12-`)보다 새 시각 꼴
    (`-0930-`)이 늦다. 이름순으로 고르면 `-12-` 가 `-0930-` 보다 뒤에 서서 옛 일지가 걸린다. 이름이
    두 꼴이 아니면(규약 전의 이름) 그 날짜의 맨 앞이다."""
    found = JOURNAL_FILE.match(name)
    if found is None:
        return name[:10], -1, name
    day, stamp, seq = found.groups()
    return (day, 1, stamp) if stamp is not None else (day, 0, seq)


def _shift(olds: list[int], top: int) -> list[tuple[int, int]]:
    """`olds` 를 차례대로 `top` 뒤에 붙인다. 자리가 그대로인 것은 뺀다."""
    pairs = [(old, top + 1 + i) for i, old in enumerate(sorted(olds))]
    return [(old, new) for old, new in pairs if old != new]


def moves(ours: Numbers, taken: list[Numbers], found: list[Clash]) -> list[Move]:
    """겹친 종류의 이 브랜치 새 번호 전부를 형제들의 최대값 뒤로 옮긴다.

    겹친 번호만 옮기면 이 브랜치의 다른 새 번호와 부딪히거나 차례가 뒤집힌다.
    헌법 판은 고르지 않는다.
    """
    if not any(clash.kind == "ADR" for clash in found):
        return []
    top = max((int(k) for n in taken for k in n.adrs), default=0)
    olds = [int(key) for key in ours.adrs]
    return [Move("ADR", f"{a:04d}", f"{b:04d}") for a, b in _shift(olds, top)]


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def highest_version(held: Sequence[tuple[str, str | None]]) -> tuple[str, list[str]] | None:
    """(자리, 판) 가운데 가장 높은 판과 그 판을 쓴 자리 전부. 판은 글자가 아니라 수로 견준다."""
    versions = [version for _, version in held if version is not None]
    if not versions:
        return None
    top = max(versions, key=_version_key)
    return top, [label for label, version in held if version == top]


def reserved_version(branch: str | None, main_text: str, ours_text: str) -> str | None:
    """main 의 헌법 README(`main_text`)가 `branch` 몫으로 비워 둔 판 가운데, 이 브랜치의 헌법
    README(`ours_text`)가 그 문장을 지운 것. 이 브랜치의 판 줄이 main 의 판 줄과 같아야 한다. 판
    줄이 다르면 판 줄로 보고(main 을 합치기 전의 브랜치는 그 문장이 아예 없다), 판 줄이 없는
    글(지웠거나 비운 README)은 가져간 판이 없다. 둘 이상이면 가장 높은 판이다. 분리 HEAD(`branch` 가
    None)의 몫은 없다."""
    ours_line, main_line = VERSION.search(ours_text), VERSION.search(main_text)
    if ours_line is None or main_line is None or ours_line[1] != main_line[1]:
        return None
    reserved = {version for version, owner in RESERVED.findall(main_text) if owner == branch}
    kept = {version for version, owner in RESERVED.findall(ours_text) if owner == branch}
    return max(reserved - kept, key=_version_key, default=None)


def dangling_cites(
    text: str, known: Collection[str], kept: frozenset[str] = frozenset()
) -> list[str]:
    """`text` 의 일지 인용 가운데 `known`(일지 파일 이름)에 풀리는 파일이 없는 것. 나온 차례로 한
    번씩 든다. 인용은 `<인용>-` 로 시작하는 파일 이름으로 푼다. 접두 뒤의 하이픈이 `-14` 와
    `-1432-…` 를 가른다.

    인용 블록(`>` 로 시작하는 줄)은 사용자 프롬프트의 원문이고, 코드 스팬과 펜스 안은 옮기기 전의
    옛 번호를 적은 기록이나 도구의 출력이라 보지 않는다. 펜스는 여는 줄과 같은 글자로 같거나 더
    길게 닫고, 닫지 않으면 끝까지 간다. `kept` 와 글자가 같은 줄(줄 끝의 CR 은 빼고 견준다)은
    merge-base 나 main 의 판에 있던 줄이라 보지 않는다(`rewrite` 와 같다).
    """
    found: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        bare = line.rstrip("\r")
        mark = FENCE.match(bare)
        if fence is not None:
            if (
                mark is not None
                and mark[1][0] == fence[0]
                and len(mark[1]) >= len(fence)
                and not bare[mark.end() :].strip()
            ):
                fence = None
            continue
        if mark is not None:
            fence = mark[1]
            continue
        # "일지" 가 없는 줄은 정규식을 돌리지 않는다. 큰 미추적 파일도 이 판정이 통째로 읽는다
        if "일지" not in bare or bare in kept or bare.startswith(">"):
            continue
        for cite in JOURNAL_CITE.finditer(CODE_SPAN.sub("", bare)):
            for key in cite[1].split("·"):
                if key not in found and not any(name.startswith(f"{key}-") for name in known):
                    found.append(key)
    return found


def unbumped(changed: frozenset[str], ours: Numbers) -> list[str]:
    """이 브랜치가 판을 새로 매기지 않았는데 고친 헌법 파일."""
    return [] if ours.version is not None else sorted(changed & CONSTITUTION_TEXTS)


def harness_files(paths: Iterable[str]) -> list[str]:
    """`paths` 가운데 카나리아로 불러 보는 하네스 파일(스킬 폴더 바로 아래의 본문, 규칙,
    서브에이전트)."""
    return sorted(path for path in paths if HARNESS.match(path))


def uncanaried(
    harness: Iterable[str], changed: frozenset[str], specs: Mapping[str, str | None]
) -> list[tuple[str, list[str]]]:
    """`harness` 가운데 그 파일을 원천으로 든 카나리아 명세를 이 브랜치가 하나도 고치지 않은 것.

    짝의 뒤는 그 파일을 원천으로 든 명세 전부다(없으면 빈 목록).
    """
    found: list[tuple[str, list[str]]] = []
    for path in harness:
        held = sorted(spec for spec, source in specs.items() if source == path)
        if not any(spec in changed for spec in held):
            found.append((path, held))
    return found


def renumber(shifted: Iterable[Move]) -> dict[str, str]:
    """옮길 ADR 번호를 옛 번호 → 새 번호로 든다."""
    return {move.old: move.new for move in shifted if move.kind == "ADR"}


def rewrite(text: str, plan: Mapping[str, str], kept: frozenset[str] = frozenset()) -> str:
    """`plan`(옛 ADR 번호 → 새 번호)의 옛 번호를 든 인용을 한 번에 새 번호로 바꾼다. 인용 블록
    (`>` 로 시작하는 줄)은 다른 데서 옮겨 온 원문이라 둔다.

    `kept` 와 글자가 같은 줄(줄 끝의 CR 은 빼고 견준다)도 둔다. merge-base 나 main 의 판에 있던
    줄의 같은 번호는 상대를 가리킨다(`.claude/rules/adr.md`). BOM 은 떼고 바꾼 뒤 다시 붙인다.
    BOM 이 `^` 를 막아 첫 줄만 규칙에서 벗어났다(PR 직전 버그 축).
    """

    def swap(match: re.Match[str]) -> str:
        found = match.groupdict()
        if (adrs := found["adrs"]) is not None:
            return "·".join(plan.get(number, number) for number in adrs.split("·"))
        if (adr := found["adr"]) is not None:
            return plan.get(adr, adr)
        return match[0]

    bom = BOM if text.startswith(BOM) else ""
    lines = text[len(bom) :].split("\n")
    return bom + "\n".join(
        line if line.rstrip("\r") in kept else CITATION.sub(swap, line) for line in lines
    )


@dataclass(frozen=True)
class MovePlan:
    renames: list[tuple[str, str]]  # 저장소 기준 옛 경로 → 새 경로
    texts: dict[str, str]  # 고칠 파일(옛 경로) → 고친 글
    originals: dict[str, bytes]  # 고칠 파일(옛 경로) → 고치기 전 바이트. 멈추면 되돌린다


def plan_moves(
    root: Path,
    ours: Numbers,
    shifted: Sequence[Move],
    changed: Iterable[str],
    kept: Mapping[str, frozenset[str]] | None = None,
) -> MovePlan:
    """옮길 번호대로 바꿀 파일 이름과, `changed` 가운데 인용을 고칠 파일의 글을 짓는다.

    디스크는 읽기만 한다. 옮길 자리에 무엇이 있거나 파일을 읽지 못하면 MoveError 다. 옮길 자리가
    이 브랜치의 다른 옮길 파일이면(같은 슬러그의 사슬) 그 파일을 먼저 옮기는 차례로 둔다. 심볼릭
    링크는 따라가 쓰지 않는다. 반박 검증에서 저장소 밖을 가리키는 링크를 따라가 밖의 파일을
    고쳤다(일지 2026-10-15-15). `kept` 는 파일마다 두는 줄이다(`rewrite`).
    """
    plan = renumber(shifted)
    renames: list[tuple[str, str]] = []
    for old, new in plan.items():
        name = ours.adrs[old]
        renames.append((f"{ADR_DIR}/{name}", f"{ADR_DIR}/{new}{name[len(old) :]}"))
    sources = {source for source, _ in renames}
    for _, target in renames:
        if target not in sources and (root / target).exists():
            raise MoveError(f"옮길 자리 {target} 에 이미 무엇이 있다. 아무것도 고치지 않았다")
    texts: dict[str, str] = {}
    originals: dict[str, bytes] = {}
    for path in sorted(changed):
        file = root / path
        if file.is_symlink() or not file.is_file():
            continue
        try:
            raw = file.read_bytes()
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue  # 글이 아니다
        except OSError as error:
            raise MoveError(f"{path} 를 읽지 못했다({error}). 아무것도 고치지 않았다") from error
        lines = (kept or {}).get(path, frozenset())
        if (changed_text := rewrite(text, plan, lines)) != text:
            texts[path] = changed_text
            originals[path] = raw
    return MovePlan(vacating_first(renames), texts, originals)


def vacating_first(renames: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """옮길 자리를 비켜 줄 이름 바꾸기를 먼저 둔다.

    옮김은 정렬한 옛 번호를 차례대로 붙인 것이라 서로 자리를 맞바꾸는 순환이 없다. 그래서 자리가
    빈 것부터 고르면 끝난다. 순환이 들어오면 끝나지 않는 대신 MoveError 다.
    """
    pending = list(renames)
    ordered: list[tuple[str, str]] = []
    while pending:
        sources = {source for source, _ in pending}
        ready = [pair for pair in pending if pair[1] not in sources]
        if not ready:
            raise MoveError(
                f"서로 자리를 맞바꾸는 이름 바꾸기가 있다: {pending}. 아무것도 고치지 않았다"
            )
        ordered += ready
        pending = [pair for pair in pending if pair not in ready]
    return ordered


def apply_moves(root: Path, plan: MovePlan) -> None:
    """글을 먼저 고치고 이름을 바꾼다. 인덱스는 건드리지 않는다.

    도중에 멈추면 바꾼 이름과 쓴 글을 거꾸로 되돌린다. 되돌리지 않고 다시 치면 이미 옮긴 인용이
    차례대로 옮기는 사슬(03→05, 05→06)을 따라 한 번 더 옮겨진다(셀프 리뷰 표준 축, 일지
    2026-10-15-15). 다 되돌렸으면 MoveError, 되돌리지 못한 것이 있으면 StuckMoveError 다.
    """
    written: list[str] = []
    renamed: list[tuple[str, str]] = []
    try:
        for path, text in plan.texts.items():
            # 쓰기 전에 올린다. `write_bytes` 는 먼저 비우고 써서, 쓰다 멈춘 파일도 되돌릴 것이다
            written.append(path)
            (root / path).write_bytes(text.encode("utf-8"))
        for source, target in plan.renames:
            (root / source).rename(root / target)
            renamed.append((source, target))
    except OSError as error:
        left = _undo(root, plan, written, renamed)
        if left:
            raise StuckMoveError(
                f"옮기다 멈췄고({error}) 되돌리지 못한 것이 있다: {', '.join(left)}"
            ) from error
        raise MoveError(f"옮기다 멈춰({error}) 고친 것을 모두 되돌렸다") from error


def _undo(
    root: Path, plan: MovePlan, written: list[str], renamed: list[tuple[str, str]]
) -> list[str]:
    """바꾼 이름을 거꾸로 되돌리고 쓴 글을 옛 바이트로 되쓴다. 되돌리지 못한 것을 돌려준다.

    이미 옛 바이트인 파일(열지도 못하고 멈춘 파일)은 되쓰지 않는다. 되쓰다 또 실패해 되돌리지 못한
    것으로 들면 `--move` 를 다시 치지 말라는 거짓 할 일이 나간다.
    """
    left: list[str] = []
    stuck: set[str] = set()
    for source, target in reversed(renamed):
        try:
            (root / target).rename(root / source)
        except OSError:
            left.append(f"{target} → {source}")
            stuck.add(source)
    for path in written:
        if path in stuck:
            left.append(path)  # 옛 이름으로 돌아오지 않아 그 자리에 쓰면 사본이 생긴다
            continue
        try:
            if (root / path).read_bytes() != plan.originals[path]:
                (root / path).write_bytes(plan.originals[path])
        except OSError:
            left.append(path)
    return left


def github_repo(url: str) -> tuple[str, str] | None:
    """원격 URL 이 github.com 의 것이면 (owner, repo)."""
    match = GITHUB_URL.search(url.strip())
    return (match.group(1), match.group(2)) if match else None


def gh_pulls(text: str) -> dict[int, str]:
    """`gh api … --jq` 가 낸 "번호 head" 줄에서 열린 PR 의 번호 → head 커밋."""
    found: dict[int, str] = {}
    for line in text.splitlines():
        match = GH_PULL.match(line.strip())
        if match:
            found[int(match.group(1))] = match.group(2)
    return dict(sorted(found.items()))


def open_pulls(listing: str) -> dict[int, str]:
    """`git ls-remote` 의 `refs/pull/*` 줄에서 merge ref 가 있는 PR 의 번호 → head 커밋."""
    heads: dict[int, str] = {}
    merges: set[int] = set()
    for line in listing.splitlines():
        sha, _, ref = line.partition("\t")
        match = PULL_REF.match(ref.strip())
        if match is None:
            continue
        number = int(match.group(1))
        if match.group(2) == "head":
            heads[number] = sha.strip()
        else:
            merges.add(number)
    return {number: heads[number] for number in sorted(merges) if number in heads}


def closed_heads(listing: str, pulls: dict[int, str]) -> dict[str, int]:
    """`git ls-remote` 의 `refs/pull/*/head` 줄에서 열린 PR(`pulls`)이 아닌 PR 의 head → 번호.

    열린 PR 의 head 와 같은 커밋은 뺀다. 한 커밋을 head 로 든 닫힌 PR 이 여럿이면 큰 번호다.
    """
    opened = set(pulls.values())
    found: dict[str, int] = {}
    for line in listing.splitlines():
        sha, _, ref = line.partition("\t")
        match = PULL_REF.match(ref.strip())
        if match is None or match.group(2) != "head":
            continue
        number, sha = int(match.group(1)), sha.strip()
        if number not in pulls and sha not in opened:
            found[sha] = max(number, found.get(sha, 0))
    return found


def remote_branches(listing: str) -> dict[str, str]:
    """`git ls-remote` 줄에서 원격 브랜치 이름 → 그 끝 커밋."""
    found: dict[str, str] = {}
    for line in listing.splitlines():
        sha, _, ref = line.partition("\t")
        if (name := ref.strip().removeprefix("refs/heads/")) != ref.strip():
            found[name] = sha.strip()
    return found


@dataclass(frozen=True)
class Worktree:
    path: str
    head: str


def worktrees(porcelain: str) -> list[Worktree]:
    """`git worktree list --porcelain` 의 워크트리. bare 와 사라진(prunable) 것은 뺀다."""
    found: list[Worktree] = []
    for block in re.split(r"\n\s*\n", porcelain.strip()):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            name, _, value = line.partition(" ")
            fields[name] = value
        if "bare" in fields or "prunable" in fields:
            continue
        if "worktree" in fields and "HEAD" in fields:
            found.append(Worktree(fields["worktree"], fields["HEAD"]))
    return found


def _run(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str] | None:
    """명령을 띄운다. 띄우지 못하거나 시간을 넘기면 None."""
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_result(
    cwd: Path, args: tuple[str, ...], timeout: float
) -> subprocess.CompletedProcess[str]:
    result = _run(["git", "-c", "core.quotepath=false", *args], cwd, timeout)
    if result is None:
        raise SurveyError(f"git {args[0]} 을 띄우지 못했거나 {timeout}초를 넘겼다")
    return result


def git(cwd: Path, *args: str, timeout: float = LOCAL_TIMEOUT) -> str:
    result = _git_result(cwd, args, timeout)
    if result.returncode != 0:
        raise SurveyError(f"git {args[0]} (종료 {result.returncode}): {result.stderr.strip()}")
    return result.stdout


def is_ancestor(root: Path, commit: str, of: str) -> bool:
    result = _git_result(root, ("merge-base", "--is-ancestor", commit, of), LOCAL_TIMEOUT)
    if result.returncode > 1:
        raise SurveyError(f"git merge-base --is-ancestor: {result.stderr.strip()}")
    return result.returncode == 0


def merge_base(root: Path, one: str, other: str) -> str | None:
    """두 커밋의 merge-base. 이 클론에 공통 조상이 없으면(얕은 클론) None."""
    result = _git_result(root, ("merge-base", one, other), LOCAL_TIMEOUT)
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise SurveyError(f"git merge-base: {result.stderr.strip()}")
    return result.stdout.strip()


def current_branch(root: Path) -> str | None:
    """지금 브랜치의 이름. detached HEAD 면 None."""
    result = _git_result(root, ("symbolic-ref", "--quiet", "--short", "HEAD"), LOCAL_TIMEOUT)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def gh_listing(root: Path, owner: str, repo: str) -> str | None:
    """`gh api` 로 읽은 열린 PR 의 "번호 head" 줄. gh 가 없거나 실패하면 None."""
    gh = shutil.which("gh")
    if gh is None:
        return None
    endpoint = f"repos/{owner}/{repo}/pulls?state=open&per_page=100"
    result = _run([gh, "api", endpoint, "--paginate", "--jq", GH_JQ], root, NETWORK_TIMEOUT)
    return result.stdout if result is not None and result.returncode == 0 else None


def own_pull_bodies(root: Path, owner: str, repo: str, branch: str) -> dict[int, str] | None:
    """`gh api` 로 읽은, 이 저장소의 `branch` 를 head 로 든 열린 PR 의 번호 → 본문.

    gh 가 없거나 실패하거나 출력을 풀지 못하면 None. 포크에서 연 PR 은 head 의 owner 가 달라
    걸리지 않는다.
    """
    gh = shutil.which("gh")
    if gh is None:
        return None
    endpoint = f"repos/{owner}/{repo}/pulls?state=open&head={owner}:{quote(branch, safe='')}"
    result = _run([gh, "api", endpoint, "--jq", GH_BODY_JQ], root, NETWORK_TIMEOUT)
    return pull_bodies(result.stdout) if result is not None and result.returncode == 0 else None


def pull_bodies(text: str) -> dict[int, str] | None:
    """`own_pull_bodies` 의 gh 가 낸 줄(`[번호, 본문]` 의 JSON)에서 번호 → 본문.

    본문이 빈 PR 은 null 이 와 빈 글로 든다. 풀지 못한 줄이 하나라도 있으면 None 이다. 일부만 보고
    다 봤다고 하지 않는다. 줄은 `\\n` 으로만 가른다. JSON 은 문자열 안의 U+0085·U+2028·U+2029 를
    날것으로 둘 수 있고(jq 가 그것을 이스케이프하는지는 재지 않았다), `splitlines` 는 그 글자에서도
    갈라 본문에 그 글자가 든 PR 의 줄을 풀지 못하게 한다.
    """
    found: dict[int, str] = {}
    for line in text.split("\n"):  # splitlines 는 U+0085·U+2028 에서도 가른다
        if not line.strip():
            continue
        try:
            pair: Json = json.loads(line)
        except ValueError:
            return None
        if not isinstance(pair, list) or len(pair) != 2:
            return None
        number, body = pair
        if not isinstance(number, int) or not (body is None or isinstance(body, str)):
            return None
        found[number] = body or ""
    return found


def moved_bodies(bodies: Mapping[int, str], shifted: Iterable[Move]) -> dict[int, str]:
    """`bodies`(PR 번호 → 본문) 가운데 옮길 번호대로 인용이 바뀌는 것만 옮긴 본문으로 낸다.

    꼴은 `rewrite` 와 같다.
    """
    plan = renumber(shifted)
    moved = {number: rewrite(body, plan) for number, body in bodies.items()}
    return {number: moved[number] for number in sorted(moved) if moved[number] != bodies[number]}


def write_moved_bodies(
    moved: Mapping[int, str], folder: Path | None = None
) -> dict[int, Path | OSError]:
    """옮긴 본문(`moved_bodies`)을 PR 마다 `folder`(없으면 처음 쓸 때 만드는 임시 폴더)의
    `pr-<번호>-body.md` 에 바이트 그대로 쓴다. PR 의 본문은 고치지 않는다.

    PR 번호 → 쓴 파일이고, 쓰지 못한 PR 은 그 오류다. 하나를 쓰지 못해도 나머지는 쓴다.
    """
    written: dict[int, Path | OSError] = {}
    target = folder
    for number in sorted(moved):
        try:
            target = target or Path(tempfile.mkdtemp(prefix="sibling-overlap-"))
            path = target / f"pr-{number}-body.md"
            path.write_bytes(moved[number].encode("utf-8"))
        except OSError as error:
            written[number] = error
            continue
        written[number] = path
    return written


def pull_body_lines(
    bodies: Mapping[int, str] | None,
    written: Mapping[int, Path | OSError],
    repo: tuple[str, str],
) -> list[str]:
    """이 브랜치의 열린 PR 본문(`own_pull_bodies`)마다 옮긴 본문을 쓴 결과(`write_moved_bodies`)를
    대 본 출력 줄.

    쓴 PR 은 그 파일을 올리는 REST 명령을 든다. 클라우드 세션에서 `gh pr list`,
    `gh pr checks <번호>`, `gh pr view <번호> --json headRefOid` 가 GraphQL 이 막혀 실패했고 REST 는
    됐다(`.claude/rules/tools.md`. `gh pr edit` 는 거기서 재지 않았다). 그 명령은 본문 전체를 이번에
    읽은 판으로 덮어써, 읽은 뒤에 사람·봇·세션이 고친 것(CodeRabbit 이 본문에 넣는 요약 블록 등)이
    지금 본문에서 빠진다(GitHub 의 편집 이력에는 남는다). 그래서 올리기 전에 지금 본문과 그 파일을
    견주라는 말을 명령 앞에 적고, 명령은 줄 끝에 두어 그 뒤를 그대로 붙여 넣을 수 있게 한다(PR #328
    CodeRabbit·셀프 리뷰). 열린 PR 이 없으면 빈 목록이다.
    """
    if bodies is None:
        return [
            "이 브랜치의 열린 PR 본문을 읽지 못했다(gh 가 없거나 `gh api` 가 실패했다). PR 본문에"
            " 옮기기 전 번호가 남았는지 손으로 본다"
        ]
    owner, name = repo
    lines: list[str] = []
    for number in sorted(bodies):
        head = f"이 브랜치의 열린 PR #{number} 본문"
        outcome = written.get(number)
        if outcome is None:
            lines.append(f"{head}에는 옮길 인용이 없다")
        elif isinstance(outcome, OSError):
            lines.append(
                f"{head}에 옮기기 전 번호가 있다. 옮긴 본문을 쓰지 못했다({outcome}). 손으로 고친다"
            )
        else:
            where = outcome.as_posix()
            lines.append(
                f"{head}에 옮기기 전 번호가 있다. 옮긴 본문을 {where} 에 썼다. 올리는 명령은 본문"
                " 전체를 이 파일로 덮어쓴다. 올리기 전에 지금 본문을 다시 읽어 이 파일과 견주고,"
                " 옮긴 번호 밖의 차이(읽은 뒤에 사람·봇·세션이 고친 것)가 있으면 이 파일에도"
                " 넣는다. 올리는 명령: gh api"
                f' repos/{owner}/{name}/pulls/{number} --method PATCH -F "body=@{where}"'
            )
    return lines


class Snapshot(Protocol):
    def names(self, directory: str) -> list[str]: ...

    def text(self, path: str) -> str: ...


@dataclass(frozen=True)
class Tree:
    """커밋 하나의 트리."""

    root: Path
    commit: str

    def names(self, directory: str) -> list[str]:
        listing = git(self.root, "ls-tree", "--name-only", self.commit, "--", f"{directory}/")
        return [PurePosixPath(line).name for line in listing.splitlines()]

    def text(self, path: str) -> str:
        if not git(self.root, "ls-tree", "--name-only", self.commit, "--", path).strip():
            return ""  # 그 커밋에 파일이 없다
        return git(self.root, "show", f"{self.commit}:{path}")


@dataclass(frozen=True)
class Disk:
    """작업 트리. 커밋하지 않은 변경과 미추적 파일까지 든다."""

    root: Path

    def names(self, directory: str) -> list[str]:
        folder = self.root / directory
        if not folder.is_dir():
            return []
        return sorted(path.name for path in folder.iterdir() if path.is_file())

    def text(self, path: str) -> str:
        file = self.root / path
        return file.read_text(encoding="utf-8", errors="replace") if file.is_file() else ""


def numbers_of(snapshot: Snapshot) -> Numbers:
    return read_numbers(
        snapshot.names(JOURNAL_DIR),
        snapshot.names(ADR_DIR),
        snapshot.text(CONSTITUTION),
    )


def merge_heads(root: Path) -> list[str]:
    """합치기를 커밋하기 전이면 `MERGE_HEAD` 파일의 커밋들(octopus 면 여럿). 아니면 빈 목록."""
    result = _git_result(root, ("rev-parse", "--git-path", "MERGE_HEAD"), LOCAL_TIMEOUT)
    if result.returncode != 0:
        raise SurveyError(f"git rev-parse --git-path: {result.stderr.strip()}")
    path = Path(result.stdout.strip())
    marker = path if path.is_absolute() else root / path
    return marker.read_text(encoding="utf-8").split() if marker.is_file() else []


def canary_sources(root: Path) -> dict[str, str | None]:
    """디스크의 카나리아 명세(저장소 기준 경로) → 그 `source`. 읽지 못했거나 글자가 아니면 None."""
    found: dict[str, str | None] = {}
    for file in sorted(root.glob(CANARY_SPECS)):
        try:
            source: object = tomllib.loads(file.read_text(encoding="utf-8")).get("source")
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            source = None
        found[file.relative_to(root).as_posix()] = source if isinstance(source, str) else None
    return found


def empty_places(numbers: Numbers) -> list[str]:
    """비면 경로가 어긋난 것으로 보는 번호의 자리. 대기열은 들지 않는다. 폴더가 된 뒤에는 옛 표가
    어느 merge-base 에도 없다. 일지와 harness 티켓은 번호가 아니라 들지 않는다."""
    places = (
        (ADR_DIR, not numbers.adrs),
        (CONSTITUTION, numbers.version is None),
    )
    return [place for place, empty in places if empty]


def _lines(text: str) -> frozenset[str]:
    return frozenset(line for line in text.splitlines() if line)


def _own_changes(root: Path, base: str, main_sha: str) -> frozenset[str]:
    """작업 트리 `root` 가 `base` 뒤에 고친 파일 가운데 main 과 내용이 다른 것. 미추적 파일을
    더한다.

    이 브랜치에는 merge-base 를, 형제 워크트리에는 그 형제의 merge-base 나 닫힌 PR 의 head 를
    넘긴다. main 과 같은 파일은 main 이 들여온 것이다. 합치기를 커밋하기 전에는 merge-base 가 옛
    자리에 머물러 main 이 고친 파일이 모두 섞였고, 카나리아 누락이 main 의 규칙과 스킬을 알렸다(일지
    2026-10-15-15). 형제에서도 같은 일이 나, main 과 글자가 같은 두 파일을 그 형제가 함께 고친
    파일로 냈다(대기열 294, 일지 2026-10-16-20).
    """
    since_base = _lines(git(root, "diff", "--name-only", base))
    unlike_main = _lines(git(root, "diff", "--name-only", main_sha))
    untracked = _lines(git(root, "ls-files", "--others", "--exclude-standard"))
    return (since_base & unlike_main) | untracked


def dangling_files(
    root: Path, commits: Sequence[str], changed: Iterable[str], known: Collection[str]
) -> list[tuple[str, list[str]]]:
    """`changed` 의 파일마다, `commits` 의 판에 글자 그대로 있는 줄을 뺀 줄에서 `known` 에 없는
    일지를 가리킨 인용(`dangling_cites`).

    줄을 가르는 git 호출은 없는 번호가 든 파일에서만 친다. 지운 파일과 UTF-8 로 읽지 못하는 파일은
    두고 넘어간다.
    """
    found: list[tuple[str, list[str]]] = []
    for path in sorted(changed):
        file = root / path
        if not file.is_file():
            continue
        try:
            text = file.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not dangling_cites(text, known):
            continue
        kept = _kept_lines(root, commits, [path])[path]
        if numbers := dangling_cites(text, known, kept):
            found.append((path, numbers))
    return found


FROM_GH = "gh api"
FROM_MERGE_REF = "merge ref"


@dataclass(frozen=True)
class Remote:
    """원격에서 읽은 것. 열린 PR(번호 → head), 그것을 읽은 길, 이 브랜치의 원격 커밋, 닫힌 PR."""

    pulls: dict[int, str]
    pulls_from: str  # FROM_GH 또는 FROM_MERGE_REF
    own_head: str | None
    closed: dict[str, int]  # 닫힌 PR 의 head → 번호
    heads: frozenset[int] = frozenset()  # 원격에 `refs/pull/<N>/head` 가 있는 PR
    unfetched: tuple[int, ...] = ()  # head 커밋을 받지 못해 `pulls` 에서 뺀 열린 PR(대기열 288)


def pull_heads(listing: str) -> frozenset[int]:
    """`git ls-remote` 의 `refs/pull/*/head` 줄의 PR 번호."""
    found: set[int] = set()
    for line in listing.splitlines():
        match = PULL_REF.match(line.partition("\t")[2].strip())
        if match is not None and match.group(2) == "head":
            found.add(int(match.group(1)))
    return frozenset(found)


def read_remote(root: Path) -> Remote:
    """열린 PR, 이 브랜치의 원격 끝, 닫힌 PR 의 head 를 읽는다. 로컬의 ref 는 움직이지 않는다."""
    branch = current_branch(root)
    patterns = ["refs/pull/*/head", "refs/pull/*/merge", "refs/heads/*"]
    listing = git(root, "ls-remote", REMOTE, *patterns, timeout=NETWORK_TIMEOUT)
    repo = github_repo(git(root, "remote", "get-url", REMOTE))
    from_gh = gh_listing(root, *repo) if repo else None
    if from_gh is not None:
        pulls, pulls_from = gh_pulls(from_gh), FROM_GH
    else:
        pulls, pulls_from = open_pulls(listing), FROM_MERGE_REF
    branches = remote_branches(listing)
    own = branches.get(branch) if branch else None
    closed = closed_heads(listing, pulls)
    return Remote(pulls, pulls_from, own, closed, pull_heads(listing))


def has_commit(root: Path, sha: str) -> bool:
    """`sha` 가 이 클론에 있는 커밋인지."""
    result = _git_result(root, ("cat-file", "-e", f"{sha}^{{commit}}"), LOCAL_TIMEOUT)
    return result.returncode == 0


def _has_trunk(root: Path, name: str) -> bool:
    """`origin/<name>` 의 추적 ref 가 이 클론에 있고 커밋을 가리키는지."""
    ref = f"refs/remotes/{REMOTE}/{name}^{{commit}}"
    result = _git_result(root, ("rev-parse", "--verify", "--quiet", ref), LOCAL_TIMEOUT)
    return result.returncode == 0


def trunk_names(root: Path) -> list[str]:
    """대조할 오래 사는 브랜치의 이름. 첫째가 이 브랜치의 기준 브랜치이고(`tools/base_rule.py`),
    뒤는 이 클론에 추적 ref 가 있는 다른 오래 사는 브랜치다.

    `origin/dev` 가 없으면 `["main"]` 하나라 기준이 main 이던 때와 같은 대조다. dev 를 기준으로
    하면 main 이 둘째다. dev 에서 main 으로 가는 사이에 hotfix 가 끼면 main 이 dev 보다 앞서 번호를
    가질 수 있고, 그 번호도 이 브랜치 밖의 것으로 센다. hotfix 브랜치는 반대로 dev 가 둘째다.
    규칙의 판정(`base_rule.base_name`)만 가져다 쓰고 ref 는 이 모듈의 git 호출로 본다.
    """
    dev = _has_trunk(root, base_rule.DEV)
    base = base_rule.base_name(current_branch(root), dev_exists=dev)
    others = [name for name in (base_rule.MAIN, base_rule.DEV) if name != base]
    return [base, *(name for name in others if _has_trunk(root, name))]


def fetch(root: Path, remote: Remote) -> Remote:
    """기준 브랜치와 다른 오래 사는 브랜치(`trunk_names`)를 당기고, 열린 PR 의 head 를 ref 없이
    받는다.

    gh 가 열린 PR 로 읽어도 원격에 `refs/pull/<N>/head` 가 아직 없을 수 있다. PR 을 연 지 몇 분
    안에 그 ref 를 받는 fetch 가 128로 끝나 대조 전체가 2로 멈췄다(대기열 288, 일지
    2026-10-16-18). 그래서 ref 는 원격에 있는 것만 받고, 그 뒤에도 head 커밋이 이 클론에 없는
    PR(ref 가 없거나 gh 가 읽은 head 보다 옛것인 PR)은 커밋을 sha 로 받는다. 같은 저장소의 PR 이면
    gh 가 읽은 head 는 그때의 head 브랜치 끝이다. 로컬 원격에서는 그런 커밋이 받아졌고, GitHub 이
    그 커밋을 sha 로 내주는지와 그 사이 강제 푸시로 끝에서 밀려난 커밋은 재지 않았다. 그래도 받지
    못한 PR 만 `pulls` 에서 빼 `unfetched` 에 든다. sha 로 받는 fetch 가 시간 제한을 넘기면
    `SurveyError` 로 대조 전체가 멈춘다(모듈 독스트링의 못 보는 것).
    """
    present = [number for number in remote.pulls if number in remote.heads]
    git(
        root,
        "fetch",
        "--quiet",
        "--no-tags",
        "--no-write-fetch-head",
        REMOTE,
        *(f"+refs/heads/{name}:refs/remotes/{REMOTE}/{name}" for name in trunk_names(root)),
        *(f"refs/pull/{number}/head" for number in present),
        timeout=NETWORK_TIMEOUT,
    )
    unfetched: list[int] = []
    for number, head in remote.pulls.items():
        if has_commit(root, head):
            continue
        args = ("fetch", "--quiet", "--no-tags", "--no-write-fetch-head", REMOTE, head)
        _git_result(root, args, NETWORK_TIMEOUT)
        if not has_commit(root, head):
            unfetched.append(number)
    pulls = {n: head for n, head in remote.pulls.items() if n not in unfetched}
    return replace(remote, pulls=pulls, unfetched=tuple(unfetched))


def survey(root: Path, remote: Remote) -> Survey:
    """fetch 가 끝난 클론에서 이 브랜치와 형제의 번호와 고친 파일을 읽는다."""
    trunks = trunk_names(root)
    base_label = f"{REMOTE}/{trunks[0]}"
    main_sha = git(root, "rev-parse", base_label).strip()
    base = merge_base(root, "HEAD", main_sha)
    if base is None:
        raise SurveyError(
            f"이 브랜치와 {base_label} 의 merge-base 가 이 클론에 없다. {SHALLOW_HINT}"
        )
    base_numbers = numbers_of(Tree(root, base))
    if missing := empty_places(base_numbers):
        raise SurveyError(f"merge-base 에서 번호의 자리가 비었다: {', '.join(missing)}")
    main_numbers = numbers_of(Tree(root, main_sha))
    main_changed = _lines(git(root, "diff", "--name-only", base, main_sha))
    main_new = fresh(main_numbers, base_numbers)
    main_sibling = Sibling(
        label=base_label,
        commit=main_sha,
        numbers=main_new,
        changed=main_changed,
        version=main_numbers.version,
    )
    others: list[Sibling] = []
    taken = [base_numbers, main_numbers]
    # 기준이 아닌 오래 사는 브랜치(dev 가 기준이면 main)의 번호 전체. 그 브랜치를 base 로 연 PR
    # (dev 가 기준일 때 main 에서 딴 hotfix PR)의 head 는 이 번호를 품지만 PR 이 더한 것이 아니다
    trunk_numbers: list[Numbers] = []
    # 이 브랜치가 이미 품은 기준이 아닌 오래 사는 브랜치의 번호
    inherited: list[Numbers] = []
    branch = current_branch(root)

    def add(
        label: str,
        head: str,
        numbers: Numbers,
        changed: frozenset[str] | None,
        closed: int | None = None,
    ) -> None:
        new = fresh(numbers, base_numbers, main_numbers)
        for trunk in trunk_numbers:
            # 번호만 같은 다른 파일은 그 형제가 새로 매긴 것이다. 같은 번호에 같은 파일일 때만 뺀다
            new = unshared(new, trunk)
            if new.version == trunk.version:
                new = replace(new, version=None)
        others.append(
            Sibling(
                label=label,
                commit=head,
                numbers=new,
                changed=changed,
                version=new.version,
                closed=closed,
            )
        )
        taken.append(numbers)

    for name in trunks[1:]:
        # 기준이 아닌 오래 사는 브랜치(dev 가 기준이면 main). 이 브랜치가 이미 품은 것은 번호가 이
        # 브랜치 안에 있어 형제가 아니다
        label = f"{REMOTE}/{name}"
        other = git(root, "rev-parse", label).strip()
        other_numbers = numbers_of(Tree(root, other))
        if is_ancestor(root, other, "HEAD"):
            # 형제로 알리지 않는다. 그래도 이 브랜치가 그쪽에서 물려받은 번호는 이 브랜치가 새로
            # 매긴 것이 아니라 공유한 이력이다(`--move` 가 옮기지 않게 `ours` 에서 뺀다)
            inherited.append(other_numbers)
            trunk_numbers.append(other_numbers)
            taken.append(other_numbers)
            continue
        since = merge_base(root, other, main_sha)
        changed = _lines(git(root, "diff", "--name-only", since, other)) if since else None
        add(label, other, other_numbers, changed)
        trunk_numbers.append(other_numbers)
    for number, head in remote.pulls.items():
        if head == remote.own_head or is_ancestor(root, head, "HEAD"):
            continue
        since = merge_base(root, head, main_sha)
        changed = _lines(git(root, "diff", "--name-only", since, head)) if since else None
        add(f"PR #{number}", head, numbers_of(Tree(root, head)), changed)
    for tree in worktrees(git(root, "worktree", "list", "--porcelain")):
        path, head = Path(tree.path).resolve(), tree.head
        if path == root or not path.is_dir():
            continue
        numbers = numbers_of(Disk(path))
        if (closed := remote.closed.get(head)) is not None:
            # 커밋한 변경은 병합됐거나 앞으로 병합되지 않아 충돌 후보가 아니다(대기열 194)
            label = f"워크트리 {path}(PR #{closed} 닫힘)"
            add(label, head, numbers, _own_changes(path, head, main_sha), closed)
            continue
        since = merge_base(root, head, main_sha)
        changed = _own_changes(path, since, main_sha) if since else None
        add(f"워크트리 {path}", head, numbers, changed)
    disk = numbers_of(Disk(root))
    ours = unshared(fresh(disk, base_numbers), main_numbers)
    for numbers in inherited:
        ours = unshared(ours, numbers)
    if heads := merge_heads(root):
        # 합치기를 커밋하기 전이다. 합칠 머리가 main 이 아니어도 그 번호는 이 브랜치 밖의 것이다
        merged = [Tree(root, head) for head in heads]
        for tree in merged:
            numbers = numbers_of(tree)
            taken.append(numbers)
            ours = unshared(ours, numbers)
    changed = _own_changes(root, base, main_sha)
    reserved: str | None = None
    if CONSTITUTION not in changed:
        # 판 줄이 main 과 같다. 합치기를 커밋하기 전에는 main 이 올린 판이 디스크에 있다
        ours = replace(ours, version=None)
    elif ours.version in (None, main_numbers.version):
        # 판 줄은 merge-base 나 main 의 것이다. main 이 이 브랜치 몫으로 비워 둔 판의 문장을 이
        # 브랜치가 지웠으면 그 판으로 올린 것이다(대기열 279)
        main_text = Tree(root, main_sha).text(CONSTITUTION)
        disk_text = Disk(root).text(CONSTITUTION)
        reserved = reserved_version(branch, main_text, disk_text)
        if reserved is not None:
            ours = replace(ours, version=reserved)
    specs = canary_sources(root)
    # rag-engine 은 카나리아 도구(agent-os 의 `tools/canary.py`)와 그 명세를 복사하지 않았다. 명세가
    # 하나도 없는 저장소에서는 바꾼 하네스 파일을 세지 않는다 — 알림이 시키는 일을 할 도구가 없다
    changed_harness = (path for path in harness_files(changed) if (root / path).is_file())
    harness = list(changed_harness) if specs else []
    known = {name for numbers in [*taken, disk] for name in numbers.journals}
    return Survey(
        ours,
        changed,
        main_sibling,
        others,
        taken,
        remote.pulls_from,
        harness,
        specs,
        base,
        reserved,
        dangling_files(root, (base, main_sha), changed, known),
        remote.unfetched,
    )


def findings(result: Survey) -> list[tuple[Sibling, Clash]]:
    return [
        (sibling, clash)
        for sibling in result.siblings
        for clash in clashes(result.ours, sibling.numbers)
    ]


def _describe(clash: Clash) -> str:
    if clash.kind == "헌법":
        return "이 브랜치와 그쪽이 같은 판으로 올렸다"
    return f"이 브랜치 {clash.ours}, 그쪽 {clash.theirs}"


_PULLS_FROM = {FROM_GH: "gh api", FROM_MERGE_REF: "merge ref(gh api 를 쓰지 못했다)"}


def _ours_line(ours: Numbers) -> str:
    keys = [f"ADR {key}" for key in sorted(ours.adrs)]
    keys += [f"헌법 {ours.version}"] if ours.version else []
    return f"이 브랜치의 새 번호: {', '.join(keys)}" if keys else "이 브랜치의 새 번호 없음"


@dataclass(frozen=True, kw_only=True)
class Verdict:
    """출력과 종료 코드가 함께 읽는 판정. 한 번만 지어 둘이 어긋나지 않게 한다.

    칸이 많고 같은 타입의 칸이 이웃해, 위치 인자로 지으면 순서가 틀려도 타입 검사가 잡지 못한다.
    그래서 키워드로만 짓는다(PR #345 claude-review).
    """

    found: list[tuple[Sibling, Clash]]
    shifted: list[Move]
    top_version: tuple[str, list[str]] | None  # 형제가 쓴 가장 높은 헌법 판과 그 자리
    unbumped: list[str]  # 판을 올리지 않고 고친 헌법 파일
    # 카나리아 명세를 고치지 않고 바꾼 하네스 파일과 그 파일을 원천으로 든 명세
    uncanaried: list[tuple[str, list[str]]]
    # 이 브랜치가 더한 줄에서 어디에도 없는 일지를 가리킨 인용(파일, 인용)
    dangling: list[tuple[str, list[str]]]

    @property
    def code(self) -> int:
        fix = self.found or self.unbumped or self.uncanaried or self.dangling
        return 1 if fix else 0


def judge(result: Survey) -> Verdict:
    found = findings(result)
    shifted = moves(result.ours, result.taken, [clash for _, clash in found])
    top = highest_version([(s.label, s.version) for s in result.siblings])
    return Verdict(
        found=found,
        shifted=shifted,
        top_version=top,
        unbumped=unbumped(result.changed, result.ours),
        uncanaried=uncanaried(result.harness, result.changed, result.specs),
        dangling=result.dangling,
    )


def _clash_lines(found: Sequence[tuple[Sibling, Clash]]) -> list[str]:
    return [f"- {s.label} {c.kind} {c.key}: {_describe(c)}" for s, c in found]


def _siblings_line(siblings: list[Sibling]) -> str:
    shown = [f"{s.label} {s.commit[:7]}" for s in siblings if s.closed is None]
    if folded := sum(1 for s in siblings if s.closed is not None):
        shown.append(f"PR 이 닫힌 워크트리 {folded}곳(커밋하지 않은 변경만 견준다)")
    return "형제: " + ", ".join(shown)


def render(result: Survey, verdict: Verdict) -> str:
    lines = [
        _siblings_line(result.siblings),
        f"열린 PR 을 읽은 길: {_PULLS_FROM[result.pulls_from]}",
    ]
    if result.unfetched:
        numbers = ", ".join(f"#{number}" for number in result.unfetched)
        lines.append(
            f"받지 못해 대조에서 뺀 열린 PR: {numbers}(원격에서 head 커밋을 받지 못했다. 막 연 PR"
            " 이면 원격이 ref 를 아직 만들지 않은 것이다). 그 PR 과의 번호 겹침과 함께 고친 파일은"
            " 보지 않았으니 잠시 뒤 다시 친다. 다시 쳐도 같으면 기다리지 않는다. 포크의 PR 이거나"
            " 원격에 없는 커밋일 수 있고, 그 PR 과의 겹침은 PR 화면에서 손으로 본다"
        )
    if verdict.top_version:
        version, labels = verdict.top_version
        lines.append(
            f"형제가 쓴 가장 높은 헌법 판: {version}({', '.join(labels)})."
            " 판을 올리면 이보다 높게 고른다"
        )
    lines.append(_ours_line(result.ours))
    if result.reserved:
        lines.append(
            f"올린 판으로 센 헌법 {result.reserved}: {result.main.label} 의 헌법 README 가"
            " 이 브랜치 몫으로 비워 둔 판이고, 이 브랜치가 그 문장을 지웠다"
        )
    if verdict.found:
        lines.append(f"번호 겹침 {len(verdict.found)}:")
        lines += _clash_lines(verdict.found)
    else:
        lines.append("번호 겹침 없음")
    if verdict.unbumped:
        lines.append(
            f"헌법 파일을 고치고 판을 올리지 않았다: {', '.join(verdict.unbumped)}."
            " 위의 가장 높은 판보다 높게 올린다(원칙 변경은 major, 절 추가는 minor,"
            " 문구 수정은 patch)"
        )
    if verdict.uncanaried:
        lines.append(
            "카나리아 명세를 이 브랜치에서 고치지 않고 바꾼 하네스 파일. 새 `claude -p` 세션에서"
            " 불러 보고(`tools/canary.py`) 그 명세의 `# 최신 결과:` 줄을 고친다. 그 파일을 원천으로"
            " 든 명세가 없으면 새로 쓴다(docs/constitution/operations.md 환경 규약 상세). 계정"
            " 한도로 돌리지 못하면 그 절의 계정 한도 항목대로 사전 확인만 돌리고 이 알림이 남은 채"
            " 커밋한다:"
        )
        for path, specs in verdict.uncanaried:
            names = ", ".join(PurePosixPath(spec).name for spec in specs) or "명세 없음"
            lines.append(f"- {path}: {names}")
    if verdict.dangling:
        lines.append(
            "어디에도 없는 일지를 가리킨 인용(main, 형제, 이 브랜치 어디에도"
            " `docs/journal/<인용>-*.md` 가 없다). 가리키려던 일지 파일 이름의"
            " 앞부분(`<날짜>-<HHMM>`, 옛 일지는 `<날짜>-<NN>`)으로 고친다."
            " 아직 만들지 않은 이 브랜치의 일지면 일지 파일을 먼저 만들고"
            " 그 이름의 앞부분을 든다. 옮기기 전의 옛 이름처럼 일부러 없는 것을"
            " 적은 기록이면 코드 스팬(``)에 넣고, 일부러 없는 이름을 쓴 시험"
            " 데이터면 시험이 바뀌지 않게 백틱을 넣지 말고 저장소에 있는"
            " 일지의 앞부분으로 바꾼다:"
        )
        lines += [f"- {path}: {', '.join(cites)}" for path, cites in verdict.dangling]
    if verdict.shifted:
        moved = ", ".join(f"{m.kind} {m.old} → {m.new}" for m in verdict.shifted)
        lines.append(f"옮길 번호: {moved}")
        lines.append(
            "`--move` 를 붙여 다시 치면 이 번호대로 ADR 의 파일 이름과 이 브랜치의 변경과"
            " 미추적 파일 안의 인용을 옮긴다"
        )
    shared: list[str] = []
    for sibling in result.siblings:
        if sibling.changed is None:
            shared.append(f"- {sibling.label}: 알 수 없다(merge-base 가 없다. {SHALLOW_HINT})")
        elif paths := sorted(result.changed & sibling.changed):
            shared.append(f"- {sibling.label}: {', '.join(paths)}")
    if shared:
        lines.append("함께 고친 파일(나중에 병합하는 쪽에서 글자 충돌 후보, 종료 코드와 무관):")
        lines += shared
    else:
        lines.append("함께 고친 파일 없음")
    return "\n".join(lines)


def _moved_line(shifted: Sequence[Move], plan: MovePlan) -> str:
    renamed = dict(plan.renames)
    moved = ", ".join(f"{m.kind} {m.old} → {m.new}" for m in shifted)
    names = ", ".join(f"{old} → {new}" for old, new in plan.renames) or "없음"
    texts = ", ".join(sorted(renamed.get(path, path) for path in plan.texts)) or "없음"
    return (
        f"옮겼다: {moved}. 이름을 바꾼 파일: {names}. 인용을 고친 파일: {texts}. 스테이지하지"
        " 않았으니 옛 이름의 지움까지 함께 스테이지한다(`git add -A`). 낱말 없이 든 번호,"
        " 번호 뒤의 조사는 옮기지 않았으니 손으로 본다"
    )


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        """인자가 틀려 2로 끝날 때도 할 일을 싣는다."""
        self.print_usage(sys.stderr)
        self.exit(2, f"인자가 틀렸다: {message}\n{ON_FAILURE}\n")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="uv run python tools/sibling_overlap.py", description=USAGE, epilog=EXITS)
    parser.add_argument("path", nargs="?", help="저장소 안의 경로. 없으면 지금 폴더")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--move",
        action="store_true",
        help="옮길 번호대로 ADR 의 파일 이름과 이 브랜치의 변경과 미추적 파일 안의 인용을"
        " 옮기고 다시 대조한다. 이 브랜치의 열린 PR 본문은 옮긴 판과 올리는 명령만 낸다",
    )
    group.add_argument(
        "--journal",
        action="store_true",
        help="대조하지 않고 이 브랜치의 일지 경로를 한 줄로 찍는다. 더한 일지가 없으면 1로 끝난다",
    )
    return parser


def branch_journals(root: Path) -> list[str]:
    """이 브랜치가 더한 일지의 경로를 시각순으로 든다(가장 늦은 것이 끝).

    merge-base 뒤에 더한 일지와 커밋하지 않은 새 일지다. main 을 합친 뒤에는 merge-base 가 main 의
    끝으로 옮겨 가 main 이 들여온 일지는 들지 않는다. 같은 날 옛 순번 꼴과 새 시각 꼴이 섞여도
    시각순(`journal_order`)이다. 이름순이면 `-12-` 가 `-0930-` 뒤에 선다. 이름이 날짜로 시작하는
    `.md` 만 일지로 센다(일지 폴더의 `README.md` 와 `.txt` 는 든 적이 없다).

    못 보는 것. squash 로 병합된 뒤 main 을 합친 브랜치에서는 merge-base 가 그 병합 커밋으로
    옮겨 가 이 브랜치가 더한 일지가 사라지고 `--journal` 은 1로 끝난다(명세 "최신 일지를 찾는
    법"의 못 보는 것이다). 이름만 바뀐 일지(`git mv`)는 더한 파일이 아니라 `--diff-filter=A` 에
    잡히지 않는다.
    """
    added = git(
        root,
        "diff",
        "--merge-base",
        f"{REMOTE}/{trunk_names(root)[0]}",
        "--name-only",
        "--diff-filter=A",
        "--",
        f"{JOURNAL_DIR}/",
    )
    fresh_files = git(root, "ls-files", "--others", "--exclude-standard", "--", f"{JOURNAL_DIR}/")
    paths = {line for line in [*added.splitlines(), *fresh_files.splitlines()] if line}
    names = [
        path
        for path in paths
        if PurePosixPath(path).parent.as_posix() == JOURNAL_DIR
        and JOURNAL_ANY.match(PurePosixPath(path).name)
    ]
    return sorted(names, key=lambda path: journal_order(PurePosixPath(path).name))


def _print_journal(start: Path) -> int:
    root = Path(git(start, "rev-parse", "--show-toplevel").strip()).resolve()
    found = branch_journals(root)
    if not found:
        print("이 브랜치가 더한 일지가 없다", file=sys.stderr)
        return 1
    print(found[-1])
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    where: str | None = args.path
    move: bool = args.move
    start = Path(where) if where else Path.cwd()
    if args.journal:
        try:
            return _print_journal(start)
        except SurveyError as error:
            print(f"이 브랜치의 일지를 찾지 못했다. {error}", file=sys.stderr)
            return 2
    check = _move_and_check if move else _check
    try:
        result, verdict = check(start)
    except SurveyError as error:
        print(f"형제를 대조하지 못했다. {error}", file=sys.stderr)
        print(ON_FAILURE, file=sys.stderr)
        return 2
    except StuckMoveError as error:
        print(f"번호를 옮기지 못했다. {error}", file=sys.stderr)
        print(ON_STUCK, file=sys.stderr)
        return 2
    except MoveError as error:
        print(f"번호를 옮기지 못했다. {error}", file=sys.stderr)
        print(ON_FAILURE, file=sys.stderr)
        return 2
    print(render(result, verdict))
    return verdict.code


def _prepare(start: Path) -> tuple[Path, Remote]:
    """저장소 루트를 찾고 원격을 읽어 fetch 한다."""
    root = Path(git(start, "rev-parse", "--show-toplevel").strip()).resolve()
    return root, fetch(root, read_remote(root))


def _check(start: Path) -> tuple[Survey, Verdict]:
    """대조한다."""
    root, remote = _prepare(start)
    result = survey(root, remote)
    return result, judge(result)


def _kept_lines(
    root: Path, commits: Sequence[str], paths: Iterable[str]
) -> dict[str, frozenset[str]]:
    """파일마다 `commits` 의 판에 있는 줄(줄 끝의 CR 은 뺀다). 그 판에 없으면 빈 집합."""
    trees = [Tree(root, commit) for commit in commits]
    return {
        path: frozenset(line.rstrip("\r") for tree in trees for line in tree.text(path).split("\n"))
        for path in paths
    }


def _move_and_check(start: Path) -> tuple[Survey, Verdict]:
    """대조하고, 옮길 번호가 있으면 옮긴 뒤 다시 대조한다."""
    root, remote = _prepare(start)
    result = survey(root, remote)
    verdict = judge(result)
    if not verdict.shifted:
        print("옮길 번호가 없어 옮기지 않았다")
        return result, verdict
    kept = _kept_lines(root, (result.base, result.main.commit), result.changed)
    plan = plan_moves(root, result.ours, verdict.shifted, result.changed, kept)
    apply_moves(root, plan)
    print(_moved_line(verdict.shifted, plan))
    report_own_pulls(root, verdict.shifted)
    result = survey(root, remote)
    return result, judge(result)


def report_own_pulls(root: Path, shifted: Sequence[Move]) -> None:
    """origin 이 GitHub 이고 브랜치 위일 때 이 브랜치의 열린 PR 본문을 옮길 번호에 대 보고, 옮긴
    본문을 파일에 써서 그 줄을 찍는다(대기열 376)."""
    repo = github_repo(git(root, "remote", "get-url", REMOTE))
    branch = current_branch(root)
    if repo is None or branch is None:
        return
    bodies = own_pull_bodies(root, *repo, branch)
    written = write_moved_bodies(moved_bodies(bodies, shifted)) if bodies is not None else {}
    for line in pull_body_lines(bodies, written, repo):
        print(line)


if __name__ == "__main__":
    sys.exit(main())
