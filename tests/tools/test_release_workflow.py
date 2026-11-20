"""`.github/workflows/release.yml` 의 꼴 시험(release-image 08).

릴리스 워크플로 자체에는 자동 시험이 없다(명세 Testing Decisions). 워크플로가 부르는 판정은
`test_release.py` 와 `test_release_ci.py` 가 보고, 감사는 zizmor 가 한다. 이 시험은 그 둘이 못 보는
꼴만 글자로 본다. YAML 을 풀지 않고 글을 줄 단위로 읽는다(PyYAML 은 이 저장소가 선언한 의존성이
아니다).

agent-os 의 같은 이름 시험(커밋 `1aac0cf`)은 릴리스의 첫 실제 실행(2026-11-17)이
`시험한 이미지와 올린 이미지 대조` 단계에서 시작도 못 하고 `Argument list too long` 으로 죽은 일에서
나왔다. 그 단계는 bake 액션의 `metadata` 출력(출처 증명에 든 GitHub 컨텍스트까지 실려 약 185KB)을
환경 변수로 받았고, 리눅스의 환경 변수 하나는 커널 상한(`MAX_ARG_STRLEN`, 128KiB 로 본다. 러너에서
재지 않았다)을 넘으면 `bash` 를 띄우지 못한다. 첫 셋은 그 모양을 막는다. 크기는 입력이 정하므로 작은
날의 CI로는 보이지 않는다.

나머지는 이 저장소에서 더한 것이다. 계기와 잡의 수, 액션의 고정, 로그인의 차례, 태그와 표시, 제한
시간, 단독 compose 시험과 판정 도구가 이름으로 맞물리는 자리를 본다. 못 보는 것은 각 도우미의
독스트링에 적었다.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools.release_ci import BAKE_FILE, IMAGES

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
STANDALONE_TEST = ROOT / "tests" / "standalone" / "test_standalone_compose.py"

# `${{ steps.<id>.outputs.metadata }}` 꼴의 표현식. bake 액션의 출력 이름이 `metadata` 다.
_METADATA_EXPRESSION = re.compile(r"\$\{\{\s*steps\.[\w-]+\.outputs\.metadata\s*\}\}")
_JOB_HEADER = re.compile(r"^  (?P<name>[a-z][a-z0-9-]*):\s*$")
_STEP_NAME = re.compile(r"^      - name:\s*(?P<name>.+?)\s*$")
_USES = re.compile(r"^\s*(?:- )?uses:\s*(?P<ref>\S+)")
_PINNED_USES = re.compile(r"[\w./-]+@[0-9a-f]{40}")
# 고정이 필요 없는 곳은 같은 저장소의 로컬 액션(`./…`)뿐이다. 이 워크플로는 로컬 액션을 쓰지 않는다.
_TIMEOUT = re.compile(r"^    timeout-minutes:\s*(?P<minutes>\d+)\s*$", re.M)

# 캐시가 없는 첫 잡의 셈(release.yml 의 build 옆 주석): 시험용 이미지 짓기 10 + 모델 폴더 준비 5 +
# 단독 compose 시험 40(기다림 1800초 30분 + 검색 시험 10) + 점검 10 + 올리기 10 + 대조와 아티팩트 5
# = 80분. 제한은 이 셈을 넘어야 한다.
BUILD_WORST_CASE_MINUTES = 80


def code_lines(text: str) -> list[str]:
    """YAML 주석 줄(`#` 으로 시작하는 줄)을 뺀 줄. 줄 끝의 `# 판` 주석은 그대로 둔다."""
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def job_text(text: str, job: str) -> str:
    """`jobs:` 아래 두 칸 들여 쓴 잡 하나의 글(다음 잡 머리 앞까지)."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {job}:"), None)
    if start is None:
        return ""
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if _JOB_HEADER.match(lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def job_names(text: str) -> list[str]:
    """`jobs:` 아래 잡의 이름들. `jobs:` 앞의 최상위 키(`permissions:` 등)는 세지 않는다."""
    lines = text.splitlines()
    start = lines.index("jobs:")
    return [m["name"] for line in lines[start + 1 :] if (m := _JOB_HEADER.match(line))]


def step_names(job: str) -> list[str]:
    return [m["name"] for line in job.splitlines() if (m := _STEP_NAME.match(line))]


def unpinned_uses(text: str) -> list[str]:
    """커밋 해시(40자)로 고정되지 않은 `uses:` 의 값을 모은다. 주석 줄은 보지 않는다.

    못 보는 것: 해시가 그 저장소의 실제 커밋인지, 뒤의 판 주석이 해시와 맞는지(릴리스를 고를 때
    손으로 태그를 해시로 풀어 대 보았다), 컨테이너를 `docker://` 로 부르는 꼴(이 워크플로는 쓰지
    않는다).
    """
    found: list[str] = []
    for line in code_lines(text):
        match = _USES.match(line)
        if match is not None and _PINNED_USES.fullmatch(match["ref"]) is None:
            found.append(match["ref"])
    return found


def metadata_expression_lines(text: str) -> list[str]:
    """워크플로 글에서 bake의 `metadata` 출력을 끌어 쓰는 줄을 모은다.

    못 보는 것: 출력을 `toJSON` 등으로 감싸거나 대괄호 꼴(`steps['push'].outputs.metadata`)로 쓰거나
    다른 이름의 출력으로 다시 내보내 환경 변수에 싣는 길, `metadata` 가 아닌 다른 큰 출력. 이 이름
    하나만 막는다. 환경 변수 자리만 가리지 않고 줄 안 어디든 쓰면 잡으므로 YAML 주석에 적은 표현식도
    잡는다(거짓 양성)."""
    return [line.strip() for line in text.splitlines() if _METADATA_EXPRESSION.search(line)]


def test_이_저장소의_릴리스_워크플로는_bake_메타데이터_출력을_표현식으로_쓰지_않는다() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    # 범위가 비면 위반 0으로 조용히 초록이다. 이 단계가 있는 파일을 읽었는지 먼저 본다.
    assert "시험한 이미지와 올린 이미지 대조" in text
    assert metadata_expression_lines(text) == []


def test_이_저장소의_릴리스_워크플로는_올린_digest를_해시_태그에서_읽는다() -> None:
    # 옛 모양을 막는 위 시험은 해시 태그 읽기를 지워도 초록이다. 새 모양이 있음을 따로 본다.
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'imagetools inspect "$NAMESPACE/$repo:$HASH_TAG"' in text


def test_이_저장소의_릴리스_워크플로는_올리는_태그와_읽는_태그를_한_변수에서_받는다() -> None:
    # 읽는 쪽 단언만으로는 잡의 HASH_TAG 정의를 지우거나 올리기 단계의 TAG 를 틀리게 해도 초록이다.
    # 올린 태그와 읽는 태그가 갈라지는 회귀를 막으려고 정의와 올리는 쪽을 따로 본다.
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "HASH_TAG: sha-${{ github.sha }}" in text
    assert "TAG: ${{ env.HASH_TAG }}" in text
    assert text.count("sha-${{ github.sha }}") == 1


def test_bake_메타데이터를_환경_변수로_받는_줄을_잡는다() -> None:
    text = "\n".join(
        [
            "        env:",
            "          NUMBER: ${{ steps.plan.outputs.number }}",
            "          METADATA: ${{ steps.push.outputs.metadata }}",
        ]
    )
    assert metadata_expression_lines(text) == ["METADATA: ${{ steps.push.outputs.metadata }}"]


def test_번호처럼_작은_출력은_잡지_않는다() -> None:
    text = "          NUMBER: ${{ steps.plan.outputs.number }}"
    assert metadata_expression_lines(text) == []


def on_triggers(text: str) -> list[str]:
    """`on:` 블록 바로 아래(두 칸 들여 쓴) 실행 계기의 이름들. 주석 줄은 보지 않는다.

    못 보는 것: `on: [push]` 처럼 한 줄에 적은 꼴과 `on: push` 꼴(블록이 아니라 계기를 못 읽어 빈
    목록이 된다). 그래서 이 저장소 시험은 빈 목록도 실패로 본다.
    """
    lines = code_lines(text)
    if "on:" not in lines:
        return []
    found: list[str] = []
    for line in lines[lines.index("on:") + 1 :]:
        if line and not line.startswith(" "):
            break
        if (m := re.match(r"^  (?P<name>[A-Za-z_]+):", line)) is not None:
            found.append(m["name"])
    return found


def test_이_저장소의_릴리스_워크플로는_main_푸시에서만_돌고_수동_실행이_없다() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    head = "\n".join(code_lines(text)).split("jobs:")[0]
    assert re.search(r"^on:\n  push:\n    branches: \[main\]\n", head, re.M) is not None
    # 계기는 push 하나뿐이다. `repository_dispatch` 같은 다른 계기를 더하면 main 푸시가 아닌
    # 실행으로 올리기가 돈다. 빈 목록은 `on:` 블록을 못 읽은 것이라 위반 0으로 초록이 되지 않게
    # 막는다.
    assert on_triggers(text) == ["push"]
    assert "workflow_dispatch" not in head
    assert "pull_request" not in head
    assert "schedule" not in head


def test_main_푸시_말고_다른_실행_계기가_더해진_워크플로를_잡는다() -> None:
    base = "name: x\non:\n  push:\n    branches: [main]\njobs:\n  a:\n"
    assert on_triggers(base) == ["push"]
    extra = base.replace("on:\n  push:", "on:\n  repository_dispatch:\n  push:")
    assert on_triggers(extra) == ["repository_dispatch", "push"]
    commented = base.replace("on:\n", "on:\n  # workflow_dispatch:\n")
    assert on_triggers(commented) == ["push"]
    assert on_triggers("name: x\njobs:\n  a:\n") == []


def test_이_저장소의_릴리스_워크플로는_한_번에_하나만_돌고_기다리는_실행을_취소하지_않는다() -> (
    None
):
    text = "\n".join(code_lines(WORKFLOW.read_text(encoding="utf-8")))
    assert "concurrency:\n  group: release\n  cancel-in-progress: false\n" in text


def test_이_저장소의_릴리스_워크플로는_잡이_build와_publish_둘이고_둘_다_환경_release를_쓴다() -> (
    None
):
    text = WORKFLOW.read_text(encoding="utf-8")
    assert job_names(text) == ["build", "publish"]
    for job in ("build", "publish"):
        assert "    environment: release\n" in job_text(text, job)


def test_이_저장소의_릴리스_워크플로는_모든_액션을_커밋_해시로_고정한다() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    # 범위가 비면 위반 0으로 조용히 초록이다. 액션을 쓰는 줄이 있는 파일을 읽었는지 본다.
    assert any(_USES.match(line) for line in code_lines(text))
    assert unpinned_uses(text) == []


def test_해시가_아닌_태그로_부른_액션을_잡는다() -> None:
    text = "      - uses: actions/checkout@v4\n      - uses: docker/login-action@" + "a" * 40 + "\n"
    assert unpinned_uses(text) == ["actions/checkout@v4"]
    assert unpinned_uses("      # - uses: actions/checkout@v4\n") == []


# (앞 단계, 뒤 단계). 시험과 점검은 로그인 앞, 올리기는 로그인 뒤, 올린 이미지 대조는 올리기 뒤,
# 노트는 점검 뒤(점검의 경고 판정을 노트가 확인한다).
STEP_ORDER = (
    ("단독 compose 시험", "Docker Hub 로그인"),
    ("점검", "Docker Hub 로그인"),
    ("Docker Hub 로그인", "이미지 올리기"),
    ("이미지 올리기", "시험한 이미지와 올린 이미지 대조"),
    ("점검", "노트 짓기"),
)


def out_of_order(names: list[str]) -> list[tuple[str, str]]:
    """`STEP_ORDER` 에서 이름이 없거나 앞뒤가 뒤집힌 쌍을 모은다.

    못 보는 것: 같은 이름의 단계가 둘이면 첫째만 센다(이 워크플로의 `build` 에는 없다). 단계의 `if`
    조건이 실제로 단계를 건너뛰게 하는지, 단계가 `needs` 로 다른 잡에 있는지는 보지 않는다. 이름은
    `      - name: 이름` 꼴의 글자만 읽는다. 이름에 따옴표를 치거나(`"점검"`) 줄 뒤에 주석을 붙이면
    (`점검 # …`) 그 글자째 이름이 되어 이름이 없다고 읽고, `- id:` 로 시작하는 단계는 읽지 못한다.
    그래서 꼴이 바뀌면 거짓 양성(이름이 없다는 실패)이 난다. 이 워크플로는 꼴대로 쓰여 있다.
    """
    return [
        (first, later)
        for first, later in STEP_ORDER
        if first not in names or later not in names or names.index(first) > names.index(later)
    ]


def test_이_저장소의_릴리스_워크플로는_시험과_점검을_마친_뒤에_Docker_Hub에_로그인한다() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    names = step_names(job_text(text, "build"))
    assert names  # 단계를 하나도 못 읽었으면 위반 0으로 조용히 초록이다
    assert out_of_order(names) == []
    # 로그인 액션과 접근 토큰은 로그인 단계에만 쓴다. 빌드 잡의 다른 단계가 토큰을 받으면 시험이
    # 도는 동안 러너에 자격이 있는 셈이다.
    build = job_text(text, "build")
    assert build.count("docker/login-action@") == 1
    assert build.count("secrets.DOCKERHUB_TOKEN") == 1


def test_이_저장소의_릴리스_워크플로는_latest_태그와_사전_릴리스_표시를_쓰지_않는다() -> None:
    code = "\n".join(code_lines(WORKFLOW.read_text(encoding="utf-8")))
    assert ":latest" not in code
    assert "prerelease" not in code
    assert re.search(r"tags?:\s*latest", code) is None


def test_이_저장소의_릴리스_워크플로는_build_잡의_제한_시간을_캐시_없는_셈보다_길게_둔다() -> None:
    build = job_text(WORKFLOW.read_text(encoding="utf-8"), "build")
    match = _TIMEOUT.search(build)
    assert match is not None
    assert int(match["minutes"]) > BUILD_WORST_CASE_MINUTES
    # 셈이 잡 옆 주석에 적혀 있다.
    assert "1800" in build


def test_이_저장소의_릴리스_워크플로는_단독_compose_시험에_환경_변수를_모두_넘긴다() -> None:
    test = STANDALONE_TEST.read_text(encoding="utf-8")
    names = re.findall(
        r'^(?:NAMESPACE|VERSION|BUNDLE|MODELS|LOGS)_ENV: Final = "(\w+)"', test, re.M
    )
    assert len(names) == 5  # 시험이 입력으로 받는 이름 다섯을 읽었는지 본다
    text = WORKFLOW.read_text(encoding="utf-8")
    step = _step_text(text, "build", "단독 compose 시험")
    # 모델 폴더와 로그 폴더는 잡 전체의 env 에 두고, 나머지 셋은 시험 단계가 직접 받는다.
    job_env = re.search(r"^    env:\n(?P<body>(?:      .*\n)+)", job_text(text, "build"), re.M)
    assert job_env is not None
    for name in names:
        assert f"{name}:" in step or f"{name}:" in job_env["body"]
    assert "uv run pytest tests/standalone" in step


def test_이_저장소의_릴리스_워크플로는_이미지_이름과_짓기_파일을_판정_도구와_같이_쓴다() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert f"files: {BAKE_FILE}" in text
    assert text.count(f"files: {BAKE_FILE}") == 2  # 시험용으로 한 번, 올리기로 한 번
    assert f"for image in {' '.join(IMAGES)}; do" in text
    for image in IMAGES:
        assert f"--grype {image}=out/grype-{image}.json" in text
        assert f'--digest "{image}=$DIGEST_{image.upper()}"' in text


def test_이_저장소의_릴리스_워크플로는_지은_서버_이미지의_계약_버전을_노트에_넘긴다() -> None:
    step = _step_text(WORKFLOW.read_text(encoding="utf-8"), "build", "노트 짓기")
    assert "rag-engine --version" in step
    assert "--contract-versions" in step


def _step_text(text: str, job: str, step: str) -> str:
    """잡 안의 단계 하나의 글(다음 단계 머리 앞까지). 없으면 빈 글."""
    lines = job_text(text, job).splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == f"- name: {step}"), None)
    if start is None:
        return ""
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if _STEP_NAME.match(lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def test_로그인이_시험_앞으로_오거나_대조가_없으면_잡는다() -> None:
    ok = [first for first, _ in STEP_ORDER] + [later for _, later in STEP_ORDER]
    ok = list(dict.fromkeys(ok))
    # 한 번 올바른 차례(앞 단계가 모두 뒤 단계보다 앞)를 만들어 위반 0을 확인한다.
    ordered = [
        "점검",
        "단독 compose 시험",
        "Docker Hub 로그인",
        "노트 짓기",
        "이미지 올리기",
        "시험한 이미지와 올린 이미지 대조",
    ]
    assert set(ordered) == set(ok)
    assert out_of_order(ordered) == []
    # 로그인을 점검 앞으로 옮기면 그 쌍이 잡힌다.
    login_first = ["Docker Hub 로그인", *[n for n in ordered if n != "Docker Hub 로그인"]]
    assert ("점검", "Docker Hub 로그인") in out_of_order(login_first)
    # 대조 단계를 지우면 없는 이름으로 잡는다. 주석만 남긴 파일도 단계 이름이 아니라서 걸린다.
    no_check = [n for n in ordered if n != "시험한 이미지와 올린 이미지 대조"]
    assert ("이미지 올리기", "시험한 이미지와 올린 이미지 대조") in out_of_order(no_check)


def test_단계_글을_이름으로_잘라_낸다() -> None:
    text = "jobs:\n  build:\n    steps:\n      - name: 가\n        run: a\n"
    text += "      - name: 나\n        run: b\n"
    assert "run: a" in _step_text(text, "build", "가")
    assert "run: b" not in _step_text(text, "build", "가")
    assert _step_text(text, "build", "없다") == ""
