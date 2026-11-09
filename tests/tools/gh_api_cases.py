"""`gh api` 로 PR 을 여는 꼴과 아닌 꼴(대기열 408). `hook_pr_next_session` 과 `hook_handoff` 의
시험이 같은 표를 쓴다. 두 훅은 서로 import 하지 않아 판정을 따로 두므로(`.claude/rules/tools.md`),
같은 입력으로 둘을 함께 고정한다.

메서드는 `-X`·`--method` 가 정하고, 없으면 몸(`-f`·`-F`·`--input`)이 있을 때 POST 다(`gh api --help`
와 `.scratch/harness/probes/gh_api_method.py`).
"""

from __future__ import annotations

OPENS = (
    "gh api repos/o/r/pulls -f title=x -f head=b -f base=main",
    'gh api --method POST "repos/{owner}/{repo}/pulls" --input body.json',
    "gh api -X POST /repos/o/r/pulls -F draft=true",
    "gh api -XPOST repos/o/r/pulls",
    # 짧은 옵션의 `=` 는 값이 아니다(gh 2.98.0 의 `-X=POST` 요청 줄이 `POST` 였다, PR 직전 리뷰)
    "gh api -X=POST repos/o/r/pulls",
    "gh api --method=POST repos/o/r/pulls/",
    "gh api repos/o/r/pulls --input body.json",
    "cd /c/project/agent && gh api repos/o/r/pulls -f 'title=feat: x' > pr.json",
    'gh api repos/o/r/pulls --input - <<\'EOF\'\n{"title": "x"}\nEOF',
)

NOT_OPENS = (
    "gh api repos/o/r/pulls",
    "gh api repos/o/r/pulls -X GET -f state=open",
    "gh api repos/o/r/pulls -X=GET -f state=open",
    "gh api repos/o/r/pulls --input body.json --method GET",
    "gh api repos/o/r/pulls/12/comments -f body=x",
    "gh api repos/o/r/issues -f title=x",
    "gh api repos/o/r/pulls -f title=x --help",
    "echo 'gh api repos/o/r/pulls -f title=x'",
    'git commit -m "gh api repos/o/r/pulls -f title=x"',
)

# PowerShell 의 줄 이음(줄 끝 백틱). 백틱을 명령 치환으로 갈라 둘째 줄의 몸을 놓쳤다(PR 직전 리뷰).
POWERSHELL_OPENS = ("gh api repos/o/r/pulls `\n  -f title=x -f head=b -f base=main",)

# 못 보는 것(거짓 음성). GraphQL 의 `createPullRequest` 와 변수로 준 엔드포인트.
BLIND = (
    "gh api graphql -f query='mutation { createPullRequest(input: {}) { clientMutationId } }'",
    'gh api "$ENDPOINT" -f title=x',
)
