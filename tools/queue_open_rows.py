"""열린 대기열 항목을 회차, 날짜, 대상 파일로 세고, 닫힌 항목까지 낱말로 찾는다(찾기는 끝의 절).

`next-session` 결정표의 하네스 chore 배치 조건(`.scratch/retro-queue/`의 열린 항목 가운데 회차 5
이상인 것)과 retro 5단계의 만료(승인 줄의 가장 늦은 날짜로부터 14일)를 세는 자리다(ADR 0036). 같은
대상 파일이 셋 이상인 항목은 2026-10-19까지 둘째 계기였고, 지금은 chore 를 고른 뒤 함께 묶을
항목으로만 찍는다. 그 계기가 하네스 chore 뒤에 또 chore 를 불렀다. 세션마다 손이나 스크래치
스크립트로 세다가, 회차를 머리 글에 적은 옛 항목(17)이 빠졌고(대기열 167, 일지 2026-10-07-12) 근거로
든 파일까지 대상으로 세어 `.claude/rules/tools.md`가 대상 아홉으로 나왔다(일지 2026-10-16-30).

대기열은 항목마다 파일 하나인 폴더 `.scratch/retro-queue/`다(ADR 0045). 파일 모양은 폴더의
`README.md`가 원천이고, 이 도구가 읽는 모양은 이렇다. 첫 줄 `# <ID>: <머리>`(ID는 파일 이름의 stem),
이어서 `**상태:**`, `**어디로:**`, `**승인:**` 줄이 이 차례로 있고, 빈 줄 뒤에 본문이 온다. 옛
항목의 ID는 네 자리로 채운 번호(`0573`)이고 새 항목은 영어 제목(`coderabbit-inline-size`)이다.

판정.
- 항목: 폴더 바로 아래의 `*.md` 가운데 `README.md`가 아닌 파일. 첫 줄이
  `# <파일 이름의 stem>: <머리>` 꼴이 아니거나 라벨 줄 셋이 이 차례로 모두 있지 않거나(라벨 줄 앞의
  빈 줄은 건너뛴다) 상태 값이 `열림`·`닫힘`·`만료`로 시작하지 않으면 세지 않고 파일 경로와 빠진 줄을
  알리며 1로 끝난다. 상태 값은 시작만 보므로 `열림하지 않음`도 열림으로 읽는다. 조용히 빠지는
  항목이 이 도구가 막으려는 실패다.
- 닫힘: 상태 값이 `닫힘`이나 `만료`로 시작하면 닫힌 항목이다(`닫힘 (…)`의 괄호 안은 보지 않는다).
  부분 반영(141)은 `열림`이라 열린 항목이다.
- 회차: `<수>회차`를 승인 줄에서 찾고, 없으면 머리와 본문, 그다음 어디로 줄에서 찾는다. 한 곳에
  여럿이면 가장 큰 것이다. 회차는 오르기만 하는데 옛 글이 남을 수 있어서다. 만료한 옛 항목을 잇는 새
  항목은 승인 줄에 이어 센 회차를 적는다(`0435`가 4회차로 만료했고 이은 항목이 5회차를 적으면
  5회차로 센다).
- 대상과 인용: 어디로 줄의 코드 스팬 가운데 경로인 것(`/`가 들었거나 확장자가 붙은 파일 이름이고,
  공백·`{`·`<`·`$`가 없고 `-`·`/`로 시작하지 않는다. 옵션과 슬래시 명령을 뺀다)만 센다. 괄호 밖이면
  대상, 괄호 안이면 근거로 든 인용이다. 코드 스팬 안의 괄호는 깊이를 바꾸지 않는다. 같은 항목에서
  대상이면서 인용이면 대상으로만 센다.
- 사람 몫: 어디로 줄이 `사람 몫:`으로 시작하는 항목. 앞의 굵게 표시(`**`)는 벗기고 본다. 사람이 할
  일을 세션마다 다시 보며 회차가 쌓여 chore 계기가 됐다(238, 11회차). 그래서 회차 5 이상에도
  만료에도 넣지 않고 따로 찍는다.
- 만료: 사람 몫도 회차 5 이상도 아닌 열린 항목 가운데 승인 줄의 가장 늦은 날짜(승인 날짜와 일지
  파일명의 `YYYY-MM-DD`)가 기준일(`--today`, 기본 오늘)의 14일 전보다 이른 것. 회차 5 이상인 항목은
  chore 가 반영할 때까지 남긴다(chore 는 기능의 마지막 티켓 뒤에만 열려 14일을 넘기기 쉽다). 날짜가
  없는 항목은 따로 찍는다. 만료는 고쳐졌다는 판정이 아니라 목록에서 내리는 것이다. 닫는 일과 다시
  일어났을 때 잇는 일은 retro 5단계가 한다.
- 같은 대상 파일은 파일 대상만 묶는다. `/`로 끝나는 디렉터리와 `*`가 든 패턴은 여러 파일을 담는
  그릇이라 묶으면 늘 셋을 넘는다(`tools/`가 여덟 항목). 그것들은 따로 찍는다. 인용 경로도 항목
  번호와 함께 늘 찍어, 아래 못 보는 것의 두 방향을 출력에서 사람이 가른다.
- 식별자: 문자열이다. 숫자 ID(파일 이름 `0573`)는 출력에 앞의 0을 뗀 정수 모양(`573`)으로, 슬러그는
  그대로 찍는다. 정렬은 (-회차, 숫자 ID 오름차순이 먼저, 그다음 슬러그 오름차순)이다.
- 인용 풀기: `item_name`·`item_path`가 "대기열 573"과 "대기열 0573"을 같은 파일 `0573.md`로,
  슬러그를 그 이름의 파일로 푼다. 시험이 이 풀이를 고정한다. 아침 보고는 스크립트로 돌아 이
  모듈을 가져오지 못해 같은 규칙을 `morning_report.queue_key`에 따로 두고, 찾기는 파일 경로를
  그대로 찍어 이 함수를 부르지 않는다. 새 CLI 는 없다.

못 보는 것.
- 괄호 밖 본문의 인용은 대상으로 센다(286의 "`.claude/rules/tools.md`의 반박 시험을 거친다", 57의
  "…의 단독 실행 규약과 함께 본다"). 반대로 괄호 안의 대상은 인용으로 세어 대상 수에서 빠진다(141의
  "사용처(`tools/hook_pr_head_sync.py`, …)"). 둘 다 시험으로 고정했다.
- 고칠 파일이 아닌데 경로 모양인 것을 대상으로 센다. git이 만드는 `index.lock`(293), 훅이 지켜보는
  경로(227의 `docs/adr/`)가 그렇다. 부분 반영 항목(141)에서 이미 반영한 몫의 대상도 그대로 센다.
- 같은 파일을 다른 이름으로 적은 것(`operations.md`와 `docs/constitution/operations.md`, 디렉터리
  `tools/`와 그 아래 파일)은 다른 대상이다.
- 결정표의 둘째 조건인 "사용자가 순서를 올린 항목"은 항목에 표지가 없어 세지 않는다.
- 회차를 숫자 아닌 말("세 번째")로만 적은 항목은 회차를 모른다고 센다.
- 승인 줄의 날짜는 회차가 아닌 일(부분 반영, 승인)의 날짜도 가장 늦은 날짜로 센다. 그래서 반영을
  적은 날이 늦으면 새 회차가 없어도 만료하지 않는다. 머리·본문·어디로 줄의 날짜는 보지 않는다. 둘 다
  시험으로 고정했다.
- 승인 줄에 회차가 없으면 머리와 본문에서 찾아, 다른 항목의 회차를 인용한 글("17의 3회차")도 그
  항목의 회차로 센다.
- 어디로 줄의 백틱이 홀수 개면 닫히지 않은 백틱 뒤의 경로를 세지 않는다.
- 파일 이름이 번호도 슬러그도 아니어도(`Foo.md`) 라벨 줄이 맞으면 항목으로 센다. 이름 규칙은 저장소
  상태 시험(`tests/test_retro_queue_names.py`)이 본다.
- `README.md`는 항목이 아니고, 하위 폴더의 항목과 `.md`가 아닌 파일은 보지 않는다. 읽기, 찾기,
  `--ref` 모두 같다. 시험으로 고정했다.

쓰임: `uv run python tools/queue_open_rows.py [--queue <폴더> | --ref <커밋>] [--rows]
[--today YYYY-MM-DD]`. 기본은 지금 폴더의 `.scratch/retro-queue/`라 저장소 루트에서 친다.
`--ref`는 그 커밋의 `.scratch/retro-queue/`를 읽는다. `git ls-tree`로 목록을 받고
`git cat-file --batch` 한 프로세스로 내용을 받는다(항목마다 git 을 띄우지 않는다). 폴더가 없는
커밋(이행 전)은 오류로 끝나고 옛 파일 `.scratch/retro-queue.md`로 돌아가지 않는다. 워크트리에서
병합한 뒤에는 `git fetch origin` 뒤 `--ref origin/main`으로 다른 PR이 더한 항목까지 센다.
`--rows`는 열린 항목마다 회차와 대상·인용을 한 줄씩 더 찍는다. 종료 0은 모두 읽었다, 1은 라벨 줄이
빠진 항목이 있다(그 항목을 뺀 수다), 2는 인자가 틀렸거나 대기열을 읽지 못했다(폴더가 없다,
UTF-8 이 아니다 포함).

찾기: `uv run python tools/queue_open_rows.py [--queue <폴더> | --ref <커밋>] --search <정규식>
[--search <정규식> ...]`. retro 5단계의 항목 찾기(새 항목을 쓰기 전에 같은 일을 다룬 항목을
찾는다)가 쓴다. Grep 도구는 긴 줄을 `[Omitted long matching line]`으로만 내고, 세션마다 맞은 항목을
Read 로 다시 열거나 스크래치 스크립트를 지었다(대기열 425).
- 닫힌 항목까지 파일 원문 전체(첫 줄, 라벨 줄, 본문)에 정규식을 맞추고, 여럿이면 하나라도 맞은
  항목이다. 맞은 항목마다 파일 경로(`--queue`로 준 폴더 기준이거나 `--ref`면
  `.scratch/retro-queue/<이름>`), 열림·닫힘(만료도 닫힘이다), 회차(위의 회차 판정), 머리(첫 줄
  `# <ID>: ` 뒤), 승인 줄을 한 줄로 번호 오름차순, 그다음 슬러그 순서로 찍는다. 줄 번호는 찍지
  않는다. 항목이 파일 하나라 맞은 파일을 Read 로 연다. 기본 출력은 내지 않으므로
  `--rows`·`--today`와 함께 주면 쓰임 오류다.
- 낱말은 정규식이다. `[`·`(`·`|`·`\\` 같은 문자는 정규식으로 읽힌다. 셸에서 따옴표 없이 주면 셸도 그
  문자를 읽으므로, 공백과 그 문자는 아무 글자에나 맞는 `.`으로 바꿔 준다. 맞은 항목 수에는 상한이
  없어, 넓은 낱말은 수백 항목을 낸다.
- 머리는 `HEAD_CHARS`(120)자에서 자른다. 승인 줄은 첫 승인으로 시작해 회차와 닫힘을 뒤에 덧붙여 가는
  줄이라, 길면 앞 `APPROVAL_HEAD`(80)자(첫 승인)와 끝 `APPROVAL_TAIL`(160)자(가장 늦게 덧붙인 글의
  꼬리)를 남기고 가운데를 줄인다. 덧붙인 글이 길면 끝에 회차가 들지 않으므로 회차와 열림·닫힘은 줄
  전체에서 판정해 따로 찍는다. 자르거나 줄였으면 그 글자 수를 적는다.
- 종료 0은 맞은 항목을 모두 읽었다(맞은 항목이 없어도 0이다), 1은 맞은 항목 가운데 라벨 줄이 빠진
  항목이 있다(그 항목은 경로와 빠진 줄만 찍고, 머리 줄에 그 수를 따로 센다), 2는 인자나 정규식이
  틀렸거나 대기열을 읽지 못했다.

찾기의 못 보는 것. 모두 시험으로 고정했다.
- 어디에 맞았는지는 찍지 않는다. 어디로 줄, 본문, 잘린 자리에서만 맞은 항목도 찍히지만 그 낱말은
  출력에 없다. 머리로 가리지 못하면 그 파일을 연다.
- 수를 찾으면 그 수를 품은 더 긴 수에도 맞는다(`425`가 `1425`에). 원문 전체에 맞추므로 번호 425
  항목의 첫 줄은 `0425`라 `(?<!\\d)425(?!\\d)`에 맞지 않고, 다른 항목의 `대기열 425` 인용은 `0425`에
  맞지 않는다. 둘 다 찾으려면 `(?<!\\d)0?425(?!\\d)`. `\\b`는 수와 한글 사이를 경계로 보지 않아
  `425의`를 놓친다.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path

QUEUE = Path(".scratch/retro-queue")
README = "README.md"
MIN_ROUNDS = 5
MIN_ROWS = 3
EXPIRY_DAYS = 14
HUMAN = "사람 몫"
HUMAN_MARK = f"{HUMAN}:"
SHARED = f"{MIN_ROWS}개 항목 이상"
HEAD_CHARS = 120
APPROVAL_HEAD = 80
APPROVAL_TAIL = 160
USAGE = (
    "쓰임: uv run python tools/queue_open_rows.py [--queue <폴더> | --ref <커밋>] [--rows]"
    " [--today YYYY-MM-DD]\n"
    "      uv run python tools/queue_open_rows.py [--queue <폴더> | --ref <커밋>]"
    " --search <정규식> [--search <정규식> ...]\n"
)
GIT_TIMEOUT = 30

LABELS = ("**상태:**", "**어디로:**", "**승인:**")
NUMBER = re.compile(r"[0-9]+")
SLUG = re.compile(r"[a-z][a-z0-9-]*")
LINE_SPLIT = re.compile(r"\r?\n")
ROUND = re.compile(r"(\d+)회차")
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
FILE_NAME = re.compile(r"^[\w.-]+\.(md|py|toml|ya?ml|json|lock|ts|tsx|mjs|ps1|sh)$")
NOT_PATH = re.compile(r"[\s{<$]")
ROUND_CELLS = ("승인", "무엇", "어디로")  # 회차를 찾는 차례. 무엇은 머리와 본문이다
FILE_MODES = (b"100644", b"100755")


@dataclass(frozen=True)
class Item:
    """`ident` 는 파일 이름의 stem 이다(`0573`, `coderabbit-inline-size`). `round_cell` 은 회차를
    찾은 곳의 이름이고, 회차를 모르면 None 이다. `last` 는 승인 줄의 가장 늦은 날짜이고, `human` 은
    어디로 줄이 `사람 몫:`으로 시작하는 항목이다."""

    ident: str
    rounds: int | None
    round_cell: str | None
    targets: tuple[str, ...]
    citations: tuple[str, ...]
    last: date | None = None
    human: bool = False


class HitState(Enum):
    """맞은 항목의 상태. `BROKEN` 이면 라벨 줄이 빠져 나머지를 읽지 않았다."""

    OPEN = "열림"
    CLOSED = "닫힘"
    BROKEN = "라벨 줄이 빠졌다"


@dataclass(frozen=True)
class Hit:
    """`--search` 에 맞은 항목. `path` 는 파일 경로이고, `head` 와 `approval` 은 길이를 묶은 머리와
    승인 줄이며, `problem` 은 `BROKEN` 일 때 빠진 줄이다."""

    ident: str
    path: str
    state: HitState
    rounds: int | None = None
    head: str = ""
    approval: str = ""
    problem: str = ""


@dataclass(frozen=True)
class _Fields:
    head: str
    open: bool
    where: str
    approval: str
    body: str


def item_name(identifier: str) -> str:
    """인용 `대기열 <ID>`의 파일 이름. 숫자만이면 네 자리로 채우고(573과 0573은 `0573.md`), 슬러그
    꼴이면 그대로다. 둘 다 아니면 ValueError."""
    if NUMBER.fullmatch(identifier):
        return f"{int(identifier):04d}.md"
    if SLUG.fullmatch(identifier):
        return f"{identifier}.md"
    raise ValueError(f"대기열 식별자가 숫자도 슬러그도 아니다: {identifier!r}")


def item_path(identifier: str) -> Path:
    return QUEUE / item_name(identifier)


def display_id(ident: str) -> str:
    """출력에 찍는 식별자. 숫자면 앞의 0을 뗀 정수 모양이고 슬러그면 그대로다."""
    return str(int(ident)) if NUMBER.fullmatch(ident) else ident


def sort_key(ident: str) -> tuple[int, int, str]:
    """숫자 ID 가 정수 오름차순으로 먼저, 그다음 슬러그가 오름차순이다."""
    if NUMBER.fullmatch(ident):
        return (0, int(ident), "")
    return (1, 0, ident)


def is_item_name(name: str) -> bool:
    return name.endswith(".md") and len(name) > len(".md") and name != README


def _stem(name: str) -> str:
    return name.removesuffix(".md")


def _name_key(name: str) -> tuple[int, int, str]:
    return sort_key(_stem(name))


def is_path(span: str) -> bool:
    if not span or NOT_PATH.search(span) or span.startswith(("-", "/")):
        return False
    return "/" in span or FILE_NAME.match(span) is not None


def is_file(path: str) -> bool:
    """디렉터리(`/`로 끝난다)도 패턴(`*`)도 아닌 경로."""
    return not path.endswith("/") and "*" not in path


def paths_in(where: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """어디로 줄의 경로를 (대상, 인용)으로 가른다. 괄호 깊이가 0이면 대상이다."""
    targets: list[str] = []
    citations: list[str] = []
    depth = 0
    index = 0
    while index < len(where):
        char = where[index]
        if char == "`":
            end = where.find("`", index + 1)
            if end == -1:
                break
            span = where[index + 1 : end]
            if is_path(span):
                (citations if depth else targets).append(span)
            index = end + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        index += 1
    kept = tuple(dict.fromkeys(targets))
    return kept, tuple(path for path in dict.fromkeys(citations) if path not in kept)


def _fields(name: str, text: str) -> _Fields | str:
    """항목 파일의 첫 줄·라벨 줄·본문. 모양이 틀렸으면 까닭(문자열)이다."""
    stem = _stem(name)
    lines = LINE_SPLIT.split(text)
    prefix = f"# {stem}: "
    head = lines[0][len(prefix) :].strip() if lines[0].startswith(prefix) else ""
    if not head:
        return f"첫 줄이 `# {stem}: <머리>` 꼴이 아니다"
    values: list[str] = []
    index = 1
    for label in LABELS:
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines) or not lines[index].startswith(label):
            return f"빠진 줄: {label}"
        values.append(lines[index][len(label) :].strip())
        index += 1
    status, where, approval = values
    if status.startswith("열림"):
        is_open = True
    elif status.startswith(("닫힘", "만료")):
        is_open = False
    else:
        return f"상태 값이 열림·닫힘·만료로 시작하지 않는다: {status!r}"
    return _Fields(head, is_open, where, approval, "\n".join(lines[index:]).strip())


def label_problem(name: str, text: str) -> str | None:
    """파일 `name`(예 `0573.md`)의 내용이 항목 모양이 아니면 까닭, 맞으면 None."""
    found = _fields(name, text)
    return found if isinstance(found, str) else None


def _rounds(fields: _Fields) -> tuple[int | None, str | None]:
    texts = {
        "승인": fields.approval,
        "무엇": f"{fields.head}\n{fields.body}",
        "어디로": fields.where,
    }
    for name in ROUND_CELLS:
        found = [int(count) for count in ROUND.findall(texts[name])]
        if found:
            return max(found), name
    return None, None


def _last_date(approval: str) -> date | None:
    """승인 날짜와 일지 파일명(`YYYY-MM-DD-NN`)의 날짜 가운데 가장 늦은 것. 없는 날짜는 넘는다."""
    found: list[date] = []
    for text in DATE.findall(approval):
        try:
            found.append(date.fromisoformat(text))
        except ValueError:
            continue
    return max(found, default=None)


def read_items(files: dict[str, str]) -> tuple[list[Item], list[str]]:
    """(열린 항목, 라벨 줄이 빠진 항목의 파일 이름). 이름→내용 사전을 받는다. 닫힌·만료 항목은 열린
    목록에 넣지 않는다. `README.md`와 `.md`가 아닌 이름은 항목이 아니다."""
    items: list[Item] = []
    broken: list[str] = []
    for name in sorted(files, key=_name_key):
        if not is_item_name(name):
            continue
        fields = _fields(name, files[name])
        if isinstance(fields, str):
            broken.append(name)
            continue
        if not fields.open:
            continue
        rounds, round_cell = _rounds(fields)
        targets, citations = paths_in(fields.where)
        human = fields.where.lstrip("*").startswith(HUMAN_MARK)
        last = _last_date(fields.approval)
        items.append(Item(_stem(name), rounds, round_cell, targets, citations, last, human))
    return items, broken


def _head(head: str) -> str:
    if len(head) <= HEAD_CHARS:
        return head
    return f"{head[:HEAD_CHARS]} …({len(head) - HEAD_CHARS}자 줄임)"


def _approval(approval: str) -> str:
    """승인 줄. 첫 승인으로 시작해 회차와 닫힘을 덧붙여 가는 줄이라 길면 앞과 끝을 남기고 가운데를
    줄인다."""
    cut = len(approval) - APPROVAL_HEAD - APPROVAL_TAIL
    if cut <= 0:
        return approval
    return f"{approval[:APPROVAL_HEAD]} …(가운데 {cut}자 줄임)… {approval[-APPROVAL_TAIL:]}"


def search(
    files: dict[str, str], patterns: list[re.Pattern[str]], directory: Path = QUEUE
) -> list[Hit]:
    """닫힌 항목까지, 파일 원문에 `patterns` 가운데 하나라도 맞은 항목을 번호, 슬러그 차례로."""
    hits: list[Hit] = []
    for name in sorted(files, key=_name_key):
        text = files[name]
        if not is_item_name(name) or not any(pattern.search(text) for pattern in patterns):
            continue
        ident, path = _stem(name), (directory / name).as_posix()
        fields = _fields(name, text)
        if isinstance(fields, str):
            hits.append(Hit(ident, path, HitState.BROKEN, problem=fields))
            continue
        rounds, _ = _rounds(fields)
        state = HitState.OPEN if fields.open else HitState.CLOSED
        head, approval = _head(fields.head), _approval(fields.approval)
        hits.append(Hit(ident, path, state, rounds=rounds, head=head, approval=approval))
    return hits


def _numbers(items: list[Item]) -> str:
    return " ".join(display_id(item.ident) for item in items)


def _item_key(item: Item) -> tuple[int, int, str]:
    return sort_key(item.ident)


def _grouped(pairs: list[tuple[str, Item]]) -> dict[str, list[Item]]:
    grouped: defaultdict[str, list[Item]] = defaultdict(list)
    for path, item in pairs:
        grouped[path].append(item)
    for group in grouped.values():
        group.sort(key=_item_key)
    return dict(sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0])))


def by_target(items: list[Item]) -> dict[str, list[Item]]:
    return _grouped([(target, item) for item in items for target in item.targets])


def by_citation(items: list[Item]) -> dict[str, list[Item]]:
    return _grouped([(cited, item) for item in items for cited in item.citations])


def _item_line(item: Item) -> str:
    rounds = f"{item.rounds}회차({item.round_cell})" if item.rounds is not None else "회차 모름"
    targets = ", ".join(item.targets) or "(대상 경로 없음)"
    cited = f" / 인용: {', '.join(item.citations)}" if item.citations else ""
    return f"  {display_id(item.ident)} {rounds} 대상: {targets}{cited}"


def _groups(groups: dict[str, list[Item]]) -> list[str]:
    return [f"  `{path}`: {_numbers(group)}" for path, group in groups.items()]


def render(items: list[Item], broken: list[str], today: date | None = None) -> str:
    """`today` 가 없으면 오늘(로컬 날짜)을 기준으로 만료를 판정한다. `broken` 은 한 항목에 한 줄로
    그대로 찍는다(파일 경로와 빠진 줄)."""
    out = [f"열린 항목 {len(items)}개"]
    counted = [item for item in items if not item.human]
    ripe = sorted(
        (item for item in counted if item.rounds is not None and item.rounds >= MIN_ROUNDS),
        key=lambda item: (-(item.rounds or MIN_ROUNDS), *_item_key(item)),
    )
    waiting = [item for item in counted if item not in ripe]
    listed = " ".join(f"{display_id(item.ident)}({item.rounds}회차)" for item in ripe)
    out.append(f"회차 {MIN_ROUNDS} 이상: {listed or '(없음)'}")
    humans = [item for item in items if item.human]
    if humans:
        out.append(f"{HUMAN}(회차를 chore 계기로 세지 않고 만료하지 않는다): {_numbers(humans)}")
    day = today or datetime.now().astimezone().date()  # 이 기계의 시간대
    cutoff = day - timedelta(days=EXPIRY_DAYS)
    stale = sorted(
        (item for item in waiting if item.last is not None and item.last < cutoff),
        key=lambda item: (item.last or cutoff, *_item_key(item)),
    )
    expired = " ".join(f"{display_id(item.ident)}({item.last})" for item in stale)
    out.append(f"만료할 항목(승인 줄의 가장 늦은 날짜가 {cutoff} 전): {expired or '(없음)'}")
    undated = [
        item for item in waiting if item.last is None
    ]  # 만료할 수 있는 항목만 날짜가 필요하다
    if undated:
        out.append(f"날짜를 찾지 못한 항목: {_numbers(undated)}")
    grouped = by_target(items)
    shared = {
        path: group for path, group in grouped.items() if is_file(path) and len(group) >= MIN_ROWS
    }
    if shared:
        out.append(
            f"같은 대상 파일이 {SHARED}(chore 계기가 아니다. chore 를 고른 뒤 함께 묶을 항목이다."
            " 항목 원문으로 실제 대상인지 가른다):"
        )
        out.extend(_groups(shared))
    else:
        out.append(f"같은 대상 파일이 {SHARED}: (없음)")
    containers = {path: group for path, group in grouped.items() if not is_file(path)}
    if containers:
        out.append("디렉터리·패턴 대상(조건에 세지 않는다):")
        out.extend(_groups(containers))
    cited = by_citation(items)
    if cited:
        out.append("괄호 안의 인용으로 센 경로(대상이면 위의 수에 더한다):")
        out.extend(_groups(cited))
    unknown = [item for item in items if item.rounds is None]
    if unknown:
        out.append(f"회차를 찾지 못한 항목: {_numbers(unknown)}")
    if broken:
        out.append("라벨 줄이 빠진 항목: (세지 않았다. 항목 파일의 라벨 줄을 고치고 다시 센다)")
        out.extend(f"  {entry}" for entry in broken)
    return "\n".join(out)


def render_rows(items: list[Item]) -> str:
    """`--rows` 가 기본 출력 뒤에 붙이는 항목마다·대상마다의 줄."""
    out = [
        "항목마다:",
        *(_item_line(item) for item in items),
        "대상마다:",
        *_groups(by_target(items)),
    ]
    return "\n".join(out)


def _hit_line(hit: Hit) -> str:
    if hit.state is HitState.BROKEN:
        return f"  {hit.path} {hit.state.value}({hit.problem}). 그 파일을 열어 본다"
    rounds = f"{hit.rounds}회차" if hit.rounds is not None else "회차 모름"
    return f"  {hit.path} {hit.state.value} {rounds} 머리: {hit.head} / 승인: {hit.approval}"


def _count(hits: list[Hit], state: HitState) -> int:
    return sum(hit.state is state for hit in hits)


def render_hits(hits: list[Hit]) -> str:
    """`--search` 의 출력. 맞은 항목마다 한 줄이다."""
    if not hits:
        return "맞은 항목 없음"
    counts = [
        f"열린 항목 {_count(hits, HitState.OPEN)}개",
        f"닫힌 항목 {_count(hits, HitState.CLOSED)}개",
    ]
    broken = _count(hits, HitState.BROKEN)
    if broken:
        counts.append(f"라벨 줄이 빠진 항목 {broken}개")
    head = (
        f"맞은 항목 {len(hits)}개({', '.join(counts)})."
        " 같은 일로 보이는 항목은 그 파일을 Read 로 연다:"
    )
    return "\n".join([head, *(_hit_line(hit) for hit in hits)])


def read_folder(path: Path) -> dict[str, str]:
    """폴더 바로 아래의 항목 파일(`README.md`와 하위 폴더, `.md`가 아닌 것을 뺀다)의 이름→내용.
    폴더가 없거나 UTF-8 이 아니면 OSError, UnicodeDecodeError 로 올린다."""
    files: dict[str, str] = {}
    for entry in sorted(path.iterdir(), key=lambda entry: _name_key(entry.name)):
        if is_item_name(entry.name) and entry.is_file():
            files[entry.name] = entry.read_text(encoding="utf-8")
    return files


def git_bytes(args: list[str], stdin: bytes | None = None) -> bytes:
    """`git <args>` 의 표준 출력. git 이 실패하거나 시간을 넘기면 OSError 로 올린다."""
    try:
        done = subprocess.run(
            ["git", *args],
            input=stdin or b"",
            capture_output=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise OSError(f"git {args[0]} 가 {GIT_TIMEOUT}초 안에 끝나지 않았다") from error
    if done.returncode != 0:
        message = done.stderr.decode("utf-8", errors="replace").strip()
        raise OSError(message or f"git {args[0]} 가 {done.returncode}로 끝났다")
    return done.stdout


def read_ref_folder(ref: str) -> dict[str, str]:
    """커밋 `ref` 의 `.scratch/retro-queue/` 의 항목 파일 이름→내용. `git ls-tree` 로 목록을, `git
    cat-file
    --batch` 한 프로세스로 내용을 받는다. 폴더가 없으면 OSError 이고 옛 파일로 돌아가지 않는다."""
    listing = git_bytes(["ls-tree", "-z", f"{ref}:{QUEUE.as_posix()}"])
    wanted: list[tuple[str, bytes]] = []
    for line in listing.split(b"\0"):
        meta, _, raw = line.partition(b"\t")
        fields = meta.split(b" ")
        name = raw.decode("utf-8", errors="replace")
        if len(fields) == 3 and fields[1] == b"blob" and fields[0] in FILE_MODES:
            if is_item_name(name):
                wanted.append((name, fields[2]))
    if not wanted:
        return {}
    out = git_bytes(["cat-file", "--batch"], b"".join(sha + b"\n" for _, sha in wanted))
    files: dict[str, str] = {}
    position = 0
    for name, _ in wanted:
        end = out.find(b"\n", position)
        header = out[position:end].split(b" ") if end != -1 else []
        if len(header) != 3 or header[1] != b"blob":
            raise OSError(f"git cat-file 의 출력을 읽지 못했다: {name}")
        start = end + 1
        stop = start + int(header[2])
        files[name] = out[start:stop].decode("utf-8")
        position = stop + 1
    return files


class _UsageError(Exception):
    """인자를 잘못 줬다. 대기열을 읽기 전에 난다. 메시지(줄바꿈까지)는 쓰임 앞에 그대로 붙는다."""


@dataclass(frozen=True)
class _Args:
    """가른 인자. `patterns` 가 있으면 찾기이고, 그때 `each` 는 거짓, `today` 는 없다."""

    path: Path | None
    ref: str | None
    today: date | None
    each: bool
    patterns: list[re.Pattern[str]]


def _parse(argv: list[str]) -> _Args:
    """인자를 가른다. 틀렸으면 `_UsageError`."""
    path: Path | None = None
    ref: str | None = None
    today: date | None = None
    each = False
    patterns: list[re.Pattern[str]] = []
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--rows":
            each = True
        elif arg == "--search" and args:
            source = args.pop(0)
            try:
                patterns.append(re.compile(source))
            except (re.error, OverflowError, RecursionError) as error:
                # 큰 반복 수(`a{99999999999}`)와 깊은 괄호는 re.error 가 아닌 것을 던진다
                raise _UsageError(f"정규식이 틀렸다: {source}: {error}\n") from error
        elif arg == "--today" and args and today is None:
            try:
                today = date.fromisoformat(args.pop(0))
            except ValueError as error:
                raise _UsageError from error
        elif arg == "--queue" and args and ref is None:
            path = Path(args.pop(0))
        elif arg == "--ref" and args and path is None and not args[0].startswith("-"):
            # `-` 로 시작하면 git 이 옵션으로 읽는다(`--output=<경로>` 는 파일을 쓴다)
            ref = args.pop(0)
        else:
            raise _UsageError
    if patterns and (each or today is not None):
        raise _UsageError  # 검색은 기본 출력을 내지 않아 그 옵션이 쓰일 자리가 없다
    return _Args(path, ref, today, each, patterns)


def main(argv: list[str]) -> int:
    try:
        args = _parse(argv)
    except _UsageError as error:
        sys.stderr.write(f"{error}{USAGE}")
        return 2
    directory = args.path or QUEUE
    try:
        files = read_ref_folder(args.ref) if args.ref is not None else read_folder(directory)
    except (OSError, UnicodeDecodeError) as error:
        # 해독 실패를 놓치면 트레이스백의 종료 1이 "라벨 줄이 빠진 항목" 과 섞인다
        sys.stderr.write(f"대기열을 읽지 못했다: {error}\n")
        return 2
    if args.patterns:
        hits = search(files, args.patterns, directory)
        print(render_hits(hits))
        return 1 if any(hit.state is HitState.BROKEN for hit in hits) else 0
    items, broken = read_items(files)
    shown = [
        f"{(directory / name).as_posix()} ({label_problem(name, files[name])})" for name in broken
    ]
    print(render(items, shown, args.today))
    if args.each:
        print(render_rows(items))
    return 1 if broken else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
