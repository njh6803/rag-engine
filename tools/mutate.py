"""바이트 그대로 되돌리는 변이 도구.

테스트가 무엇을 재는지 변이로 본다. 구현 전부터 초록인 가드, 구현 뒤에 쓴 테스트, 새 검사가 그
대상이다. 세션마다 스크래치에 변이 스크립트를 새로 짓다가 같은 함정을 두 번 밟아서 여기 있다(대기열
29). 텍스트로 되돌려 줄 끝이 CRLF 가 됐고, 기대 결과를 받지 않아 아무것도 재지 않은 변이가 초록으로
지나갔다. pytest 밖의 명령(Vitest, Playwright, tsc)도 돈다. web 티켓 03~08이 같은 규약의 JS 러너를
저마다 지었고 첫 판정이 틀렸다(대기열 59, tsc 의 종료 코드 2를 빨강으로, TS1360 을 문법 오류로).

사용: PYTHONUTF8=1 uv run python tools/mutate.py <변이 파일.toml> [이름|번호 ...] [--since <커밋>]
          [--check]
      uv run python tools/mutate.py --check <변이 파일.toml> <변이 파일.toml> ...
      uv run python tools/mutate.py --staged
LLM 테스트가 대상이면 `PYTHONUTF8=1 uv run --env-file .env python tools/mutate.py …` 이고 tests 에
`-m llm`(위젯의 실제 모델 e2e 면 `-m llm_widget`)을 넣는다. `--check` 는 원문만 본다 — 명령을 돌리지
않고, 고른 변이마다 원문이 파일에 정확히 한 번 있는지(와 러너의 자리, 되돌릴 파일)를 보고 틀린 것을
모두 알린다. 코드를 고친 뒤 다른 변이 파일의 원문이 옮겨 가지 않았는지 볼 때 쓴다. `--check` 만 변이
파일 여럿(`.toml` 로 끝나는 인자)을 받고, 그때는 이름·번호·`--since` 를 섞지 않는다. 고르지 않고
주면 줄마다 그 파일의 경로가 붙고 읽지 못한 파일이 있어도 나머지를 본다. 이름·번호·`--since` 로
고른 `--check` 와 변이를 돌리는 실행은 표지의 메아리(아래 표지 절)도 본다. 고른 `--check` 는 표지의
품질(표지 없는 빨강, 단언 풀이 줄 표지, 호출 한 토막 표지)도 본다.

`--staged` 는 커밋에 들 판(색인)에서 원문을 보고, pre-commit 이 커밋마다 띄운다. 이 커밋이 더하거나
고친 표(`*_mutations.toml`)는 모든 원문을 보고, 그 표에서 어느 부모 판과도 다른 변이는 표지의
메아리를 색인의 시험 파일로 보고 표지의 품질(표지 없는 빨강, 단언 풀이 줄 표지, 호출 한 토막
표지)도 본다. 변이를
돌린 뒤 `ruff format` 이 코드를 고쳐 커밋한 표의 원문이 사라진 일이 있었다(대기열 92). 커밋에 들지
않은 표는 이 커밋이 고친 파일(지우거나 옮긴 것 포함)을 가리키는 변이만 보고, 부모 판에서 맞던 원문이
색인에서 깨졌을 때 알린다. 표가 가리키는 코드만 바뀌고 표는 커밋에 들지 않아, 커밋에 든 표만 보던
확인을 지나 원문이 0번인 표가 남았다(대기열 312). 부모 판에서도 맞지 않던 원문은 썩어도 되고(대기열
73·92), 다시 돌리거나 그 표를 고쳐 커밋할 때 이 확인이 알린다. 합치는 중이면(`MERGE_HEAD`) 표가
색인과 같은 부모 모두에서 맞던 원문만 본다. main 을 합치는 커밋을 가지의 HEAD 하나와만 견주면 main
의 변경이 모두 들어, main 이 이미 깬 원문을 그 커밋의 탓으로 읽는다. 색인을 읽으므로 ruff 훅이 고친
바이트는 다음 시도에서 본다(고친 시도는 pre-commit 이 실패로 끝낸다). `git commit <경로>` 는 임시
색인을 `GIT_INDEX_FILE` 로 훅에 넘기고 이 확인은 그 색인을 본다. 색인에도 어느 부모에도 없는
파일(추적하지 않는 생성물)은 이 커밋이 깰 수 없어 옛 `--check` 처럼 작업 트리에서 읽고, 그래서 그
파일이 있는 체크아웃에서 커밋한다 (`.scratch/design-refresh/probes/checker_mutations.toml` 의 머리
주석). 이 커밋이 추적을 끊은 파일은 작업 트리에 남아도 읽지 못했다고 알린다. 못 보는 것: 색인의
블롭을 그대로 읽어 작업 트리의 줄 끝 변환을 거치지 않는다. `eol=crlf` 인 파일에 CRLF 로 적은 원문은
디스크에서 맞아도 이 확인에서는 0번이다. 이 저장소는 `* text=auto eol=lf` 라 색인과 작업 트리의 줄
끝이 같다. `git commit --amend` 의 훅도 HEAD(고칠 커밋)를 부모로 본다. 그 커밋이 훅을
건너뛰고(`--no-verify`) 넣은 깨진 원문은 부모 판에서도 맞지 않던 원문으로 읽혀 amend 에서 지나간다.

고르기. 이름, 번호, `--since <커밋>` 으로 고르고 함께 주면 합친다. 아무것도 주지 않으면 전부다.
번호는 표에 적힌 차례(1부터)이고, 출력의 줄 머리와 어긋났을 때의 마지막 줄(`다시 돌릴 번호`)에
찍힌다. 이름은 공백이 들어 따옴표 인자가 필요한데 워크트리 가드가 그런 인자를 거부한 적이 있어,
고를 때는 번호나 `--since` 를 쓴다(대기열 193). 그래서 이름을 숫자로만 짓지 않는다. `--since` 는
그 커밋에 있던 같은 표와 견주어 새로 더했거나 무엇이든(원문, 기대, 시험, 시간 제한, 그 변이가 쓰는
러너) 달라진 변이를 고른다. 그 커밋에 표가 없으면 모두 새것이다. 고를 것이 없으면 아무것도 돌리지
않고 2로 끝난다. 잘못 준 커밋이 0 으로 끝나면 잰 것처럼 보이기 때문이다. 줄 커밋은 그 표를
마지막으로 돌린 커밋이다(일지의 검사 절에 적어 둔다). 이 브랜치가 더하거나 고친 변이만 보려면
기준 ref(`hotfix/*` 는 `origin/main`, 그 밖은 `origin/dev` 가 있으면 그것, 없으면 `origin/main`)다.
커밋한 표를 다른 워크트리에서 돌리며 `HEAD` 를 주면 표가 같아 고를 것이 없다.
언제 전체를 돌리나: 시험을 고치거나 지웠으면 전체, 시험을 더하기만 했거나 코드만 바꿨으면 고른
것(원문을 고쳤거나 더한 변이)이다. 견주는 쪽은 그 표를 마지막으로 돌린 판이다. 시험을 더해서는
빨갛던 변이가 초록이 되지 않지만, 고치거나 지우면 다른 변이를 잡던 단언이 사라질 수 있다. 시험을
고친 판에서 그런 일을 전체 실행이 잡았다(일지 2026-10-12-16의 둘째 판). 전체 실행은 셀프 리뷰와
PR 직전 리뷰(보안·버그·성능)를 반영해 커밋한 뒤에 한 번 돈다. 리뷰가 시험을 고치면 그 전의 실행은
옛 시험을 잰 것이라, 리뷰 전에 띄운 묶음을 멈추고 다시 돌렸다(셀프 리뷰 전에 약 15분, 대기열 265.
PR 직전 리뷰 전에 약 13분, 일지 2026-10-16-07). 이 문장을 두고도 리뷰 전에 새 표 둘의 전체를 돌려
다시 돌았다(대기열 359). 그래서 고르지 않은 전체 실행은 시작 줄에서, 표 자체(표지가 여기 있다)나
표가 가리키는 파일이나 그 시험(`tests` 인자 가운데 러너의 자리 기준으로 있는 파일, `::` 뒤는 뗀다)에
커밋하지 않은 변경이 있으면 그 경로를 알린다. 리뷰 전 실행을 가리키는 대리 신호라 막지 않는다. git
저장소 밖이면 말하지 않는다. 못 보는 것: 코드만 바꾼
판에서 원문이 그대로인 변이도 둘레의 코드가 바뀌어 결과가 달라질 수 있다. 시험을 더하면 초록을
기대한 변이(대조군)가 빨개질 수 있다(일지 2026-10-12-29, `mutate_restore` 표). 고른 것만 돌리면 둘
다 보지 못한다.

변이 파일은 TOML 이다. 원문은 리터럴 여러 줄 문자열(`'''`)로 적으면 이스케이프가 없다. 여는 `'''`
바로 뒤의 줄바꿈은 TOML 이 버리지만 닫는 `'''` 앞의 줄바꿈은 원문에 든다. 그래서 닫는 `'''` 를 다음
줄에 두는 원문은 마지막 줄을 줄 끝까지 온전히 적고, 줄의 일부만 적을 때는 닫는 `'''` 를 같은 줄에
둔다(줄의 일부만 적은 원문 넷이 `--check` 에서 걸렸다, 대기열 152). 아래 예시는 네 칸 들여쓴 채라
옮길 때 그 네 칸을 걷어 낸다.

    [runner.vitest]                      # 선택. 이름은 마음대로이고 pytest 만 내장이라 못 쓴다
    command = ["pnpm", "exec", "vitest", "run"]
    cwd = "web"                          # 저장소 루트 기준. 기본은 루트
    judge = "vitest"                     # pytest, vitest, playwright, tsc, exit
    # red_exit = 1                          exit 판정이면 반드시(1 이상). 빨강으로 읽을 종료 코드
    # baseline_output = ["검사 12"]          선택. 기준선 출력에 있어야 할 표지

    [[mutation]]
    name = "꺼짐을 깨짐 앞에"
    runner = "pytest"                    # 선택. 기본은 내장 pytest(-q -p no:cacheprovider)
    tests = ["tests/core/test_run.py"]   # 명령 뒤에 붙는다. -k(pytest), -t(vitest)로 좁힌다
    expect = "red"                       # red, green, 또는 unhandled(vitest 판정만)
    repeat = 1                           # 선택. 매번 기대와 같아야 한다
    timeout = 600                        # 선택. 한 번 돌리는 시간 제한(초). 기본 600
    # diagnostic_in = "clients.test-d.ts"   tsc 판정이면 반드시. 빨강이 날 파일
    # expect_output = ["이름이 없다: a"]      선택. 매 반복의 출력에 있어야 할 표지
    # restore = ["web/gen/openapi.ts"]      선택. 명령이 고쳐 쓸 수 있어 되돌릴 파일

    [[mutation.edit]]                    # 여럿이면 차례로 들어간다
    file = "src/agent_os/core/run.py"    # 저장소 루트 기준
    old = '''
        servers = _resolve_servers(plugins, manifest)
        _reject_masked_approvals(manifest, servers)
        _reject_disabled(plugins.read_disabled(), manifest)
    '''
    new = '''
        _reject_disabled(plugins.read_disabled(), manifest)
        servers = _resolve_servers(plugins, manifest)
        _reject_masked_approvals(manifest, servers)
    '''

판정(`judge`). 종료 코드만으로는 빨강과 오류를 가를 수 없는 명령이 있어 판정마다 출력의 요약을
읽는다. 오류는 기대가 무엇이든 어긋남이다 — 문법 오류로 모든 것이 빨간 변이는 테스트의 이빨을 재지
않는다.
- pytest: 종료 코드 0 은 초록, 1 은 빨강, 나머지(수집 오류, 없는 경로, 선택된 테스트 없음)는 오류다.
  0 이어도 skip 이 섞였으면 오류다. 재지 않은 테스트가 있다(원칙 I).
- vitest: 종료 코드가 실패, 수집 오류, 처리하지 않은 에러에 모두 1 이다. 요약의 `Tests` 줄에 실패가
  셀 때만 빨강이고, 파일 단위의 FAIL(`[ 파일 ]` 로 끝나는 줄, 수집 오류)이 하나라도 있으면 오류다.
  실패 없이 `Errors` 줄만 있으면 처리하지 않은 에러(unhandled)다. 가드가 막는 것이 그것뿐인 변이는
  그것을 기대로 적는다. 초록은 통과한 테스트가 하나 이상일 때다.
- playwright: 요약에 `N failed` 가 셀 때만 빨강이다. 초록은 종료 코드 0 에 통과가 있고 skip 이 없을
  때다.
- tsc: 종료 코드가 문법 오류와 타입 에러에 같고(2) 오류 번호로도 가를 수 없다(`satisfies` 의
  어긋남이 TS1360 이다). 빨강은 `diagnostic_in` 파일에서 난 진단이고, 그 파일 밖에서만 나면 오류다.
  `diagnostic_in` 은 진단 경로의 꼬리로 맞춘다. 이름만 적으면 다른 디렉터리의 같은 이름
  (`index.ts`)도 맞으니, 이름이 겹치면 디렉터리까지 적는다.
- exit: 종료 코드로만 말하는 명령(node 검사기)이다. 0 은 초록, 러너의 `red_exit` 는 빨강,
  나머지(읽을 파일이 없다는 2 따위)는 오류다. 검사기 변이를 따로 짓던 프로브를 표로 옮기려고
  더했다(대기열 253).

표지(`expect_output`, `baseline_output`). 판정이 기대와 맞아도 엉뚱한 까닭의 빨강일 수 있다
(`.claude/rules/probes.md` 의 표지 항목). 그래서 변이마다 출력에 있어야 할 문구를 적을 수 있고, 색
코드를 벗긴 출력에서 매 반복 찾는다. 하나라도 없으면 `표지 없음: …` 줄과 출력의 끝 10줄, 그 앞의
실패 머리 줄을 내고 어긋남으로 센다. 머리 줄은 `AssertionError`·`TypeError` 처럼 `Error` 로 끝나는
낱말로 시작하는 줄, `Expected`·`Received` 로 시작하는 줄, diff 의 `-`·`+` 줄이다. 들여쓴 줄도
받고 앞에서 스무 줄까지 낸다. 표지를 고르려고 돌린 출력에서 고른 단언의 머리가 끝 10줄 밖이어도
보인다(대기열 455). 러너의 `baseline_output` 은 기준선에서 같은 일을 한다. 없으면 기준선은 초록이
아니다. 종료 코드 0 만으로는 아무것도 읽지 않고 끝난 검사기와 가를 수 없다. 빈 문자열은 어느
출력에나 있어 변이 파일 오류다. 러너가 어느 실패나 통과에나 찍는 판정 낱말(`_VERDICT_WORDS`. pytest
의 `failed`·`passed`·`error`, vitest 의 `FAIL`, playwright 의 `passed` 따위, 대소문자를 가리지
않는다)만으로 된 표지도 같은 까닭으로 변이 파일 오류다. 숫자와 기호는 낱말로 세지 않아 `1 failed` 도
걸린다. `["failed"]` 를 표지로 골랐더니 pytest 의 요약 줄과 단언 dict 의 `"type": "failed"` 에 늘
실려 고른 단언이 빨개졌다는 표지가 되지 못했다(대기열 313). exit 판정은 요약을 읽지 않아 거를 낱말을
두지 않는다. 못 보는 것: 판정 낱말이 아닌 낱말이 하나라도 섞이면 받는다(`test failed` 의 `test`).
exit 러너의 명령이 pytest 여도 그 출력의 판정 낱말을 거르지 않는다(`["failed"]` 를 받는다). 머리
줄도 못 보는 것이 있다. 고르는 상한이 끝에서가 아니라 맨 앞에서 스무 줄이라, 실패가 여럿 쌓인
출력에서는 앞 블록의 줄이 상한을 채워 마지막 실패 블록의 머리가 안 보일 수 있다. 줄 머리만 보므로
`Error` 만 있는 줄과 `- ` 로 시작하는 목록 줄도 머리로 받아 상한을 소음이 채울 수 있다. 반대로
pytest 의 `E ` 접두 줄(`E       TypeError: x`)은 받지 않는다.

표지의 메아리. 빨강이나 처리하지 않은 에러를 기대한 변이의 표지가 그 시험 파일(`tests` 인자 가운데
옵션이 아닌 것을 러너의 자리 기준으로 이은 경로, `::` 뒤는 뗀다)의 원문에 글자 그대로 있으면
알린다. 시험 함수 이름은 실패 머리에, 기대 값의 글자는 실패 줄 둘레의 코드 조각에 늘 실려, 그
시험의 어느 단언이 빨개져도 표지가 맞는다. 표지 스물여덟을 시험 함수 이름으로 골랐고, 기대 배열의
글자가 코드 조각에 실린 일도 있었다(대기열 417). 원문만 보는 확인은 이름·번호·`--since` 로 고른
`--check` 와 `--staged` 의 새 변이만 본다. 옛 변이는 소급하지 않고 그 변이를 고칠 때 본다. 변이를
돌리는 실행(전체와 고른 것)은 돌릴 변이를 모두 1단계에서 보고, 걸리면 기준선 전에 끝낸다. 다시
돌리는 변이는 지금 재는 것이다. 실행만 메아리를 보지 않아, 표지 열여덟이 시험 함수 이름인 채로 표
전부가 기대대로를 찍었다(대기열 502). 초록을 기대한 변이는
실패 머리와 코드 조각을 찍지 않아 보지 않는다. 못 보는 것: 파일 단위로 맞대어, 같은 파일의 다른
시험에만 있는 글자도 알린다(거짓 양성, 그 시험이 빨개질 때는 실리지 않는다). 폴더 인자는 그 안의
파일을 보지 않는다(거짓 음성). 원문의 이스케이프(`\\"`)와 출력의 글자가 달라 글자 그대로 맞지 않는
메아리는 놓친다.

표지의 품질. 빨강(`expect = "red"`)을 기대한 변이의 표지에서 셋을 더 알린다. 고른 `--check` 와
`--staged` 의 새 변이만 보고 변이를 돌리는 실행에는 걸지 않는다. 옛 표 3613 변이 가운데 빨강을
기대하고 표지가 없는 것이 1883, 단언 풀이 줄 표지를 든 빨강이 176이라(`.scratch/**/*_mutations.toml`
을 `tomllib` 로 읽어 손으로 셌다) 돌리는 실행에 걸면 옛 표를 다시 돌릴 때마다 멈춘다.
- `expect_output` 이 없다. 다른 까닭으로 빨개져도 기대와 맞아, `wait_ci` 변이 열다섯이 표지 없이
  두 리뷰를 지났다(대기열 350). 초록과 처리하지 않은 에러를 기대한 변이는 보지 않는다.
- 러너의 판정이 pytest 인데 표지가 pytest 가 단언을 풀어 쓴 줄(`where 1 = run()`,
  `assert 0 == 1`)이다. `E` 와 `+` 접두와 들여쓰기가 앞에 있어도 같은 줄로 보고 알린다. 시험이 다른
  까닭으로 빨개져도 그 호출과 값이 실려, 러너가 다른 까닭으로 멈춰도 맞았다(대기열 517). 단언에 싣는
  메시지나 변이를 손으로 넣어 본 실패 출력의 원인 문구로 고른다.
- 같은 판정인데 표지의 줄 머리가 호출 한 토막(`matches(server='x', tool='add')`, `Rule(server=None,
  tool='*')`)이다. `+  where False = matches(…)` 줄에서 머리를 뗀 부분 문자열만 골라 풀이 줄 머리
  기준을 지났다. 그 줄은 다른 단언이 빨개져도 실려 맞았다(대기열 579). `이름(` 뒤가 인자처럼
  생긴 것(`)`, 따옴표나 괄호, 숫자나 식별자 뒤의 `,` `)`, 식별자 뒤의 `=` `,` `)` `(`)만 받는다.
  인자 줄(`rule = Rule(…)`), 비교 실패의 diff 줄(`At index 0 diff: Hit(…)`)은 줄 머리가 호출이
  아니라 알리지 않는다. 옛 표 pytest 판정의 빨강 표지 1330개 가운데 줄 머리가 `이름(` 꼴인 것은
  12개였고, 그중 열이 이 규칙에 걸리고 둘(`zeta(7회차) …` 목록 출력)은 인자처럼 생기지 않아
  걸리지 않는다(`.scratch/**/*_mutations.toml` 을 `tomllib` 로 읽어 손으로 셌다).
못 보는 것: 줄 머리만 본다. `AssertionError: assert 0 == 1`, `AssertionError: matches('a')` 처럼
앞에 낱말이 붙은 줄은 받는다. 호출 꼴이지만 값의 repr 인 줄 머리(`Hit(ident='0001', rounds=None`)는
고른 단언만 찍는 줄이어도 풀이 줄과 갈라 볼 수 없어 알린다(거짓 양성). 인자가 정수 하나나 식별자,
따옴표로 바로 시작하는 문자열이 아니면 받는다(거짓 음성). `f(1.5)`, `f(b'x')`·`f(f'x')`,
`f(*args)`, `f(-x)`, `f(x[0])`, `f(안녕)` 과 인자가 줄 끝에서 끊긴 `Rule(` 이 그 예다. `==` 만 본다.
`assert 1 != 1`, `assert 'a' in b`, `assert x is None` 처럼 pytest 가 풀어 쓰는 다른 비교는
받는다(거짓 음성). 반대로 단언에 싣는 메시지가 `assert 결과 == 'done'` 처럼 `assert` 로 시작해 `==`
를 들면 풀이 줄과 갈라 볼 수 없어 알린다(거짓 양성). pytest 가 아닌 판정의 표지는 보지 않는다.
판정이 exit 인 러너의 명령이 pytest 여도 보지 않는다. 표지가 있어도 고른 단언이 빨개졌다는
표지인지는 가를 수 없다(이 확인은 없거나 알려진 나쁜 모양만 본다).

하는 일, 차례대로:
1. 변이 파일의 모양과 러너·판정의 짝을 보고, 변이마다 원문이 파일에 정확히 한 번 있는지, 러너의
   자리와 되돌릴 파일이 저장소 안에 있는지, 표지가 메아리가 아닌지 본다. 하나라도 틀리면 아무
   파일도 쓰지 않고 끝낸다.
2. 러너와 인자의 짝마다 변이 없이 한 번씩 돌린다(기준선). 시간 제한은 그 짝을 쓰는 변이 가운데
   가장 긴 것이다. 초록이 아니면 변이를 넣지 않는다. 기준선이 빨간데 변이가 빨가면 그 빨강은
   아무것도 말하지 않는다. 이름으로 좁힌 선택이 비었는지도 여기서 본다.
3. 빨강을 기대한 내장 pytest 러너의 변이는 인자 끝에 `-x` 를 붙여 첫 실패에서 멈춘다. 빨강은 실패
   하나로 정해지고 `-x` 도 종료 코드 1 이라 판정이 같다. 기준선과 초록을 기대한 변이는 끝까지 돈다.
   표의 러너는 pytest 판정을 빌려도 pytest 가 아닐 수 있어(`tools/run_hooks.py`) 붙이지 않는다.
   sibling_overlap 표본 여섯을 이 규칙 전의 도구로 표에 `-x` 를 적어(기준선에도 붙었다) 견주니
   변이 몫이 약 351초에서 79초가 됐고 판정이 같았다(대기열 231,
   `.scratch/harness/probes/mutate_231/`).
4. 변이마다 원래 바이트(되돌릴 파일 포함)를 쥐고 변이를 넣어 돌린 뒤 `finally` 에서 그 바이트를
   그대로 쓴다. 쓰기 전에 편집한 파일이 쓴 변이 바이트 그대로인지 본다. 다르면 변이가 든 동안 다른
   쓰기(편집기, 다른 세션)가 들어온 것이라 덮지 않고 알린다(대기열 77). 되돌릴 파일(`restore`)은
   명령이 고쳐 쓰는 파일이라 보지 않고 쓴다. 되돌리는 읽기와 쓰기가 `OSError` 로 막히면 각각
   `RESTORE_WAITS`(합 3.7초) 동안 기다리며 다시 시도한다. 변이 87번째를 되돌리는 쓰기가 `[Errno 22]
   Invalid argument` 로 한 번 막혀 3으로 멈추고 변이가 도구 파일에 남았다(대기열 267, 일지
   2026-10-15-06). 다른 쓰기는 처음 읽은 바이트로 한 번만 본다. 되쓰는 동안 끊겨도(Ctrl+C) 그 파일을
   남은 파일로 적고 나머지 파일을 마저 되쓴 뒤 3으로 멈춘다. 명령 한 번이 시간 제한(`timeout`)을
   넘기면 그 명령이 띄운 프로세스까지 끝내고(못 보는 것은 아래), 끊기 전의 출력이 무엇이든 오류로
   판정한 뒤 남은 반복(`repeat`)을 건너뛰고 되돌려 다음 변이로 간다. 검사 러너의 변이가
   러너→pytest→러너로 되풀이하며 10분 넘게 돌았고, 손으로 죽이자 변이된 한 줄이 파일에 남았다(대기열
   139). 기다리는 동안 예외(Ctrl+C 의 `KeyboardInterrupt`)가 올라와도 띄운 프로세스까지 끝낸 뒤
   되돌린다. 윈도우에서 실제 Ctrl+C 가 그 기다림을 끊는지는 재지 않았다(시험은 그 예외를 넣는다).
5. 종료 코드: 모두 기대대로면 0, 어긋나거나(시간 제한을 넘긴 것 포함) 기준선이 초록이 아니면 1,
   변이 파일을 읽지 못했거나 틀렸거나 고른 것이 없으면 2(아무 파일도 쓰지 않았다), 테스트를 돌리지
   못했거나 되돌리지 못했으면 3.

제자리가 아닌 실행. 변이는 이 도구가 든 체크아웃을 고친다. 도는 동안(web 변이 수십 개는 40분이
넘는다) 그 체크아웃을 고치거나 소스를 읽는 리뷰를 띄우면 변이된 소스를 본다. 그래서 잴 코드를
커밋하고 다른 워크트리에서 그 워크트리의 도구로 돌린다. 변이 파일은 어느 경로여도 되고 편집의 `file`
은 도는 도구가 든 체크아웃 기준이다. pnpm 은 저장소(store)에서 링크만 해 네트워크를 타지
않는다(2026-10-01 13초, 일지 2026-10-01-01). `.env` 는 추적하지 않으므로 LLM 변이면 새 워크트리에
복사한다. 변이가 끝나면 지우는 워크트리라 사본이 남지 않는다. 남겨 두고 일하는 워크트리는 사본을
만들지 않고 `--env-file` 로 주 체크아웃의 것을 읽는다(operations.md LLM 테스트). 에이전트의
명령 상한(10분)을 넘는 실행은 백그라운드로 돌린다. 바깥에서 이 도구를 죽이는 것(셸의 `timeout`
명령, 백그라운드 실행의 상한)은 아래 못 보는 것의 강제 종료라 되돌림이 돌지 않을 수 있다. 시간은
변이마다의 `timeout` 으로 걸고, 바깥의 상한은 표 전체보다 넉넉히 준다. 도는 동안 변이한 파일을
고치면(되돌릴 파일로 적지 않았으면) 되돌림이 그 파일을 덮지 않고 3으로 멈추고, 변이는 손으로 걷어
낸다. 백그라운드로 띄운 표 묶음을 `TaskStop` 으로 멈추면 윈도우에서 묶음을 돌리던 셸 스크립트와 그
아래 프로세스가 남아 다음 표를 이어 돌았다(일지 2026-10-15-13·2026-10-16-07·2026-10-19-13). 셋째에는
찾기가 `python.exe` 에 머물러 묶음을 돌리던 `bash.exe` 와 `uv.exe` 를 놓쳤고, 그 약 17분 동안 변이가
든 체크아웃에서 이 도구와 그 시험을 고쳤다(대기열 358). 멈춘 뒤 명령줄에 표 파일 이름이나 묶음
스크립트가 든 `bash.exe`·`uv.exe`·`python.exe` 를 찾아(묶음이 상대 경로로 띄우면 명령줄 경로도 상대
경로이고, 일지 2026-10-19-13 이 그랬다) 가장 위의 것을 `taskkill /T /F` 로 끝내고, 변이가 남았는지
`git status` 로 본다. 그래서 도는 동안(기준선부터 마지막 되돌림까지) 이 체크아웃의 git
디렉터리(워크트리면 `.git` 파일이 가리키는 곳)에 `mutate-running-<pid>.json`(pid 와 표의 절대
경로와 이 프로세스의 시작 시각)을 두고 끝나면 예외로 끝나도 지운다. PostToolUse 계기 훅
`tools/hook_edit_during_mutate.py` 가 그 체크아웃의 파일을 고칠 때 표지의 pid 가 살아 있고 그
시작 시각이 같으면 알린다. 강제로 끝나 남은 표지는 pid 가 죽었거나, 그 pid 를 받은 다른 프로세스의
시작 시각이 달라 알리지 않는다(대기열 449). 시작 시각을 읽지 못하는 OS 에서는 그 칸을 적지 않아
훅이 pid 만으로 본다(그 훅의 못 보는 것). 원문만 보는 `--check` 와 `--staged` 는 파일을 쓰지 않아
표지를 두지 않는다.

    git worktree add --detach <임시 경로> HEAD
    (그 경로에서) uv sync
    (그 경로에서) pnpm -C web install --frozen-lockfile --offline    # web 변이일 때
    (그 경로에서) PYTHONUTF8=1 uv run python tools/mutate.py <변이 파일>
    git -c core.longpaths=true worktree remove <임시 경로>

지우기는 `core.longpaths` 를 켜고 친다. 끄고 치면 깊은 경로에서 `Filename too long` 으로 멈춰
등록만 빠지고 폴더가 남는다(`.scratch/harness/probes/worktree_longpath.py`). `uv sync` 를 친 임시
워크트리에서 그렇게 남았다(일지 2026-10-23-23).

바이트코드 캐시는 소스의 수정 시각(초)과 크기로만 맞춰 보므로, 크기가 같은 변이가 같은 초에 쓰이면
낡은 캐시가 돈다. 그래서 변이를 쓴 직후와 되돌린 직후에 그 소스의 `__pycache__/<이름>.*.pyc`(CPython
의 것과 pytest assertion rewrite 의 것)를 지우고, 하위 명령은 `PYTHONDONTWRITEBYTECODE=1` 로 돌아
변이된 소스의 캐시를 새로 남기지 않는다. `-p no:cacheprovider` 는 변이의 실패가 `.pytest_cache` 의
lastfailed 에 남지 않게 한다.

못 보는 것: 프로세스가 강제로 죽으면(`finally` 가 돌지 않으면) 되돌리지 못한다. 되돌리는 쓰기가
다시 시도해도 막히거나(파일이 잠겼다) 다른 쓰기가 들어왔으면 나머지 파일은 되돌리고 남은 파일을
알린다. 세 경우
모두 `git diff` 로 본다. 되돌릴 파일(`restore`, 편집한 파일을 함께 적은 것 포함)에 든 다른 쓰기는
명령의 쓰기와 가를 수 없어 덮는다. 편집한 파일을 읽은 뒤 쓰기까지의 틈에 든 쓰기도 덮는다. 틈은
다음과 같다.
- 원래 바이트를 읽고 변이를 쓰기까지.
- 되돌리기 전에 읽어 보고 다시 쓰기까지. 쓰기가 막혀 다시 시도하면 그 기다림(최대 3.7초)만큼
  길어진다.
- 앞 파일의 변이 쓰기가 실패해 변이를 쓰지 못한 파일이면, 처음 읽은 뒤 되돌리기까지. 쓴 변이
  바이트가 없어 보지 않는다.

시간 제한으로 끝내는 프로세스는 윈도우에서 `taskkill /T` 가 부모를 따라 찾은 것이고, POSIX 에서는
자식이 이끄는 프로세스 그룹이다. 부모가 먼저 끝나 고아가 된 손자(윈도우)와 제 세션이나 프로세스
그룹을 따로 연 손자(POSIX)는 남는다. 남은 것이 출력 파이프를 쥐면 끊은 뒤 10초만 출력을 기다리고
그만 읽는다. 이 판단은 윈도우 10(19045)의 `taskkill` 과 CPython 3.12.10 위에서 시험으로 봤다.

원문의 줄 끝은 파일과 같아야 한다 — 변이 파일의 `\\n` 은 CRLF 파일에서 맞지 않는다. 0번인 원문이
줄 끝을 맞춘 바이트에서 찾히면, 변이 파일 오류와 `--check` 가 "줄 끝이 다르다" 와 함께 파일의 줄
끝과 줄 끝을 맞춘 횟수를 덧붙인다. 패치 스크립트의
`Path.write_text` 가 윈도우에서 도구를 CRLF 로 바꿔 써 원문 스무 개 남짓이 0번으로만 나왔고, git 은
커밋에서 LF 로 고쳐 diff 로는 보이지 않았다(대기열 264). 0번인 원문이 글자 그대로의 `\\n`·`\\t`
를 들고 그것을 푼 바이트에서 찾히면, TOML 의 작은따옴표 문자열은 이스케이프를 풀지 않는다는 까닭과
푼 횟수를 덧붙인다. 작은따옴표로 적은 `\\n` 이 풀리지 않아 원문이 0번이었고 도구는 "0번 있다" 만
알렸다(대기열 317). 줄 끝 힌트가 먼저이고, 둘을 함께 맞춰 보지는 않는다. vitest 의 skip
은 세지 않는다. `-t` 로 좁히면 고르지 않은 테스트가 skipped 로 세어져 `it.skip` 과 가를 수 없다. tsc
의 빨강은 진단이 난 파일만 본다. 변이가 낸 문법 오류가 적은 파일까지 번져도 빨강이다. 윈도우에서
`pnpm.CMD` 같은 배치 파일은 cmd.exe 가 돌려 인자의 `&`·`%`·`^` 가 해석될 수 있다. 좁힌 선택이 비면
기준선이 오류로 잡는다(통과가 없다). 표지는 출력 어디서든 부분 문자열로 찾는다. 다른 까닭의
실패가 같은 문구를 찍으면(같은 이름의 다른 검사) 표지가 있는 것으로 센다. `-x` 로 멈춘 변이는
빨간 시험을 첫 하나만 보인다. 그 변이가 빨갛게 할 시험이 몇인지는 남지 않고, 뒤의 시험만 찍는 표지는
없어 어긋남으로 센다. 뒤의 시험이 걸려 끝까지 돌면 시간 제한을 넘겼을 변이도 첫 실패에서 멈춰
빨강이다. exit 판정은 종료 코드만 본다. node 는 잡히지 않은 예외에도 1 로 끝나, 변이가 입력을 깨
검사기가 던진 것도 `red_exit = 1` 의 빨강이다. 그런 변이는 표지로 까닭을 가른다.

판정은 출력의 요약 문구에 기댄다. 초록과 빨강을 읽는 문구(vitest 의 `Tests` 줄, playwright 의
`N passed`·`N failed`, tsc 의 진단 줄)가 도구의 판에서 바뀌면 오류로 기운다. 초록이나 빨강을
거르는 표지(vitest 파일 단위 FAIL 의 `[ 파일 ]`, pytest·playwright 의 `N skipped`)가 바뀌면 그것을
못 봐 수집 오류가 섞인 실패가 빨강으로, skip 이 섞인 통과가 초록으로 지나간다.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT = 600  # 명령 한 번의 시간 제한(초). 변이마다 `timeout` 으로 바꾼다
_DRAIN_SECONDS = 10  # 끊은 뒤 출력 파이프가 닫히기를 기다리는 시간
_KILL_SECONDS = 30  # 윈도우의 `taskkill` 을 기다리는 시간
# 되돌리는 읽기·쓰기를 다시 시도하기 전에 기다리는 초. `tools/tidy_checkouts.py` 의 같은 이름을
# 따랐다. 변이를 되돌리는 쓰기가 `[Errno 22] Invalid argument` 로 한 번 막혔고(대기열 267), 무엇이
# 그 틈에 파일을 쥐었는지는 재지 않았다
RESTORE_WAITS = (0.2, 0.5, 1.0, 2.0)
# 도는 동안 그 체크아웃의 git 디렉터리에 두는 표지 `mutate-running-<pid>.json` 의 머리. 편집 훅
# `tools/hook_edit_during_mutate.py` 의 같은 이름과 같아야 한다(대기열 358)
MARKER_PREFIX = "mutate-running-"

type Outcome = Literal["green", "red", "unhandled", "error"]
type JudgeName = Literal["pytest", "vitest", "playwright", "tsc", "exit"]

_LABELS: dict[Outcome, str] = {
    "green": "초록",
    "red": "빨강",
    "unhandled": "처리하지 않은 에러",
    "error": "오류",
}
_PYTEST_OUTCOMES: dict[int, Outcome] = {0: "green", 1: "red"}
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_PYTEST_SKIPPED = re.compile(r"\b\d+ skipped\b")
_VITEST_SUMMARY = re.compile(r"^\s*(Test Files|Tests|Errors)\s+(.+?)\s*$", re.MULTILINE)
_VITEST_FAIL = re.compile(r"^\s*FAIL\s+(.+?)\s*$", re.MULTILINE)
_VITEST_FILE_LEVEL = re.compile(r"\[ .+ \]$")
_PLAYWRIGHT_COUNT = re.compile(
    r"^\s*(\d+) (passed|failed|skipped|flaky|interrupted|did not run)\b", re.MULTILINE
)
_PLAYWRIGHT_FAILED = re.compile(r"\s*\d+ failed\s*")
_TSC_DIAGNOSTIC = re.compile(r"(\S+)\((\d+),(\d+)\): error (TS\d+)")
_NUMBER = re.compile(r"[0-9]+")
_WORD = re.compile(r"[^\W\d_]+")  # 표지의 낱말. 숫자와 기호는 낱말이 아니다
# 판정마다 러너가 어느 실패나 통과에나 찍는 낱말(대소문자를 가리지 않는다). 이 낱말뿐인 표지는
# 고른 단언이 빨개졌다는 표지가 되지 못한다(대기열 313). exit 판정은 출력의 요약을 읽지 않는다
_VERDICT_WORDS: dict[JudgeName, frozenset[str]] = {
    "pytest": frozenset(
        {"failed", "passed", "error", "errors", "skipped", "xfailed", "xpassed", "deselected"}
    ),
    "vitest": frozenset(
        {"fail", "failed", "pass", "passed", "error", "errors", "skipped", "todo", "tests"}
    ),
    "playwright": frozenset(
        {"passed", "failed", "skipped", "flaky", "interrupted", "did", "not", "run"}
    ),
    "tsc": frozenset({"error"}),
    "exit": frozenset(),
}


class SpecError(Exception):
    """변이 파일을 읽지 못했거나 틀렸다. 아무 파일도 쓰기 전에 난다."""


class RestoreError(Exception):
    """변이를 되돌리지 못한 파일이 있다. 변이가 든 동안 다른 쓰기가 들어왔거나, 그 파일을 읽거나
    다시 쓰다가 `OSError` 가 났다."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Edit(_Model):
    file: str
    old: str
    new: str


class RunnerSpec(_Model):
    command: list[str] = Field(min_length=1)
    cwd: str = "."
    judge: JudgeName
    red_exit: int | None = Field(default=None, ge=1)  # exit 판정만. 빨강으로 읽을 종료 코드
    baseline_output: list[str] = Field(default_factory=list[str])  # 기준선 출력에 있어야 할 표지


class Mutation(_Model):
    name: str
    runner: str = "pytest"
    tests: list[str] = Field(default_factory=list[str])
    expect: Literal["red", "green", "unhandled"]
    diagnostic_in: str | None = None
    expect_output: list[str] = Field(default_factory=list[str])  # 매 반복의 출력에 있어야 할 표지
    restore: list[str] = Field(default_factory=list[str])
    repeat: int = Field(default=1, ge=1)
    timeout: int = Field(default=DEFAULT_TIMEOUT, ge=1)
    edit: list[Edit] = Field(min_length=1)


class Spec(_Model):
    runner: dict[str, RunnerSpec] = Field(default_factory=dict[str, RunnerSpec])
    mutation: list[Mutation] = Field(min_length=1)


_BUILTIN: dict[str, RunnerSpec] = {
    "pytest": RunnerSpec(
        command=[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], judge="pytest"
    )
}


@dataclass(frozen=True)
class CommandResult:
    """명령 한 번의 결과. 출력은 stdout 뒤에 stderr 를 이은 것이다. 시간 제한을 넘겨 끊었으면
    `timed_out_after` 가 그 제한(초)이고 출력은 끊을 때까지 읽은 것이다. 끊은 뒤에도 출력 파이프가
    닫히지 않아 그만 읽었으면 출력 대신 그 안내 한 줄이다."""

    exit_code: int
    output: str
    timed_out_after: int | None = None

    @property
    def plain(self) -> str:
        """색 코드를 벗긴 출력."""
        return _ANSI.sub("", self.output)


@dataclass(frozen=True)
class Verdict:
    """판정 하나. `failed` 는 빨간 테스트(tsc 면 진단)의 이름이다."""

    outcome: Outcome
    summary: str
    failed: tuple[str, ...] = ()


type Runner = Callable[[Sequence[str], Path, int], CommandResult]  # 명령, 자리, 시간 제한(초)


def _last_line(text: str, exit_code: int) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1].strip("= ") if lines else f"출력 없음(종료 코드 {exit_code})"


def _count(pattern: str, text: str) -> int:
    found = re.search(pattern, text)
    return int(found.group(1)) if found else 0


def _judge_pytest(exit_code: int, text: str) -> Verdict:
    summary = _last_line(text, exit_code)
    failed = tuple(
        line.split(" ", 1)[1].split(" - ", 1)[0]
        for line in text.splitlines()
        if line.startswith(("FAILED ", "ERROR "))
    )
    outcome = _PYTEST_OUTCOMES.get(exit_code, "error")
    if outcome == "green" and _PYTEST_SKIPPED.search(summary):
        outcome = "error"
    return Verdict(outcome, summary, failed)


def _judge_vitest(exit_code: int, text: str) -> Verdict:
    lines = {m.group(1): m.group(2) for m in _VITEST_SUMMARY.finditer(text)}
    summary = ", ".join(f"{key} {value}" for key, value in lines.items())
    tests = lines.get("Tests", "")
    fails = tuple(m.group(1) for m in _VITEST_FAIL.finditer(text))
    outcome: Outcome
    if any(_VITEST_FILE_LEVEL.search(fail) for fail in fails):
        outcome = "error"
    elif exit_code == 0:
        outcome = "green" if _count(r"(\d+) passed", tests) > 0 else "error"
    elif _count(r"(\d+) failed", tests) > 0:
        outcome = "red"
    elif "Errors" in lines:
        outcome = "unhandled"
    else:
        outcome = "error"
    return Verdict(outcome, summary or _last_line(text, exit_code), fails)


def _playwright_failed(text: str) -> tuple[str, ...]:
    """요약의 `N failed` 아래에 들여 적힌 `[프로젝트] › …` 줄들."""
    titles: list[str] = []
    lines = text.splitlines()
    for at, line in enumerate(lines):
        if _PLAYWRIGHT_FAILED.fullmatch(line):
            for follow in lines[at + 1 :]:
                if not follow.strip().startswith("["):
                    break
                titles.append(follow.strip())
    return tuple(titles)


def _judge_playwright(exit_code: int, text: str) -> Verdict:
    counts: dict[str, int] = {}
    for m in _PLAYWRIGHT_COUNT.finditer(text):
        counts[m.group(2)] = counts.get(m.group(2), 0) + int(m.group(1))
    summary = ", ".join(f"{n} {word}" for word, n in counts.items())
    outcome: Outcome
    if exit_code == 0:
        passed = counts.get("passed", 0) > 0 and counts.get("skipped", 0) == 0
        outcome = "green" if passed else "error"
    else:
        outcome = "red" if counts.get("failed", 0) > 0 else "error"
    return Verdict(outcome, summary or _last_line(text, exit_code), _playwright_failed(text))


def _judge_tsc(exit_code: int, text: str, diagnostic_in: str | None) -> Verdict:
    if exit_code == 0:
        return Verdict("green", "진단 없음")
    diagnostics = [(m.group(1), m.group(0)) for m in _TSC_DIAGNOSTIC.finditer(text)]
    summary = f"진단 {len(diagnostics)}" if diagnostics else _last_line(text, exit_code)
    target = diagnostic_in or ""
    hit = any(path == target or path.endswith(f"/{target}") for path, _ in diagnostics)
    return Verdict("red" if hit else "error", summary, tuple(line for _, line in diagnostics))


def _judge_exit(exit_code: int, text: str, red_exit: int | None) -> Verdict:
    outcome: Outcome = "green" if exit_code == 0 else "red" if exit_code == red_exit else "error"
    return Verdict(outcome, _last_line(text, exit_code))


@dataclass(frozen=True)
class Judging:
    """판정 하나와 그 판정만 쓰는 인자. `diagnostic_in` 은 tsc, `red_exit` 는 exit 판정만 쓰고, 그
    짝은 변이 파일을 읽을 때 본다. 인자가 변이(`diagnostic_in`)와 러너(`red_exit`)에 흩어져 있어
    `_judging_for` 한 곳에서 묶고, 측정의 단계들은 묶음 하나만 넘긴다(PR #240 claude-review)."""

    kind: JudgeName
    diagnostic_in: str | None = None
    red_exit: int | None = None


def judge(judging: Judging, result: CommandResult) -> Verdict:
    """명령의 결과를 초록, 빨강, 처리하지 않은 에러, 오류로 가른다. 색 코드는 벗기고 읽는다. 시간
    제한을 넘겨 끊은 결과는 끊기 전의 출력이 무엇이든 오류다."""
    if result.timed_out_after is not None:
        return Verdict("error", f"시간 제한 {result.timed_out_after}초를 넘겨 끊었다")
    text = result.plain
    match judging.kind:
        case "pytest":
            return _judge_pytest(result.exit_code, text)
        case "vitest":
            return _judge_vitest(result.exit_code, text)
        case "playwright":
            return _judge_playwright(result.exit_code, text)
        case "tsc":
            return _judge_tsc(result.exit_code, text, judging.diagnostic_in)
        case "exit":
            return _judge_exit(result.exit_code, text, judging.red_exit)


def _runners(spec: Spec) -> dict[str, RunnerSpec]:
    """내장 러너와 변이 파일의 러너 표."""
    return {**_BUILTIN, **spec.runner}


def _judging_for(command: RunnerSpec, mutation: Mutation | None = None) -> Judging:
    """러너의 판정과 그 판정이 쓰는 인자. 기준선은 변이가 없어 진단 자리도 없다."""
    diagnostic_in = mutation.diagnostic_in if mutation is not None else None
    return Judging(command.judge, diagnostic_in, command.red_exit)


def _verdict_only(markers: Sequence[str], kind: JudgeName) -> list[str]:
    """`kind` 판정의 러너가 어느 실패나 통과에나 찍는 낱말만으로 된 표지. 낱말이 하나도 없는
    표지(`== 1`)는 여기서 거르지 않는다."""
    words = _VERDICT_WORDS[kind]
    found: list[str] = []
    for marker in markers:
        parts = [part.casefold() for part in _WORD.findall(marker)]
        if parts and all(part in words for part in parts):
            found.append(marker)
    return found


def _verdict_note(owner: str, field: str, markers: Sequence[str], kind: JudgeName) -> str:
    listed = ", ".join(repr(marker) for marker in markers)
    return (
        f"{owner}: {field} 의 표지 {listed} 는 {kind} 러너가 어느 실패에나 찍는 판정 낱말뿐이다."
        " 고른 단언만 찍는 문구(시험 이름, 단언의 값)로 고른다"
    )


def _runner_problems(spec: Spec) -> list[str]:
    """변이 파일의 러너마다 이름과 판정의 짝. 파일을 보지 않는다."""
    problems = [
        f"러너 이름 {name} 는 내장이다. 다른 이름을 쓴다"
        for name in spec.runner
        if name in _BUILTIN
    ]
    for name, command in spec.runner.items():
        if command.judge == "exit" and command.red_exit is None:
            problems.append(
                f"러너 {name}: exit 판정은 red_exit(빨강으로 읽을 종료 코드)가 있어야 한다"
            )
        if command.judge != "exit" and command.red_exit is not None:
            problems.append(f"러너 {name}: red_exit 는 exit 판정만 쓴다(이 러너는 {command.judge})")
        if "" in command.baseline_output:
            problems.append(f"러너 {name}: baseline_output 에 빈 표지가 있다. 어느 출력에나 있다")
        weak = _verdict_only(command.baseline_output, command.judge)
        if weak:
            problems.append(_verdict_note(f"러너 {name}", "baseline_output", weak, command.judge))
    return problems


def _mutation_problems(spec: Spec) -> list[str]:
    """변이마다 러너와 판정의 짝. 파일을 보지 않는다."""
    problems: list[str] = []
    runners = _runners(spec)
    for m in spec.mutation:
        if m.runner not in runners:
            problems.append(f"{m.name}: 러너 {m.runner} 가 [runner.{m.runner}] 에 없다")
            continue
        kind = runners[m.runner].judge
        if kind == "tsc" and m.diagnostic_in is None:
            problems.append(f"{m.name}: tsc 판정은 diagnostic_in(빨강이 날 파일)이 있어야 한다")
        if kind != "tsc" and m.diagnostic_in is not None:
            problems.append(f"{m.name}: diagnostic_in 은 tsc 판정만 쓴다(이 러너는 {kind})")
        if "" in m.expect_output:
            problems.append(f"{m.name}: expect_output 에 빈 표지가 있다. 어느 출력에나 있다")
        weak = _verdict_only(m.expect_output, kind)
        if weak:
            problems.append(_verdict_note(m.name, "expect_output", weak, kind))
        if m.expect == "unhandled" and kind != "vitest":
            problems.append(f"{m.name}: expect unhandled 는 vitest 판정만 쓴다(이 러너는 {kind})")
    return problems


def load_spec(text: str) -> Spec:
    try:
        spec = Spec.model_validate(tomllib.loads(text))
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise SpecError(str(error)) from error
    names = [m.name for m in spec.mutation]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise SpecError(f"이름이 겹친다: {', '.join(repeated)}. 이름으로 골라 다시 돌린다")
    numeric = [name for name in names if _NUMBER.fullmatch(name)]
    if numeric:
        raise SpecError(f"이름이 숫자뿐이다: {', '.join(numeric)}. 번호와 가를 수 없다")
    problems = [*_runner_problems(spec), *_mutation_problems(spec)]
    if problems:
        raise SpecError("\n".join(problems))
    return spec


def read_spec(path: Path) -> Spec:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SpecError(f"{path} 를 읽지 못했다: {error}") from error
    return load_spec(text)


def select(spec: Spec, picks: Sequence[str]) -> Spec:
    """이름이나 번호(표에 적힌 차례, 1부터)로 고른다. 없으면 전부다. 고른 것은 표의 차례로 돌고 러너
    표는 그대로 둔다."""
    if not picks:
        return spec
    known = {m.name for m in spec.mutation}
    chosen: set[str] = set()
    unknown: list[str] = []
    outside: list[str] = []
    for pick in picks:
        if _NUMBER.fullmatch(pick):
            if 1 <= int(pick) <= len(spec.mutation):
                chosen.add(spec.mutation[int(pick) - 1].name)
            else:
                outside.append(pick)
        elif pick in known:
            chosen.add(pick)
        else:
            unknown.append(pick)
    problems = [f"변이 파일에 없는 이름: {', '.join(unknown)}"] if unknown else []
    if outside:
        problems.append(f"표 밖의 번호 {', '.join(outside)} (이 표는 1~{len(spec.mutation)})")
    if problems:
        raise SpecError("\n".join(problems))
    return Spec(runner=spec.runner, mutation=[m for m in spec.mutation if m.name in chosen])


def _numbers(spec: Spec) -> dict[str, int]:
    """이름마다 표에 적힌 차례(1부터). 고를 때와 출력의 줄 머리가 쓴다."""
    return {m.name: at for at, m in enumerate(spec.mutation, 1)}


def _labelled(names: Sequence[str], numbers: Mapping[str, int]) -> str:
    return ", ".join(f"{numbers[name]}. {name}" for name in names)


def changed_names(old: Spec, new: Spec) -> list[str]:
    """`new` 의 변이 가운데 `old` 에 없거나 달라진 것의 이름, 표의 차례대로. 변이의 무엇이든(원문,
    기대, 표지, 시험, 시간 제한) 다르거나 그 변이가 쓰는 러너의 명령·자리·판정·빨강 코드·기준선
    표지가 다르면 달라진 것이다."""
    before = {m.name: m for m in old.mutation}
    old_runners, new_runners = _runners(old), _runners(new)
    return [
        m.name
        for m in new.mutation
        if before.get(m.name) != m or old_runners.get(m.runner) != new_runners.get(m.runner)
    ]


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SpecError(f"git {args[0]} 를 돌리지 못했다: {error}") from error


def changed_since(path: Path, spec: Spec, ref: str) -> list[str]:
    """`ref` 커밋에 있던 같은 표와 견주어 새로 더했거나 달라진 변이의 이름(`changed_names`). 그
    커밋에 표가 없으면 모두다. 표가 git 저장소 밖에 있거나 그 저장소에서 `ref` 를 커밋으로 풀지
    못하면 `SpecError`."""
    where = path.resolve().parent
    inside = _git(where, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise SpecError(f"--since {ref}: 표가 든 {where} 가 git 저장소 안이 아니다")
    if _git(where, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        raise SpecError(f"--since {ref}: {where} 의 저장소에서 커밋으로 풀지 못했다")
    shown = _git(where, "show", f"{ref}:./{path.name}")
    if shown.returncode != 0:
        return [m.name for m in spec.mutation]
    try:
        old = load_spec(shown.stdout)
    except SpecError as error:
        raise SpecError(
            f"--since {ref}: 그 커밋의 표를 지금의 도구로 읽지 못했다."
            f" 번호나 이름으로 고른다\n{error}"
        ) from error
    return changed_names(old, spec)


def _inside(root: Path, relative: str) -> Path | None:
    """저장소 안이면 그 경로, 밖이면 None."""
    path = (root / relative).resolve()
    return path if path.is_relative_to(root.resolve()) else None


type Reader = Callable[[Path], bytes]  # 저장소 안의 경로 → 그 판의 바이트. 없으면 OSError


def _read_disk(path: Path) -> bytes:
    return path.read_bytes()


def _mutated(
    root: Path, mutation: Mutation, read: Reader = _read_disk
) -> dict[Path, tuple[bytes, bytes]]:
    """파일마다 (원래 바이트, 변이된 바이트). 편집은 적힌 차례로 앞 편집의 결과 위에 들어간다.
    바이트는 `read` 가 읽는다. 기본은 디스크이고, 색인 확인은 커밋과 색인의 판을 읽는다."""
    files: dict[Path, tuple[bytes, bytes]] = {}
    for edit in mutation.edit:
        path = _inside(root, edit.file)
        if path is None:
            raise SpecError(f"{mutation.name}: {edit.file} 는 저장소 밖이다")
        if path not in files:
            try:
                data = read(path)
            except OSError as error:
                raise SpecError(f"{mutation.name}: {edit.file} 를 읽지 못했다: {error}") from error
            files[path] = (data, data)
        original, current = files[path]
        old = edit.old.encode("utf-8")
        count = current.count(old)
        if count != 1:
            hint = (_eol_hint(current, old) or _escape_hint(current, old)) if count == 0 else ""
            raise SpecError(
                f"{mutation.name}: {edit.file} 에 원문이 {count}번 있다. 정확히 한 번이어야 한다"
                f" (줄 끝과 들여쓰기까지 바이트로 맞춘다){hint}"
            )
        files[path] = (original, current.replace(old, edit.new.encode("utf-8")))
    return files


def _eol_hint(data: bytes, old: bytes) -> str:
    """0번인 원문이 줄 끝을 맞춘 바이트에서 찾히면 덧붙일 까닭, 아니면 빈 문자열. 파일의 줄 끝과
    줄 끝을 맞추면 몇 번인지를 함께 적어, 줄 끝이 섞인 파일이나 두 번 찾히는 원문에서도 참이다."""

    def lf(raw: bytes) -> bytes:
        return raw.replace(b"\r\n", b"\n")

    found = lf(data).count(lf(old))
    if not found:
        return ""
    crlf = data.count(b"\r\n")
    bare = data.count(b"\n") - crlf
    ending = "CRLF 와 LF 가 섞였다" if crlf and bare else "CRLF 뿐이다" if crlf else "LF 뿐이다"
    return f". 줄 끝이 다르다(파일은 {ending}, 줄 끝을 맞추면 {found}번)"


def _escape_hint(data: bytes, old: bytes) -> str:
    """0번인 원문이 글자 그대로의 `\\n`·`\\t` 를 들고, 그것을 푼 바이트에서 찾히면 덧붙일 까닭.
    아니면 빈 문자열. 작은따옴표 문자열에 적은 `\\n` 이 풀리지 않아 원문이 0번이었다(대기열
    317)."""
    if b"\\n" not in old and b"\\t" not in old:
        return ""
    found = data.count(old.replace(b"\\n", b"\n").replace(b"\\t", b"\t"))
    if not found:
        return ""
    return (
        ". 원문에 글자 그대로의 \\n·\\t 가 있다. TOML 의 작은따옴표 문자열은 이스케이프를 풀지"
        f" 않는다(풀면 {found}번). 줄을 바꿀 자리는 여러 줄 리터럴('''…''')로 적는다"
    )


def _file_problems(root: Path, spec: Spec, read: Reader = _read_disk) -> list[str]:
    """고른 변이의 원문(`read` 가 읽은 바이트), 그 변이들이 쓰는 러너의 자리, 되돌릴 파일. 자리와
    되돌릴 파일은 디스크에서 본다. 아무 파일도 쓰지 않는다."""
    problems: list[str] = []
    for name in sorted({m.runner for m in spec.mutation} & spec.runner.keys()):
        where = _inside(root, spec.runner[name].cwd)
        if where is None or not where.is_dir():
            problems.append(
                f"러너 {name}: 자리 {spec.runner[name].cwd} 가 저장소 안의 디렉터리가 아니다"
            )
    for mutation in spec.mutation:
        try:
            _mutated(root, mutation, read)
        except SpecError as error:
            problems.append(str(error))
        for relative in mutation.restore:
            path = _inside(root, relative)
            if path is None or not path.is_file():
                problems.append(f"{mutation.name}: 되돌릴 파일 {relative} 가 저장소 안에 없다")
    return problems


# 표지를 시험 원문과 맞대는 기대. 초록의 출력은 실패 머리와 코드 조각을 찍지 않는다
_ECHO_EXPECTS = frozenset({"red", "unhandled"})


def _test_args(runners: Mapping[str, RunnerSpec], mutation: Mutation) -> list[str]:
    """변이의 `tests` 인자 가운데 옵션이 아닌 것을 러너의 자리 기준으로 이은 경로. `::` 뒤의 시험
    이름은 뗀다. 파일인지(`-k` 의 식, 폴더)는 보지 않는다."""
    cwd = Path(runners[mutation.runner].cwd)
    return [
        (cwd / arg.split("::", 1)[0]).as_posix()
        for arg in mutation.tests
        if not arg.startswith("-")
    ]


def _echo_problems(root: Path, spec: Spec, read: Reader = _read_disk) -> list[str]:
    """빨강이나 처리하지 않은 에러를 기대한 변이의 표지 가운데 그 시험 파일의 원문(`read` 가 읽은
    바이트)에 글자 그대로 있는 것(대기열 417). 읽지 못하는 인자(폴더, `-k` 의 식, 없는 파일)는
    넘는다."""
    runners = _runners(spec)
    base = root.resolve()
    problems: list[str] = []
    for mutation in spec.mutation:
        if (
            mutation.expect not in _ECHO_EXPECTS
            or not mutation.expect_output
            or mutation.runner not in runners
        ):
            continue
        for candidate in dict.fromkeys(_test_args(runners, mutation)):
            path = _inside(root, candidate)
            if path is None:
                continue
            try:
                text = read(path).decode("utf-8", "replace")
            except OSError:
                continue
            echoed = [marker for marker in mutation.expect_output if marker in text]
            if echoed:
                problems.append(
                    f"{mutation.name}: expect_output 의 표지 {', '.join(map(repr, echoed))} 가"
                    f" {path.relative_to(base).as_posix()} 의 시험 원문에 글자 그대로 있다."
                    " 실패 출력의 머리(시험 이름)나 실패 줄 둘레의 코드 조각에 늘 실려, 고른"
                    " 단언이 빨개졌다는 표지가 되지 못한다(대기열 417). 변이가 낸 받은 값처럼"
                    " 그 단언이 빨개질 때만 찍히는 문구로 고른다"
                )
    return problems


# pytest 가 단언을 풀어 쓰는 줄의 머리(`where 1 = run()`, `assert 0 == 1`, `E       assert 4 == 1`,
# `+  where False = f(1)`). 줄 머리만 본다
_ASSERT_REWRITE = re.compile(r"\s*(?:E\s+)?[+\s]*(?:where\s.+=.+\(|assert\s.+==)")

_ASSERT_REWRITE_NOTE = (
    "pytest 가 단언을 풀어 쓴 줄이다. 시험이 다른 까닭으로 빨개져도 그 호출과 값이 실려, 고른"
    " 단언이 빨개졌다는 표지가 되지 못한다(대기열 517). 단언에 싣는 메시지나, 변이를 손으로 넣어"
    " 본 실패 출력의 원인 문구로 고른다"
)

# 줄 머리가 호출 한 토막(`matches(server='x')`, `Rule(server=None`)인 표지. 풀이 줄 머리(`+  where
# False = `)를 떼고 그 뒤의 부분 문자열만 고른 것이다. `이름(` 뒤가 인자처럼 생긴 것(`)`, 따옴표나
# 괄호, 숫자나 식별자 뒤의 `,` `)`, 식별자 뒤의 `=` `,` `)` `(`)만 받아 `zeta(7회차)` 같은 목록
# 출력은 거른다
_CALL_FRAGMENT = re.compile(
    r"\s*(?:E\s+)?[+\s]*[A-Za-z_][\w.]*\("
    r"(?:\s*\)|\s*['\"\[{(]|\s*-?\d+\s*[,)]|\s*[A-Za-z_][\w.]*\s*[=,)(])"
)

_CALL_FRAGMENT_NOTE = (
    "호출 한 토막(`이름(…)` 꼴)이다. `+  where False = 이름(…)` 같은 pytest 의 단언 풀이 줄에 든"
    " 부분 문자열이면 시험이 다른 까닭으로 빨개져도 그 호출과 값이 실려, 고른 단언이 빨개졌다는"
    " 표지가 되지 못한다(대기열 579). 변이를 손으로 넣어 본 실패 출력에서 인자 줄(`rule = …`)이나"
    " 단언에 싣는 메시지를 고른다"
)


def _quality_problems(spec: Spec) -> list[str]:
    """빨강을 기대한 변이의 표지 품질. 표지가 없거나(대기열 350), pytest 판정인데 표지가 단언을 풀어
    쓴 줄이거나(대기열 517) 줄 머리가 호출 한 토막이다(대기열 579). 파일을 읽지 않는다. 옛 변이를
    소급하지 않으려고 고른 `--check` 와 `--staged` 의 새 변이에만 쓰고 변이를 돌리는 실행에는 걸지
    않는다(티켓 041)."""
    runners = _runners(spec)
    problems: list[str] = []
    for mutation in spec.mutation:
        if mutation.expect != "red" or mutation.runner not in runners:
            continue
        if not mutation.expect_output:
            problems.append(
                f"{mutation.name}: 빨강을 기대했는데 expect_output 이 없다. 다른 까닭으로 빨개져도"
                " 기대와 맞는다(대기열 350). 고른 단언이 빨개질 때만 찍히는 문구를 적는다"
            )
        if runners[mutation.runner].judge != "pytest":
            continue
        for marker in mutation.expect_output:
            if _ASSERT_REWRITE.match(marker):
                note = _ASSERT_REWRITE_NOTE
            elif _CALL_FRAGMENT.match(marker):
                note = _CALL_FRAGMENT_NOTE
            else:
                continue
            problems.append(f"{mutation.name}: expect_output 의 표지 {marker!r} 는 {note}")
    return problems


def _picked_problems(root: Path, spec: Spec) -> list[str]:
    """넘겨받은 표의 원문 확인과 표지의 메아리. 고른 `--check` 에는 고른 변이가, 변이를
    돌리는 실행에는 돌릴 변이(고르지 않은 전체 실행이면 표의 모두)가 든 표가 온다."""
    return _file_problems(root, spec) + _echo_problems(root, spec)


def _validate(root: Path, spec: Spec) -> None:
    """변이를 돌리기 전의 1단계. 원문 확인에 더해 표지의 메아리도 본다. 다시 돌리는 변이는 지금
    재는 것이라 옛 변이도 본다(대기열 502)."""
    problems = _picked_problems(root, spec)
    if problems:
        raise SpecError("\n".join(problems))


def _drop_bytecode(path: Path) -> None:
    """그 소스의 바이트코드 캐시를 지운다. CPython 의 것과 pytest assertion rewrite 의 것이다."""
    for cached in path.parent.glob(f"__pycache__/{path.stem}.*.pyc"):
        cached.unlink(missing_ok=True)


def _invoke(
    root: Path, command: RunnerSpec, tests: Sequence[str], timeout: int, runner: Runner
) -> CommandResult:
    return runner([*command.command, *tests], root / command.cwd, timeout)


class _WrittenMeanwhile(Exception):
    """변이가 든 동안 다른 쓰기가 들어와, 파일이 쓴 변이 바이트가 아니다."""


def _retrying[T](action: Callable[[], T], blocked: Callable[[OSError], None]) -> T:
    """`OSError` 로 막히면 그 오류를 `blocked` 에 알리고 `RESTORE_WAITS` 의 초만큼 기다려 다시
    부른다. 끝내 막히면 마지막 `OSError` 를 낸다."""
    for wait in RESTORE_WAITS:
        try:
            return action()
        except OSError as error:
            blocked(error)
            time.sleep(wait)
    return action()


def _restore_file(
    path: Path, original: bytes, written: bytes | None, blocked: Callable[[OSError], None]
) -> None:
    """원래 바이트를 되쓴다. 쓴 변이 바이트(`written`)가 있는데 파일이 그것과 다르면 덮지 않고
    `_WrittenMeanwhile`. 읽기와 쓰기는 막히면 다시 시도한다(`_retrying`). 다른 쓰기는 처음 읽은
    바이트로 한 번만 본다. 쓰다 막힌 뒤의 파일은 이 쓰기가 남긴 앞부분이라, 다시 볼 때마다 다른
    쓰기로 읽힌다."""
    if written is not None and _retrying(path.read_bytes, blocked) != written:
        raise _WrittenMeanwhile
    _retrying(lambda: path.write_bytes(original), blocked)
    _drop_bytecode(path)


def _restore(
    root: Path,
    name: str,
    held: dict[Path, bytes],
    written: dict[Path, bytes],
    out: Callable[[str], None],
) -> None:
    """쥔 파일을 모두 되쓰고, 남은 파일이 있으면 그 뒤에 `RestoreError`. 막혔다가 지난 파일은 처음
    막힌 까닭을 남긴다. 무엇이 그 틈에 파일을 쥐는지 다음에 잴 흔적이다(대기열 267). 그 줄은 모두
    되쓴 뒤에 낸다. 출력이 줄 버퍼라 닫힌 파이프의 쓰기 오류가 그 자리에서 나, 되쓰는 도중에 내면
    남은 파일을 되쓰지 못한다(PR 직전 버그 리뷰). 되쓰는 동안 끊겨도(Ctrl+C) 그 파일을 남은 파일로
    적고 나머지를 마저 되쓴다."""
    stuck: list[str] = []
    passed: list[str] = []
    for path, original in held.items():
        relative = path.relative_to(root.resolve()).as_posix()
        blocked: list[OSError] = []
        try:
            _restore_file(path, original, written.get(path), blocked.append)
        except _WrittenMeanwhile:
            stuck.append(f"{relative} (변이가 든 동안 다른 쓰기가 들어와 덮지 않았다)")
        except OSError as error:
            stuck.append(f"{relative} ({len(blocked) + 1}번 막혔다: {error})")
        except KeyboardInterrupt:
            stuck.append(f"{relative} (되쓰는 동안 끊겼다)")
        else:
            if blocked:
                passed.append(
                    f"{relative} — {len(blocked)}번 막혔다가 지났다. 처음 막힌 까닭 {blocked[0]}"
                )
    if stuck:
        later = f". 막혔다가 지난 파일: {', '.join(passed)}" if passed else ""
        raise RestoreError(f"{name}: {', '.join(stuck)}{later}")
    for line in passed:
        out(f"되돌리기: {line}")


def _run_mutated(
    root: Path, command: RunnerSpec, mutation: Mutation, runner: Runner, out: Callable[[str], None]
) -> list[CommandResult]:
    """변이를 넣고 반복마다 돌린 결과. 되돌리기를 다시 시도했으면 그 줄을 `out` 에 낸다."""
    files = _mutated(root, mutation)
    rewritable = [(root / relative).resolve() for relative in mutation.restore]
    held = {path: original for path, (original, _) in files.items()}
    for path in rewritable:
        held.setdefault(path, path.read_bytes())
    written: dict[Path, bytes] = {}  # 쓰기가 끝난 변이 바이트. 되돌릴 파일은 넣지 않는다
    try:
        for path, (_, mutated) in files.items():
            path.write_bytes(mutated)
            _drop_bytecode(path)
            if path not in rewritable:
                written[path] = mutated
        results: list[CommandResult] = []
        tests = mutation.tests
        if mutation.expect == "red" and mutation.runner in _BUILTIN:
            tests = [*tests, "-x"]  # 빨강은 실패 하나로 정해진다(독스트링의 하는 일 3)
        for _ in range(mutation.repeat):
            result = _invoke(root, command, tests, mutation.timeout, runner)
            results.append(result)
            if result.timed_out_after is not None:
                break  # 끊긴 판정은 이미 기대와 어긋나, 남은 반복은 변이를 든 채 시간만 쓴다
        return results
    finally:
        _restore(root, mutation.name, held, written, out)


def _missing(result: CommandResult, markers: Sequence[str]) -> list[str]:
    """색 코드를 벗긴 출력에 없는 표지."""
    text = result.plain
    return [marker for marker in markers if marker not in text]


@dataclass(frozen=True)
class _Run:
    """명령 한 번의 결과, 그 판정, 출력에 없는 표지."""

    result: CommandResult
    verdict: Verdict
    missing: tuple[str, ...]


def _run_of(result: CommandResult, judging: Judging, markers: Sequence[str]) -> _Run:
    return _Run(result, judge(judging, result), tuple(_missing(result, markers)))


def _marker_note(missing: Sequence[str]) -> str:
    return f"표지 없음: {', '.join(missing)}"


_TAIL_LINES = 10
_HEAD_LINES = 20
# 실패 머리 줄: `AssertionError: …`·`TypeError: …`·`Error: …`, `Expected`·`Received`, diff 의
# `-`·`+` 줄. `Errors  1 error` 같은 요약 줄은 `Error` 바로 뒤가 낱말이라 맞지 않는다
_FAILURE_HEAD = re.compile(r"(\w*Error\b|Expected\b|Received\b|[-+](\s|$))")


def _failure_heads(lines: Sequence[str]) -> list[str]:
    """끝 10줄 밖에서 고른 실패 머리 줄, 앞에서부터 스무 줄까지. vitest 의 끝 10줄은 마지막 실패
    블록의 코드 조각이라 고른 단언의 머리와 `Received:` 줄이 거기 없다(대기열 455)."""
    outside = lines[:-_TAIL_LINES]
    heads = [line for line in outside if _FAILURE_HEAD.match(line.lstrip())]
    return heads[:_HEAD_LINES]


def _details(runs: Sequence[_Run], out: Callable[[str], None]) -> None:
    """빨간 테스트의 이름, 그리고 빨강도 초록도 아니거나 표지가 없으면 출력의 끝과 그 앞의 실패
    머리 줄."""
    for name in dict.fromkeys(name for run in runs for name in run.verdict.failed):
        out(f"   {name}")
    for run in runs:
        if run.missing:
            out(f"   {_marker_note(run.missing)}")
        if run.verdict.outcome in ("error", "unhandled") or run.missing:
            lines = run.result.plain.splitlines()
            for line in (*_failure_heads(lines), *lines[-_TAIL_LINES:]):
                out(f"   | {line}")


def _baseline_runs(
    root: Path, spec: Spec, runners: Mapping[str, RunnerSpec], runner: Runner
) -> Iterator[tuple[str, _Run]]:
    """러너와 인자의 짝마다 변이 없이 한 번씩 돌린 결과(기준선)와 그 짝의 이름. 짝 하나를 돌릴
    때마다 내놓아 부르는 쪽이 그 줄을 바로 낸다."""
    # 기준선은 러너와 인자의 짝마다 한 번이고, 그 짝을 쓰는 변이 가운데 가장 긴 제한을 받는다
    baselines: dict[tuple[str, tuple[str, ...]], int] = {}
    for m in spec.mutation:
        key = (m.runner, tuple(m.tests))
        baselines[key] = max(baselines.get(key, 0), m.timeout)
    for (name, tests), timeout in baselines.items():
        command = runners[name]
        result = _invoke(root, command, tests, timeout, runner)
        yield (
            " ".join((name, *tests)),
            _run_of(result, _judging_for(command), command.baseline_output),
        )


def _baseline_ok(run: _Run) -> bool:
    """기준선이 초록이고 표지가 모두 있다."""
    return run.verdict.outcome == "green" and not run.missing


def _report_baseline(label: str, run: _Run, out: Callable[[str], None]) -> None:
    absent = f" — {_marker_note(run.missing)}" if run.missing else ""
    out(f"기준선 {label}: {_LABELS[run.verdict.outcome]} — {run.verdict.summary}{absent}")
    if not _baseline_ok(run):
        _details([run], out)


def _mutation_runs(
    root: Path, mutation: Mutation, command: RunnerSpec, runner: Runner, out: Callable[[str], None]
) -> list[_Run]:
    """변이 하나를 넣어 돌린 반복마다의 결과."""
    judging = _judging_for(command, mutation)
    return [
        _run_of(result, judging, mutation.expect_output)
        for result in _run_mutated(root, command, mutation, runner, out)
    ]


def _matched(mutation: Mutation, runs: Sequence[_Run]) -> bool:
    """매 반복이 기대와 같고 표지가 모두 있다."""
    return all(run.verdict.outcome == mutation.expect and not run.missing for run in runs)


def _report_mutation(
    number: int,
    mutation: Mutation,
    runs: Sequence[_Run],
    *,
    matched: bool,
    out: Callable[[str], None],
) -> None:
    outcomes = ", ".join(_LABELS[run.verdict.outcome] for run in runs)
    head = "==" if matched else "!! 어긋남 —"
    out(
        f"{head} {number}. {mutation.name}: 기대 {_LABELS[mutation.expect]},"
        f" 결과 {outcomes} — {runs[-1].verdict.summary}"
    )
    _details(runs, out)


def check(spec: Spec, *, root: Path, out: Callable[[str], None], read: Reader = _read_disk) -> int:
    """원문만 본다. 명령을 돌리지 않는다. 모두 맞으면 0, 하나라도 틀리면 틀린 것을 모두 알리고 2."""
    return _report_check(spec, _file_problems(root, spec, read), out)


def check_picked(spec: Spec, *, root: Path, out: Callable[[str], None]) -> int:
    """이름·번호·`--since` 로 고른 변이의 원문 확인. `check` 에 더해 표지가 시험 원문에 글자
    그대로 있는지, 빨강을 기대했는데 표지가 없거나 단언 풀이 줄이거나 호출 한 토막인지도 본다(옛
    변이는 소급하지 않아 고른 변이에만 쓴다)."""
    return _report_check(spec, _picked_problems(root, spec) + _quality_problems(spec), out)


def _report_check(spec: Spec, problems: list[str], out: Callable[[str], None]) -> int:
    for problem in problems:
        out(f"!! {problem}")
    if problems:
        out(f"원문 확인: 변이 {len(spec.mutation)} 중 문제 {len(problems)}")
        return 2
    out(f"원문 확인: 변이 {len(spec.mutation)} 모두 원문이 한 번씩 있다")
    return 0


def measure(
    spec: Spec,
    *,
    root: Path,
    runner: Runner,
    out: Callable[[str], None],
    numbers: Mapping[str, int] | None = None,
) -> int:
    """기준선을 재고 변이를 하나씩 넣어 돌린다. 모두 기대대로면 0, 아니면 1. `numbers` 는 줄 머리와
    `다시 돌릴 번호` 에 다는 표의 번호이고, 없으면 `spec` 안의 차례다. 그래서 `select` 로 좁힌
    `spec` 을 넘기는 쪽은 원본 표의 번호(`_numbers(원본)`)를 함께 넘긴다. 넘기지 않으면 번호가
    원본과 어긋나 다시 돌릴 번호가 다른 변이를 가리킨다(`main` 이 그렇게 넘긴다)."""
    _validate(root, spec)
    if numbers is None:
        numbers = _numbers(spec)
    runners = _runners(spec)
    baselines: list[_Run] = []
    for label, run in _baseline_runs(root, spec, runners, runner):
        _report_baseline(label, run, out)
        baselines.append(run)
    if not all(_baseline_ok(run) for run in baselines):
        out("기준선이 초록이 아니라 변이를 넣지 않았다. 빨간 기준선 위의 빨강은 재는 것이 없다")
        return 1

    mismatched: list[str] = []
    for mutation in spec.mutation:
        runs = _mutation_runs(root, mutation, runners[mutation.runner], runner, out)
        matched = _matched(mutation, runs)
        _report_mutation(numbers[mutation.name], mutation, runs, matched=matched, out=out)
        if not matched:
            mismatched.append(mutation.name)

    if mismatched:
        labels = _labelled(mismatched, numbers)
        out(f"변이 {len(spec.mutation)} 중 어긋남 {len(mismatched)}: {labels}")
        out(f"다시 돌릴 번호: {' '.join(str(numbers[name]) for name in mismatched)}")
        return 1
    out(f"변이 {len(spec.mutation)} 모두 기대대로")
    return 0


def _kill_tree(process: subprocess.Popen[str]) -> None:
    """자식과 그 자식이 띄운 프로세스를 끝낸다. 윈도우는 `taskkill /T` 가 부모를 따라 찾고, POSIX 는
    자식이 이끄는 프로세스 그룹을 끝낸다(못 보는 것은 모듈 독스트링). `taskkill` 을 띄우지 못했거나
    시간을 넘겼어도, 그룹을 끝내지 못했어도 자식은 끝낸다."""
    if sys.platform == "win32":
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=_KILL_SECONDS,
            )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    process.kill()


def _drain(process: subprocess.Popen[str]) -> str:
    """끊은 뒤 남은 출력. 끝내지 못한 프로세스가 출력 파이프를 쥐고 있으면 `_DRAIN_SECONDS` 뒤에
    그만 읽는다."""
    try:
        stdout, stderr = process.communicate(timeout=_DRAIN_SECONDS)
    except subprocess.TimeoutExpired:
        return (
            f"(출력 파이프가 {_DRAIN_SECONDS}초 안에 닫히지 않아 그만 읽었다."
            " 끝내지 못한 프로세스가 남았을 수 있다)"
        )
    return stdout + stderr


def run_command(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
    """셸을 거치지 않는다. 윈도우의 `pnpm.CMD` 처럼 PATHEXT 로 찾는 이름은 `shutil.which` 가 풀고,
    그런 배치 파일은 cmd.exe 가 돌린다(독스트링의 못 보는 것). 시간 제한을 넘기거나 기다리는 동안
    예외(`KeyboardInterrupt` 등)가 올라오면 자식이 띄운 프로세스까지 끝낸다(`_kill_tree`)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
    # `with` 로 열지 않는다. 그만 읽은 뒤 `with` 를 빠져나오면(파이프를 닫고 자식을 기다린다) 이
    # 윈도우 에서 남은 손자가 끝날 때까지 멈췄다(`test_못_보는_것_고아가_…`). 다 읽은 파이프는
    # `communicate` 가 닫는다
    process = subprocess.Popen(
        [shutil.which(argv[0]) or argv[0], *argv[1:]],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,  # POSIX 에서 자식이 제 프로세스 그룹을 이끈다. 윈도우는 무시한다
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        output = _drain(process)
        code = process.wait()  # 시간 제한 없음: _kill_tree 로 끝낸 자식을 거둔다
        return CommandResult(code, output, timed_out_after=timeout)
    except BaseException:
        _kill_tree(process)
        raise
    return CommandResult(process.returncode, stdout + stderr)


def _check_files(paths: Sequence[str], *, root: Path, out: Callable[[str], None]) -> int:
    """변이 파일 여럿의 원문을 본다. 줄마다 앞에 그 파일의 경로를 붙이고, 읽지 못한 파일이 있어도
    나머지를 본다. 모두 맞으면 0, 하나라도 틀리면 2."""
    code = 0
    for path in paths:
        lines: list[str] = []
        try:
            code = max(code, check(read_spec(Path(path)), root=root, out=lines.append))
        except SpecError as error:
            lines.append(f"!! 변이 파일 오류: {error}")
            code = 2
        # 변이 파일 오류는 문제를 줄바꿈으로 잇는다. 줄마다 붙여야 둘째 줄의 출처가 보인다
        for line in "\n".join(lines).splitlines():
            out(f"{path}: {line}")
    return code


_TABLES = "*_mutations.toml"  # 색인 확인이 보는 변이 표. git 의 경로 패턴이라 `*` 가 `/` 도 맞춘다
_INDEX = ""  # 색인의 판 이름. 블롭 이름이 `:<경로>` 가 된다
_BROKEN_HERE = "부모 판에서 맞던 원문을 이 커밋이 깼다"
# `git cat-file --batch` 의 머리 줄. 없는 것은 `<이름> missing` 따위라 맞지 않는다
_BATCH_HEAD = re.compile(rb"[0-9a-f]{40,64} ([a-z]+) ([0-9]+)")


def _git_out(root: Path, *args: str) -> str:
    done = _git(root, *args)
    if done.returncode != 0:
        raise SpecError(f"git {args[0]} (종료 {done.returncode}): {done.stderr.strip()}")
    return done.stdout


def _names(output: str) -> list[str]:
    """`-z` 로 받은 경로들."""
    return [name for name in output.split("\0") if name]


def _blobs(root: Path, names: Sequence[str]) -> dict[str, bytes]:
    """`git cat-file --batch` 한 번으로 읽은 블롭. 이름은 `<커밋>:<경로>` 이고 색인은 `:<경로>` 다.
    그 판에 없거나 블롭이 아닌 것은 빠진다. 줄바꿈이 든 이름은 그 프로토콜로 물을 수 없어 빠진다."""
    asked = [name for name in dict.fromkeys(names) if "\n" not in name]
    if not asked:
        return {}
    try:
        done = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=root,
            input="".join(f"{name}\n" for name in asked).encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SpecError(f"git cat-file 를 돌리지 못했다: {error}") from error
    if done.returncode != 0:
        reason = done.stderr.decode("utf-8", "replace").strip()
        raise SpecError(f"git cat-file (종료 {done.returncode}): {reason}")
    found: dict[str, bytes] = {}
    data, at = done.stdout, 0
    for name in asked:
        end = data.find(b"\n", at)
        if end < 0:
            raise SpecError("git cat-file 의 출력이 물은 이름보다 짧다")
        head = _BATCH_HEAD.fullmatch(data, at, end)
        at = end + 1
        if head is None:
            continue
        size = int(head[2])
        if head[1] == b"blob":
            found[name] = data[at : at + size]
        at += size + 1
    return found


def _reader(
    root: Path, blobs: Mapping[str, bytes], rev: str, deleted: frozenset[str] | None = None
) -> Reader:
    """`rev` 판의 바이트를 `blobs` 에서 읽는다. `rev` 가 `_INDEX` 면 색인이다. `deleted` 를 주면 그
    판에 없고 `deleted` 에도 없는 파일(어느 판도 추적하지 않는 파일)은 작업 트리에서 읽는다."""
    base = root.resolve()
    where = "색인" if rev == _INDEX else f"커밋 {rev[:12]}"

    def read(path: Path) -> bytes:
        relative = path.relative_to(base).as_posix()
        data = blobs.get(f"{rev}:{relative}")
        if data is not None:
            return data
        if deleted is not None and relative not in deleted:
            return _read_disk(path)
        raise FileNotFoundError(errno.ENOENT, f"{where}에 없다", relative)

    return read


class _Relative:
    """편집의 `file` 을 저장소 기준 경로로 푼다. 밖이면 None. 같은 글자는 한 번만 푼다. 표 82개의
    변이마다 `resolve` 하면 색인 확인 한 번이 이 PC에서 약 7초였고, 글자마다 한 번 풀면 약 2초였다
    (2026-10-19, 프로세스 안에서 손으로 쟀다)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._base = root.resolve()
        self._known: dict[str, str | None] = {}

    def __call__(self, name: str) -> str | None:
        if name not in self._known:
            path = _inside(self._root, name)
            self._known[name] = None if path is None else path.relative_to(self._base).as_posix()
        return self._known[name]

    def files(self, mutation: Mutation) -> frozenset[str] | None:
        """변이가 고치는 파일. 저장소 밖을 가리키는 편집이 있으면 None."""
        found = [self(edit.file) for edit in mutation.edit]
        return None if None in found else frozenset(name for name in found if name is not None)


def _fits(root: Path, mutation: Mutation, read: Reader) -> bool:
    """그 판에서 원문이 차례대로 모두 정확히 한 번씩 있다."""
    try:
        _mutated(root, mutation, read)
    except SpecError:
        return False
    return True


def _changes(root: Path, parent: str) -> dict[str, str]:
    """색인이 `parent` 와 다른 경로와 그 상태 글자(`A`·`M`·`D`·`T`·`U`). 이름 바꿈은 지우고 더한
    것으로 읽는다(`--no-renames`). 그래서 상태 하나에 경로 하나다."""
    parts = _names(
        _git_out(root, "diff", "--cached", "--name-status", "--no-renames", "-z", parent)
    )
    return dict(zip(parts[1::2], parts[::2], strict=True))


def _parents(root: Path) -> list[str]:
    """이 커밋의 부모가 될 커밋. 첫 커밋이면 없고, 합치는 중이면 `MERGE_HEAD` 가 더해진다."""
    found: list[str] = []
    for ref in ("HEAD", "MERGE_HEAD"):
        done = _git(root, "rev-parse", "--quiet", "--verify", f"{ref}^{{commit}}")
        if done.returncode == 0:
            found.append(done.stdout.strip())
    return found


def _fresh(spec: Spec, olds: Sequence[bytes | None]) -> Spec | None:
    """커밋에 든 표에서 어느 부모 판의 같은 표와도 다른 변이(`changed_names`)만 남긴 표. 없으면
    None. 부모 판에 표가 없거나 지금의 도구로 읽지 못하면 그 부모와는 모두 다르다고 본다. 표지의
    메아리는 이 변이만 본다(옛 변이는 소급하지 않는다, 대기열 417)."""
    names = {m.name for m in spec.mutation}
    for old in olds:
        if old is None:
            continue
        try:
            names &= set(changed_names(load_spec(old.decode("utf-8")), spec))
        except (UnicodeDecodeError, SpecError):
            continue
    kept = [m for m in spec.mutation if m.name in names]
    return Spec(runner=spec.runner, mutation=kept) if kept else None


@dataclass(frozen=True)
class _Watched:
    """커밋에 들지 않은 표의 변이 가운데 이 커밋이 고친 파일을 가리키는 것. `same` 은 표가 색인과
    같은 부모다."""

    table: str
    mutation: Mutation
    same: tuple[str, ...]


class _Authored(NamedTuple):
    """이 커밋이 더했거나 고친 표. `fresh` 는 그 표에서 어느 부모 판의 같은 표와도 다른 변이다."""

    table: str
    spec: Spec
    fresh: Spec | None


def staged(*, root: Path, out: Callable[[str], None]) -> int:
    """커밋에 들 판(색인)의 변이 표 원문을 본다. 모두 맞으면 0, 하나라도 틀리면 2.

    표가 색인과 같은 부모가 하나도 없으면(이 커밋이 표를 더했거나 고쳤다) 모든 원문을 색인에서
    본다. 아니면 이 커밋이 고친 파일을 가리키는 변이만, 표가 같은 부모 모두에서 맞던 원문이 색인에서
    깨졌을 때 알린다. 부모에서도 맞지 않던 원문은 썩어도 된다(대기열 73·92). 어느 판도 추적하지
    않는 파일은 작업 트리에서 읽는다."""
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise SpecError(f"{root} 가 git 저장소 안이 아니다")
    parents = _parents(root)
    status = {parent: _changes(root, parent) for parent in parents}
    changed = {parent: frozenset(found) for parent, found in status.items()}
    # 어느 부모에서 지워진 파일. 색인에 없는 파일 가운데 이것 밖의 것은 어느 판도 추적하지 않는다
    deleted = frozenset(
        path for found in status.values() for path, letter in found.items() if letter == "D"
    )
    tables = _names(_git_out(root, "ls-files", "-z", "--", _TABLES))
    texts = _blobs(root, [f"{rev}:{table}" for table in tables for rev in (_INDEX, *parents)])
    relative = _Relative(root)
    lines: list[str] = []
    problems = 0
    authored: list[_Authored] = []
    authored_count = 0
    watched: list[_Watched] = []
    for table in tables:
        same = tuple(parent for parent in parents if table not in changed[parent])
        text = texts.get(f":{table}")
        if text is None:
            continue  # 색인에 블롭이 없다(충돌이 풀리지 않은 표)
        if not same:
            authored_count += 1
        try:
            spec = load_spec(text.decode("utf-8"))
        except (UnicodeDecodeError, SpecError) as error:
            if not same:
                # 변이 파일 오류는 문제를 줄바꿈으로 잇는다. 줄마다 표의 경로를 붙인다
                lines += [f"{table}: !! 변이 파일 오류: {line}" for line in str(error).splitlines()]
                problems += 1
            continue
        if not same:
            olds = [texts.get(f"{parent}:{table}") for parent in parents]
            authored.append(_Authored(table, spec, _fresh(spec, olds)))
            continue
        for mutation in spec.mutation:
            files = relative.files(mutation)
            if files is not None and all(files & changed[parent] for parent in same):
                watched.append(_Watched(table, mutation, same))
    wanted = [
        f":{name}"
        for item in authored
        for mutation in item.spec.mutation
        for name in relative.files(mutation) or ()
    ]
    wanted += [
        f":{name}"
        for item in authored
        if item.fresh is not None
        for mutation in item.fresh.mutation
        for arg in _test_args(_runners(item.fresh), mutation)
        if (name := relative(arg)) is not None
    ]
    wanted += [
        f"{rev}:{name}"
        for item in watched
        for name in relative.files(item.mutation) or ()
        for rev in (_INDEX, *item.same)
    ]
    blobs = _blobs(root, wanted)
    index = _reader(root, blobs, _INDEX, deleted)
    for table, spec, fresh in authored:
        found = _file_problems(root, spec, index)
        if fresh is not None:
            found += _echo_problems(root, fresh, index) + _quality_problems(fresh)
        lines += [f"{table}: !! {problem}" for problem in found]
        problems += len(found)
    for item in watched:
        if not all(_fits(root, item.mutation, _reader(root, blobs, rev)) for rev in item.same):
            continue  # 부모 판에서도 맞지 않던 원문이다
        try:
            _mutated(root, item.mutation, index)
        except SpecError as error:
            lines.append(f"{item.table}: !! {error} — {_BROKEN_HERE}")
            problems += 1
    for line in lines:
        out(line)
    out(
        f"색인 확인: 커밋에 든 표 {authored_count}, 고친 파일을 가리키는 다른 표의 변이"
        f" {len(watched)}, 문제 {problems}"
    )
    return 2 if problems else 0


class _UsageError(Exception):
    """인자를 잘못 줬다. 아무 파일도 읽기 전에 난다."""


@dataclass(frozen=True)
class _Args:
    """가른 인자. `tables` 의 첫째가 돌리거나 볼 변이 파일이고, 여럿은 `--check` 에서만 온다."""

    checking: bool
    tables: list[str]
    picks: list[str]  # 이름이나 번호
    since: str | None


def _parse(argv: Sequence[str]) -> _Args:
    """인자를 가른다. 틀렸으면 알릴 말을 든 `_UsageError`."""
    checking = "--check" in argv
    rest = [arg for arg in argv if arg != "--check"]
    since: str | None = None
    if "--since" in rest:
        at = rest.index("--since")
        value = rest[at + 1] if at + 1 < len(rest) else "--"
        if value.startswith("--") or rest.count("--since") > 1:
            raise _UsageError("--since 뒤에는 커밋(브랜치, 태그, 해시) 하나를 한 번만 준다")
        since = value
        rest = rest[:at] + rest[at + 2 :]
    flags = [arg for arg in rest if arg.startswith("--")]
    if flags:
        raise _UsageError(
            f"모르는 선택: {', '.join(flags)}. 아는 것은 --check, --staged, --since <커밋> 이다. "
            "변이 몇만 돌리려면 표 뒤에 그 번호(따옴표 없이 쳐 워크트리 가드를 지난다)나 "
            "이름을 준다"
        )
    if not rest:
        raise _UsageError(__doc__ or "")
    spec_path, *picks = rest
    more_tables = [pick for pick in picks if pick.endswith(".toml")]
    if more_tables and (not checking or len(more_tables) != len(picks) or since is not None):
        raise _UsageError(
            "변이 파일 여럿은 --check 로만 받고 이름·번호·--since 와 섞지 않는다."
            " 변이는 표 하나씩 돌린다"
        )
    if more_tables:
        return _Args(checking, [spec_path, *more_tables], [], since)
    return _Args(checking, [spec_path], picks, since)


def _since_picks(spec: Spec, args: _Args) -> list[str]:
    """`--since` 가 고른 이름. 주지 않았으면 없다. 이름·번호도 없이 고른 것이 없으면
    `SpecError` — 잘못 준 커밋이 0 으로 끝나면 잰 것처럼 보인다."""
    if args.since is None:
        return []
    fresh = changed_since(Path(args.tables[0]), spec, args.since)
    if not fresh and not args.picks:
        raise SpecError(
            f"--since {args.since}: 그 커밋 뒤로 바뀌거나 더한 변이가 없다. 돌릴 것이 없다"
        )
    return fresh


def _watched_paths(root: Path, spec: Spec) -> list[str]:
    """변이가 고치는 파일과 그 시험(러너의 자리 기준으로 푼 인자 가운데 있는 파일), 저장소 기준
    경로로. `::` 뒤의 시험 이름은 떼고, 옵션과 파일이 아닌 인자(`-k` 의 식)는 뺀다."""
    runners = _runners(spec)
    base = root.resolve()
    found: dict[str, None] = {}
    for mutation in spec.mutation:
        candidates = [edit.file for edit in mutation.edit] + _test_args(runners, mutation)
        for relative in candidates:
            path = _inside(root, relative)
            if path is not None and path.exists():
                found[path.relative_to(base).as_posix()] = None
    return list(found)


def _note_uncommitted(root: Path, spec: Spec, table: Path, out: Callable[[str], None]) -> None:
    """표 자체나 표가 가리키는 파일이나 그 시험에 커밋하지 않은 변경이 있으면 한 줄로 알린다.
    막지 않는다. git 저장소 밖이거나 git 을 부르지 못하면 말하지 않는다."""
    paths = _watched_paths(root, spec)
    with contextlib.suppress(ValueError):  # 표가 저장소 밖이면 표는 보지 않는다
        paths.insert(0, table.resolve().relative_to(root.resolve()).as_posix())
    if not paths:
        return
    try:
        done = _git(root, "status", "--porcelain", "-z", "--no-renames", "--", *paths)
    except SpecError:
        return
    if done.returncode != 0:
        return
    changed = [entry[3:] for entry in _names(done.stdout) if len(entry) > 3]
    if changed:
        out(
            "알림(막지 않는다): 고르지 않은 전체 실행인데 표나 표가 가리키는 파일이나 그 시험에"
            f" 커밋하지 않은 변경이 있다 — {', '.join(changed)}. 전체 실행은 셀프 리뷰와 PR 직전"
            " 리뷰를 반영해 커밋한 뒤에 한 번 돈다(독스트링의 언제 전체를 돌리나, 대기열 359)"
        )


def git_dir_of(root: Path) -> Path | None:
    """그 체크아웃의 git 디렉터리. `.git` 이 디렉터리면 그것, 워크트리의 `.git` 파일이면 `gitdir:`
    줄이 가리키는 곳이다. 읽지 못하면 None."""
    dot_git = root / ".git"
    try:
        if dot_git.is_dir():
            return dot_git
        line = dot_git.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    target = line.removeprefix("gitdir:").strip() if line.startswith("gitdir:") else ""
    return (root / target).resolve() if target else None


_QUERY_LIMITED = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
_INHERIT_HANDLE = False  # bInheritHandle. 자식 프로세스에 핸들을 물려주지 않는다
_STILL_ACTIVE = 259  # GetExitCodeProcess 가 아직 도는 프로세스에 내는 값


def process_started(pid: int) -> int | None:
    """그 pid 프로세스의 시작 시각. 윈도는 `GetProcessTimes` 의 만든 시각(100ns 단위), 리눅스는
    `/proc/<pid>/stat` 의 `starttime`(부팅 뒤 클록 틱)이다. 프로세스가 없거나 끝났거나 읽지
    못하거나 다른 OS 면 None. 윈도는 끝난 프로세스도 누가 핸들을 쥐고 있으면 열리고 만든 시각을
    내므로 끝났는지(`STILL_ACTIVE`)를 함께 본다. 편집 훅 `tools/hook_edit_during_mutate.py` 의 같은
    이름과 같은 값을 내야 한다(훅은 단독 실행 스크립트라 사본을 든다)."""
    if pid <= 0:
        return None
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        times = ctypes.POINTER(ctypes.c_ulonglong)
        kernel.GetProcessTimes.argtypes = [ctypes.c_void_p, times, times, times, times]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(_QUERY_LIMITED, _INHERIT_HANDLE, pid)
        if not handle:
            return None
        try:
            code = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            if code.value != _STILL_ACTIVE:
                return None
            created, ended, kernel_time, user_time = (ctypes.c_ulonglong() for _ in range(4))
            if not kernel.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(ended),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                return None
            return created.value
        finally:
            kernel.CloseHandle(handle)
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # 둘째 칸(실행 파일 이름)은 괄호에 싸여 공백을 들 수 있어 마지막 `)` 뒤에서 센다. 그 뒤 첫 칸이
    # 셋째 칸(state)이고 starttime 은 스물두째 칸이다(proc(5))
    fields = stat.rsplit(")", 1)[-1].split()
    return int(fields[19]) if len(fields) > 19 and fields[19].isdigit() else None


@contextlib.contextmanager
def _running_marker(root: Path, table: Path) -> Generator[None]:
    """도는 동안 그 체크아웃의 git 디렉터리에 pid 와 표와 이 프로세스의 시작 시각을 든 표지를
    두고, 끝나면(예외로 끝나도) 지운다. 편집 훅이 이것을 보고 변이가 든 체크아웃의 편집을
    알린다(대기열 358). 시작 시각은 남은 표지의 pid 를 다른 프로세스가 받았을 때 가른다(대기열
    449). 읽지 못하면 그 칸을 적지 않는다. git 디렉터리를 찾지 못했거나 쓰지 못하면 표지 없이
    돈다."""
    git_dir = git_dir_of(root)
    marker = git_dir / f"{MARKER_PREFIX}{os.getpid()}.json" if git_dir is not None else None
    if marker is not None:
        content: dict[str, str | int] = {"pid": os.getpid(), "table": str(table.resolve())}
        started: int | None = None
        # 프로세스를 볼 DLL 이나 함수를 싣지 못해도 표지 없이 돌지 않고 시작 시각만 뺀다
        with contextlib.suppress(OSError, AttributeError, ValueError, ctypes.ArgumentError):
            started = process_started(os.getpid())
        if started is not None:
            content["started"] = started
        try:
            marker.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        except OSError:
            marker = None
    try:
        yield
    finally:
        if marker is not None:
            with contextlib.suppress(OSError):
                marker.unlink(missing_ok=True)


def _run_table(args: _Args, *, root: Path, runner: Runner, out: Callable[[str], None]) -> int:
    """표 하나에서 고른 변이를 잰다. `--check` 면 원문만 본다. 고르지 않은 전체 실행이면 시작
    줄에서 커밋하지 않은 변경을 알린다."""
    table = Path(args.tables[0])
    spec = read_spec(table)
    fresh = _since_picks(spec, args)
    if args.since is not None:
        listed = f" — {_labelled(fresh, _numbers(spec))}" if fresh else ""
        out(f"--since {args.since}: 바뀌거나 더한 변이 {len(fresh)}{listed}")
    selected = select(spec, [*args.picks, *fresh])
    if args.checking:
        # 여기 오는 `--check` 는 이름·번호나 `--since` 로 고른 것이다(고르지 않으면 `_check_files`)
        return check_picked(selected, root=root, out=out)
    if not args.picks and args.since is None:
        _note_uncommitted(root, selected, table, out)
    with _running_marker(root, table):
        return measure(selected, root=root, runner=runner, out=out, numbers=_numbers(spec))


def main(
    argv: Sequence[str],
    *,
    root: Path = ROOT,
    runner: Runner = run_command,
    out: Callable[[str], None] = print,
) -> int:
    if "--staged" in argv:
        if len(argv) != 1:
            out("--staged 는 다른 인자와 섞지 않는다. 커밋에 들 판(색인)의 표를 모두 본다")
            return 2
        try:
            return staged(root=root, out=out)
        except SpecError as error:
            out(f"색인 확인을 하지 못했다: {error}")
            return 2
    try:
        args = _parse(argv)
    except _UsageError as error:
        out(str(error))
        return 2
    if args.checking and not args.picks and args.since is None:
        return _check_files(args.tables, root=root, out=out)
    try:
        return _run_table(args, root=root, runner=runner, out=out)
    except SpecError as error:
        out(f"변이 파일 오류(아무 파일도 쓰지 않았다): {error}")
        return 2
    except RestoreError as error:
        out(f"되돌리지 못했다. 남은 파일을 git diff 로 보고 변이만 걷어 낸다: {error}")
        if error.__context__ is not None:  # finally 에서 던져 가린, 그 전에 난 예외
            out(f"되돌리기 전에 난 예외: {error.__context__!r}")
        return 3
    except OSError as error:
        out(f"테스트를 돌리지 못했다(변이는 되돌렸다): {error}")
        return 3


if __name__ == "__main__":
    # pre-commit 훅 환경에 PYTHONUTF8 이 있다고 가정하지 않는다. 없으면 윈도우의 파이프는 cp949 다.
    # 파이프와 파일은 블록 버퍼라, 출력을 파일로 돌린 실행은 도는 동안 로그가 비고 끊으면 결과가
    # 사라졌다(대기열 259). 그래서 줄마다 내보낸다
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8", line_buffering=True)
    raise SystemExit(main(sys.argv[1:]))
