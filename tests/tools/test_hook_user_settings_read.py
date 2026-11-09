"""tools/hook_user_settings_read.py 의 판정. 경로는 윈도와 POSIX 둘 다 이 테스트가 고른 환경으로
푼다.

CI 는 우분투에서 돌아, 윈도 경로의 판정을 그 OS 의 경로 모듈에 기대면 거기서 갈린다. 그래서 판정은
`windows` 인자로 경로 모듈을 고르고, 환경(`USERPROFILE`·`HOME`·`CLAUDE_CONFIG_DIR`)도 인자로 받는다.
"""

from __future__ import annotations

import pytest
from tools.hook_user_settings_read import Places, ToolInput, keys_command, places, reason_for
from tools.run_hooks import registered_matchers

WINDOWS = {"USERPROFILE": "C:\\Users\\u", "HOME": "/c/Users/u"}
PROJECT = "C:\\project\\agent"


def _windows(cwd: str = PROJECT, **extra: str) -> Places:
    return places({**WINDOWS, **extra}, cwd, "nt")


def _posix(cwd: str = "/work/agent") -> Places:
    return places({"HOME": "/home/u"}, cwd, "posix")


@pytest.mark.parametrize(
    "경로",
    [
        pytest.param("C:\\Users\\u\\.claude\\settings.json", id="사용자_설정"),
        pytest.param("C:/Users/u/.claude.json", id="앱_상태_파일"),
        pytest.param("c:\\users\\U\\.CLAUDE.JSON", id="대소문자"),
        pytest.param("C:\\Users\\u\\.claude\\..\\.claude.json", id="점점"),
    ],
)
def test_사용자_설정_파일을_Read_하면_막는다(경로: str) -> None:
    reason = reason_for("Read", {"file_path": 경로}, _windows())

    assert reason is not None
    assert "키 이름만" in reason


def test_Git_Bash_의_드라이브_경로를_윈도_경로로_푼다() -> None:
    """명령의 `/c/…` 와 환경의 `HOME=/c/…` 둘 다 `C:/…` 로 푼다. 한쪽만 그 꼴이면 바꾸지 않고는
    맞지 않는다(변이로 봤다)."""
    command: ToolInput = {"command": "head -50 /c/Users/u/.claude/settings.json"}
    profile_only = places({"USERPROFILE": "C:\\Users\\u"}, PROJECT, "nt")
    home_only = places({"HOME": "/c/Users/u"}, PROJECT, "nt")

    assert reason_for("Bash", command, profile_only) is not None
    assert reason_for("Read", {"file_path": "C:\\Users\\u\\.claude.json"}, home_only) is not None


def test_PowerShell_의_HOME_은_환경에_없어도_홈이다() -> None:
    """PowerShell 의 `$HOME` 은 자동 변수다. 윈도의 환경에는 `HOME` 이 없을 수 있다."""
    place = places({"USERPROFILE": "C:\\Users\\u"}, PROJECT, "nt")
    command = "Get-Content $HOME\\.claude\\settings.json"

    assert reason_for("PowerShell", {"command": command}, place) is not None
    assert reason_for("PowerShell", {"command": "gc $env:HOME\\.claude.json"}, place) is not None


def test_POSIX_의_홈에서도_막는다() -> None:
    """CI(우분투)의 훅 러너가 PowerShell 꼴의 사례도 돌린다. 거기서도 백슬래시를 구분자로 본다."""
    command = "Get-Content $HOME\\.claude\\settings.json"

    assert reason_for("Read", {"file_path": "/home/u/.claude/settings.json"}, _posix()) is not None
    assert reason_for("Bash", {"command": "cat ~/.claude.json"}, _posix()) is not None
    assert reason_for("PowerShell", {"command": command}, _posix()) is not None


@pytest.mark.parametrize(
    "경로",
    [
        pytest.param(f"{PROJECT}\\.claude\\settings.json", id="프로젝트_설정_update_config"),
        pytest.param("C:\\Users\\u\\.claude\\settings.local.json", id="사용자_local"),
        pytest.param("C:\\Users\\u\\.claude.json.bak", id="다른_이름"),
        pytest.param("C:\\Users\\u\\.claude\\skills\\x\\SKILL.md", id="사용자_스킬"),
    ],
)
def test_다른_파일의_Read_는_지나간다(경로: str) -> None:
    """update-config 가 이 저장소에서 여는 것은 프로젝트 설정이다(반례 축, 대기열 272)."""
    assert reason_for("Read", {"file_path": 경로}, _windows()) is None


def test_상대_경로는_페이로드의_cwd_로_푼다() -> None:
    target: ToolInput = {"file_path": ".claude\\settings.json"}

    assert reason_for("Read", target, _windows(cwd="C:\\Users\\u")) is not None
    assert reason_for("Read", target, _windows()) is None


def test_CLAUDE_CONFIG_DIR_의_설정도_막는다() -> None:
    place = _windows(CLAUDE_CONFIG_DIR="D:\\cfg")

    assert reason_for("Read", {"file_path": "D:\\cfg\\settings.json"}, place) is not None
    assert reason_for("Bash", {"command": "cat $CLAUDE_CONFIG_DIR/settings.json"}, place)


@pytest.mark.parametrize(
    ("경로", "glob", "막는다"),
    [
        pytest.param("C:\\Users\\u\\.claude.json", None, True, id="파일_경로"),
        pytest.param("C:\\Users\\u", ".claude.json", True, id="홈과_이름"),
        pytest.param("C:\\Users\\u", "*.json", True, id="홈과_확장자"),
        pytest.param("C:\\Users\\u\\.claude", "*.json", True, id="설정_폴더"),
        pytest.param("C:\\Users\\u\\.claude", None, True, id="설정_폴더_glob_없이"),
        pytest.param("C:\\Users\\u", None, True, id="홈_glob_없이"),
        pytest.param("C:\\Users", "*.json", True, id="홈의_위"),
        pytest.param("C:\\Users\\u\\.claude", "**/*.{md,json}", True, id="중괄호_glob"),
        pytest.param("C:\\Users\\u", "*.py", False, id="다른_확장자"),
        pytest.param("C:\\Users\\u\\.claude", "*.{md,py}", False, id="중괄호_다른_확장자"),
        pytest.param(f"{PROJECT}\\.claude", "*.json", False, id="프로젝트"),
        pytest.param(PROJECT, None, False, id="저장소"),
    ],
)
def test_Grep_도구는_경로나_glob_이_사용자_설정에_닿으면_막는다(
    경로: str, glob: str | None, *, 막는다: bool
) -> None:
    """git 저장소가 아닌 폴더에서 Grep 도구는 glob 없이도 숨김 파일을 읽었다(셀프 리뷰 표준 축이
    가짜 파일로 손으로 봤다). 그래서 대상을 품은 폴더면 glob 이 없어도 막는다. glob 의 중괄호는
    ripgrep 처럼 펼친다(PR 직전 버그 축)."""
    tool_input: ToolInput = {"path": 경로, "output_mode": "content"}
    if glob is not None:
        tool_input["glob"] = glob

    assert (reason_for("Grep", tool_input, _windows()) is not None) is 막는다


@pytest.mark.parametrize("출력", [None, "files_with_matches", "count"])
def test_내용을_내지_않는_Grep_은_지나간다(출력: str | None) -> None:
    """Grep 도구의 기본 출력은 파일 이름(`files_with_matches`)이다. 이름과 수는 비밀을 내지 않는다
    (PR 직전 버그 축). 정규식으로 값을 맞혀 보는 길도 그래서 지나간다(못 보는 것)."""
    tool_input: ToolInput = {"path": "C:\\Users\\u\\.claude.json"}
    if 출력 is not None:
        tool_input["output_mode"] = 출력

    assert reason_for("Grep", tool_input, _windows()) is None


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param("cat ~/.claude/settings.json", id="cat"),
        pytest.param("cat $HOME/.claude.json", id="HOME_변수"),
        pytest.param('cat "${HOME}/.claude.json"', id="중괄호_변수_인용"),
        pytest.param("head -50 /c/Users/u/.claude/settings.json", id="MSYS_경로"),
        pytest.param("jq . ~/.claude.json", id="jq_전체"),
        pytest.param("jq .env ~/.claude/settings.json", id="jq_한_갈래"),
        pytest.param("grep -n env ~/.claude/settings.json", id="grep"),
        pytest.param("echo $(cat ~/.claude.json)", id="명령_치환"),
        pytest.param('bash -c "cat ~/.claude.json"', id="셸_래퍼"),
        pytest.param("cat < ~/.claude.json", id="입력_리다이렉션"),
        pytest.param("git status && sed -n 1,40p ~/.claude/settings.json", id="묶은_명령"),
        pytest.param("FOO=1 cat ~/.claude.json", id="환경_대입"),
        pytest.param("cat \\\n~/.claude.json", id="줄_이어_쓰기"),
        pytest.param("rg KEY ~/.claude", id="rg_설정_폴더"),
        pytest.param("grep -rn KEY ~/.claude/", id="grep_재귀_설정_폴더"),
        pytest.param("grep -R KEY ~", id="grep_재귀_홈"),
        pytest.param("cat ~/.claude.json # 키를 본다", id="대상_뒤의_꼬리_주석"),
        pytest.param('cat "a\\" # " ~/.claude.json', id="인용_안_이스케이프_뒤의_샵"),
        pytest.param("# it's the key\ncat ~/.claude.json", id="주석_속_따옴표"),
    ],
)
def test_Bash_로_사용자_설정을_출력하면_막는다(명령: str) -> None:
    reason = reason_for("Bash", {"command": 명령}, _windows())

    assert reason is not None
    assert "호출 전체가 돌지 않았다" in reason


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param("Get-Content $HOME\\.claude\\settings.json", id="Get_Content"),
        pytest.param("gc $env:USERPROFILE\\.claude.json -Raw | ConvertFrom-Json", id="gc_별칭"),
        pytest.param("(Get-Content ~\\.claude\\settings.json | ConvertFrom-Json).env", id="괄호"),
        pytest.param('[IO.File]::ReadAllText("$env:USERPROFILE\\.claude.json")', id="IO_File"),
        pytest.param("type C:\\Users\\u\\.claude.json", id="type"),
        pytest.param("Select-String -Path ~\\.claude\\settings.json -Pattern env", id="sls"),
        pytest.param("$s = Get-Content ~\\.claude\\settings.json -Raw", id="변수에_담기"),
        pytest.param('powershell -Command "Get-Content ~\\.claude.json"', id="셸_래퍼"),
        pytest.param('Get-Content -Path "C:\\Users\\u\\.claude.json"', id="인용_경로"),
        pytest.param("Get-Content `#x ~\\.claude.json", id="백틱으로_이스케이프한_샵"),
    ],
)
def test_PowerShell_로_사용자_설정을_출력하면_막는다(명령: str) -> None:
    assert reason_for("PowerShell", {"command": 명령}, _windows()) is not None


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param("jq keys ~/.claude.json", id="jq_키만"),
        pytest.param("jq '.env | keys' ~/.claude/settings.json", id="jq_갈래의_키만"),
        pytest.param("ls -la ~/.claude.json", id="ls"),
        pytest.param("cat .claude/settings.json", id="프로젝트_설정"),
        pytest.param("cp ~/.claude.json ~/.claude.json.bak", id="복사"),
        pytest.param("Test-Path $HOME\\.claude\\settings.json", id="Test_Path"),
        pytest.param("git diff -- .claude/settings.json", id="프로젝트_설정_diff"),
        pytest.param("cat > x.md <<'EOF'\ncat ~/.claude.json\nEOF", id="heredoc_본문"),
        pytest.param("rg KEY src/ tests/", id="저장소_안_재귀_검색"),
        pytest.param("grep KEY ~/.claude", id="재귀_아닌_grep_의_폴더"),
        pytest.param("# cat ~/.claude.json\nls", id="주석_줄"),
    ],
)
def test_키만_보거나_출력하지_않는_명령은_지나간다(명령: str) -> None:
    assert reason_for("Bash", {"command": 명령}, _windows()) is None


def test_못_보는_것_꼬리_주석의_대상_경로는_막는다() -> None:
    """거짓 양성이다. 주석을 뺀 글과 빼지 않은 글을 둘 다 보아, 셸의 이스케이프로 주석이 아닌 자리를
    주석으로 버리지 않는다(PR 직전 보안 리뷰)."""
    command = "sed -n 1p docs/x.md | head # ~/.claude/settings.json"

    assert reason_for("Bash", {"command": command}, _windows()) is not None


def test_모르는_변수의_대상은_홈의_경로로_키_명령을_준다() -> None:
    """펼치지 못한 변수를 키 명령에 넣으면 파이썬은 열지 못하고 PowerShell 은 엉뚱하게 펼친다."""
    reason = reason_for("PowerShell", {"command": "gc $env:FOO\\.claude.json"}, _windows())

    assert reason is not None
    assert "C:/Users/u/.claude.json" in reason
    assert "$env:FOO" not in reason


def test_안내하는_키_명령은_지나가고_파일을_가리킨다() -> None:
    """막을 때 주는 길이 다시 막히면 갈 곳이 없다."""
    place = _windows()
    command = keys_command("C:\\Users\\u\\.claude\\settings.json")

    assert "C:/Users/u/.claude/settings.json" in command
    assert reason_for("Bash", {"command": command}, place) is None
    assert reason_for("PowerShell", {"command": command}, place) is None


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param("python -c \"print(open('/c/Users/u/.claude.json').read())\"", id="언어_안"),
        pytest.param("cp ~/.claude.json x.json && cat x.json", id="복사_뒤_읽기"),
        pytest.param("cd ~ && cat .claude.json", id="cd_뒤_상대_경로"),
        pytest.param("cd ~ && grep -r KEY", id="경로_없는_재귀_검색"),
        pytest.param("p=~/.claude.json; cat $p", id="변수에_담은_경로"),
        pytest.param("echo ~/.claude.json | xargs cat", id="xargs"),
        pytest.param("sudo -u x cat ~/.claude.json", id="옵션이_있는_래퍼"),
        pytest.param("cat ~/.claude\\.json", id="경로_안의_이스케이프"),
        pytest.param("printenv", id="프로세스_환경"),
    ],
)
def test_못_보는_것_언어_안과_복사본과_cd_와_프로세스_환경은_지나간다(명령: str) -> None:
    """거짓 음성이다. 독스트링의 못 보는 것에 적은 길이다."""
    assert reason_for("Bash", {"command": 명령}, _windows()) is None


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param("Get-ChildItem env:", id="프로세스_환경"),
        pytest.param("Get-Content (Join-Path $HOME '.claude.json')", id="Join_Path"),
        pytest.param("Get-Content `\n~\\.claude.json", id="백틱_줄_이어_쓰기"),
    ],
)
def test_못_보는_것_PowerShell_의_프로세스_환경과_조립한_경로와_백틱_줄_이어_쓰기는_지나간다(
    명령: str,
) -> None:
    """거짓 음성이다. 독스트링의 못 보는 것에 적은 길이다."""
    assert reason_for("PowerShell", {"command": 명령}, _windows()) is None


def test_settings의_매처는_훅이_아는_도구_넷이다() -> None:
    """매처를 넓히면 훅이 이름으로 걸러 조용히 지나가고, 좁히면 그 도구의 출력을 놓친다."""
    matchers = registered_matchers("hook_user_settings_read.py", "PreToolUse")

    assert len(matchers) == 1
    assert set(matchers[0].split("|")) == {"Bash", "PowerShell", "Read", "Grep"}
