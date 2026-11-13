"""평가 세트 묶음의 경로 판정(명세 "평가 세트의 형식"의 `validate`가 보는 것, 티켓 search-eval 02).

도구가 묶음에서 여는 파일은 읽을 때나 쓸 때나 이 판정 한 자리를 지난다(머리가 가리키는 파일,
`config.json`, `records/`와 그 안의 기록 파일, `judgments.jsonl`, `miss-review.jsonl`, 기준 보고서).
읽는 파일만 판정하면 묶음에 든 링크 하나가 쓰기를 묶음 밖의 파일로 보내는 길이 남기 때문이다. 판정은
셋이다. 절대 경로(운영체제 둘의 꼴과 드라이브 문자와 `\\`로 시작하는 꼴 모두)와 `..`가 들거나 정규
꼴(`a/./b`, 끝의 `/`, 빈 마디)이 아니거나 마디에 `:`(대체 데이터 스트림)나 윈도 예약 장치 이름
(`CON`, `NUL`, `COM1`과 확장자가 붙은 꼴)이 든 경로는 파일을 열기 전에 글자만 보고 거부한다.
장치 이름은 운영체제와 무관하게 거부한다. 윈도에서 열면 읽기가 돌아오지 않거나 장치로 가기 때문이다.
통과한 경로는 링크를 푼 결과가 기준 폴더 안인지 본다. 폴더가 링크인 경우도 같다. 안을 가리키는
링크는 같은 묶음 안의 파일을 가리킬 뿐이라 받는다.

선례는 `ingest` 명령이 폴더 밖을 가리키는 링크를 거르는 것(`ingest_command._collect`)과
`LocalBlobStore` 가 키를 푼 경로가 데이터 폴더 밖이면 읽지도 쓰지도 않는 것이다. 그 둘은 둘째
판정(푼 결과)만 한다.

못 보는 것. 판정한 뒤 파일을 열기까지 사이에 링크가 바뀌는 경쟁(검사한 시각과 쓴 시각의 틈)은 막지
않는다. 하드 링크는 묶음 안의 이름과 밖의 파일이 같은 파일이라 판정이 가르지 못한다. 보고서를 쓰는
폴더와 `--config`로 준 구성 파일은 부르는 사람이 인자로 고른 자리라 이 판정의 대상이 아니다.
파일 아닌 것(폴더, POSIX의 FIFO)은 경로 판정이 아니라 읽는 쪽이 연 파일인지 보고 거른다.
"""

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final

_RESERVED_DEVICE_NAMES: Final = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{n}" for n in range(1, 10)),
        *(f"LPT{n}" for n in range(1, 10)),
    }
)


class BundlePathError(ValueError):
    """경로가 묶음 밖을 가리키거나 정규 꼴이 아니다. 메시지는 까닭이고 파일의 내용은 들지 않는다."""


class BundlePaths:
    """묶음 폴더 하나의 경로 판정. `resolve`가 판정을 지난 경로만 낸다."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, relative: str, *, under: str | None = None) -> Path:
        """묶음 폴더(`under`를 주면 그 아래 폴더) 기준의 `relative`를 풀어 낸다.

        파일이 없어도 풀린다(쓸 파일의 경로를 판정할 때다). 거부하면 `BundlePathError`다.
        """
        # `under` 폴더가 링크라서 묶음 밖이면 여기서 거부한다.
        base = self._root if under is None else self.resolve(under)
        _check_text(relative)
        resolved = (base / relative).resolve()
        if not resolved.is_relative_to(base):
            scope = "묶음 폴더" if under is None else f"{under}/"
            raise BundlePathError(f"{relative}은(는) 링크를 풀면 {scope} 밖을 가리킨다")
        return resolved


def _check_text(relative: str) -> None:
    """글자만 보고 거부한다. 파일 시스템을 열지 않는다."""
    if not relative:
        raise BundlePathError("경로가 비었다")
    if "\0" in relative:
        raise BundlePathError("경로에 널 문자가 들었다")
    if PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).anchor:
        raise BundlePathError(f"{relative}은(는) 절대 경로다. 묶음 폴더 기준 상대 경로로 적는다")
    if "\\" in relative:
        raise BundlePathError(f"{relative}에 역슬래시가 들었다. POSIX 구분자(/)로 적는다")
    parts = relative.split("/")
    if ".." in parts:
        raise BundlePathError(f"{relative}에 ..이 들었다")
    if PurePosixPath(relative).as_posix() != relative:
        raise BundlePathError(f"{relative}은(는) 정규 꼴의 경로가 아니다(./, 빈 마디, 끝의 /)")
    for part in parts:
        if ":" in part:
            raise BundlePathError(f"{relative}의 마디 {part}에 ':'가 들었다")
        if part.split(".")[0].rstrip(" ").upper() in _RESERVED_DEVICE_NAMES:
            raise BundlePathError(f"{relative}의 마디 {part}은(는) 윈도 예약 장치 이름이다")
