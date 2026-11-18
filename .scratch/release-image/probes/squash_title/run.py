"""release-image 명세의 프로브. squash 병합한 커밋의 제목이 PR 제목과 커밋 제목 가운데 무엇을
따랐는지 센다.

    uv run python .scratch/release-image/probes/squash_title/run.py [--repo 소유자/이름] [--pages N]

번호 도구는 main 에 쌓인 커밋의 제목에서 느낌표를 읽는다(ADR 0020 "올릴 때 운영자가 손댈 것의
기준"). 티켓 PR 은 squash 로 병합하므로 그 제목은 GitHub 가 정한다. 저장소 설정
`squash_merge_commit_title` 이 `COMMIT_OR_PR_TITLE` 이면 커밋이 하나인 PR 에서 PR 제목이 아니라 그
커밋의 제목을 쓴다고 ADR 0020 이 어림으로 적었다. 이 프로브는 그 설정의 지금 값을 읽고, 병합된 PR
가운데 커밋이 하나이면서 PR 제목과 커밋 제목이 다른 것을 골라 병합 커밋의 제목이 어느 쪽과 같은지
본다.

못 보는 것: 병합할 때 사람이나 도구가 제목을 직접 준 병합(`gh pr merge --subject`)은 설정과 무관하게
그 제목이 된다. 이 프로브는 그것을 가르지 못하고 "둘 다 아니다"로 센다.

필요한 것: 로그인한 `gh`. 읽기만 한다. 닫힌 PR 을 한 쪽에 100개씩 `--pages` 쪽(기본 2)까지 읽는다.
출력은 `run_out.txt` 로 커밋한다. 커밋한 출력은 저장소 루트에서 아래 두 명령을 차례로 친 것이다
(`P` 는 `.scratch/release-image/probes/squash_title`). agent-os 는 닫힌 PR 이 200개를 넘어 세
쪽(최근에 닫힌 PR 300개)을 읽었다.

    uv run python $P/run.py > $P/run_out.txt
    uv run python $P/run.py --repo njh6803/agent-os --pages 3 >> $P/run_out.txt
"""

import argparse
import json
import subprocess
import sys
from typing import Final

RELEASE_HEADS: Final = ("dev", "main")


def gh(*args: str) -> str:
    done = subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return done.stdout


def first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


def merged_pulls(repo: str, pages: int) -> list[tuple[int, str, str]]:
    """병합된 티켓 PR 의 (번호, 제목, 병합 커밋 해시). 출시 PR 과 되돌려 합치기 PR 은 뺀다."""
    found: list[tuple[int, str, str]] = []
    for page in range(1, pages + 1):
        rows = gh(
            "api",
            f"repos/{repo}/pulls?state=closed&per_page=100&page={page}",
            "--jq",
            ".[] | select(.merged_at != null)"
            " | [.number, .title, .merge_commit_sha, .head.ref] | @json",
        )
        for row in rows.splitlines():
            number, title, sha, head = json.loads(row)
            if str(head) not in RELEASE_HEADS:
                found.append((int(number), str(title), str(sha)))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--repo", default="njh6803/rag-engine")
    parser.add_argument("--pages", type=int, default=2)
    arguments = parser.parse_args()
    repo: str = arguments.repo
    pages: int = arguments.pages

    setting = gh("api", f"repos/{repo}", "--jq", ".squash_merge_commit_title").strip()
    print(f"[설정] {repo} 의 squash_merge_commit_title = {setting}", flush=True)

    pulls = merged_pulls(repo, pages)
    single = 0
    counts = {"커밋 제목을 따랐다": 0, "PR 제목을 따랐다": 0, "둘 다 아니다": 0}
    for number, title, sha in pulls:
        subjects = gh(
            "api",
            f"repos/{repo}/pulls/{number}/commits?per_page=2",
            "--jq",
            '.[] | .commit.message | split("\\n")[0]',
        ).splitlines()
        if len(subjects) != 1:
            continue
        single += 1
        commit_subject = subjects[0]
        if title == commit_subject:
            continue
        merged = first_line(gh("api", f"repos/{repo}/commits/{sha}", "--jq", ".commit.message"))
        # GitHub 는 squash 제목 끝에 ` (#번호)` 를 붙인다.
        subject = merged.removesuffix(f" (#{number})")
        if subject == commit_subject:
            verdict = "커밋 제목을 따랐다"
        elif subject == title:
            verdict = "PR 제목을 따랐다"
        else:
            verdict = "둘 다 아니다"
        counts[verdict] += 1
        print(
            f"[PR {number}] PR 제목 {title!r} / 커밋 제목 {commit_subject!r} / "
            f"병합 커밋 제목 {merged!r}: {verdict}",
            flush=True,
        )
    print(
        f"[셈] 병합된 티켓 PR {len(pulls)}개 가운데 커밋이 하나인 것 {single}개. "
        f"그 가운데 PR 제목과 커밋 제목이 다른 것의 병합 커밋 제목: {counts}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
