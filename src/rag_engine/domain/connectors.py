"""커넥터 인터페이스 1.0.0. 플러그인 자리 하나(ADR 0003, 0012)이고 버전의 규칙은 원칙 VII다.

커넥터는 원천 하나에서 문서의 목록을 읽고 문서를 받아 오는 플러그인이다. 서버가 목록을 색인과 대
봐 더함, 바뀜, 지움을 판정하므로 커넥터는 기억해 두는 것이 없다. 메서드나 칸을 더하면 minor,
지우거나 뜻을 바꾸면 major다. 서버와 작업자는 entry point 그룹 `rag_engine.connectors`에서 커넥터를
로드할 때 `interface_version`의 major가 다르면 거부하고 기록한다.

커넥터를 만드는 쪽이 지킬 약속은 아래와 같다.

- 커넥터를 만드는 함수는 원천의 설정(JSON 객체) 하나를 받는 보통 함수다(비동기 함수가 아니다).
  설정의 모양만 보고 원천에 닿지 않는다. 파일 시스템도 네트워크도 부르지 않는다. 설정이 그 커넥터가
  받는 모양이 아니면 `ConnectorError`를 사유 `invalid_config`로 올린다. 그 밖에 필요한 값(부모 폴더,
  토큰)은 커넥터가 환경 변수나 비밀 파일에서 스스로 읽는다.
- 설정(`config`)에는 비밀 값을 넣지 않는다. 관리 API의 원천 보기가 설정을 그대로 보여 주고, 서버는
  그 안에서 비밀을 가려낼 수 없다.
- `list()`는 항목을 하나씩 내는 비동기 반복이고 `fetch`와 `check()`는 비동기 함수다.
- 키가 `.pdf`, `.docx`, `.hwpx`(대소문자를 가리지 않는다)로 끝나지 않는 항목은 문서가 되지
  않는다. 서버가 수집 정책으로 거르고 동기화 기록에 센다.
- 같은 키를 두 번 내면 서버는 그 동기화를 실패시킨다.
- 커넥터는 `fetch`가 한 번에 내는 바이트의 크기를 스스로 지킨다. 서버가 파일을 읽지 않고 크기
  상한을 적용하도록 `list()`가 크기를 알려 주지만, 서버가 받은 바이트의 크기를 한 번 더 보더라도
  끝까지 읽은 뒤의 일이다.
- 서버는 예외의 사유 값만 쓰고 글은 응답, 동기화 기록, 로그 어디에도 싣지 않는다. 그 밖의 예외는
  서버가 `connector_error`로 옮기고 로그에는 예외의 종류 이름만 남긴다. 그래서 `ConnectorError`는
  사유 말고 글을 받지 않는다.
"""

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final, Protocol

from rag_engine.domain.entities import JsonValue

CONNECTOR_INTERFACE_VERSION: Final = "1.0.0"


class ConnectorFailureReason(StrEnum):
    """`ConnectorError`가 드는 닫힌 사유 값 다섯. 1.0을 낸 뒤에 값을 더하면 1.0을 아는 서버가 모르는
    값을 받으므로 첫 판에 모두 정한다."""

    INVALID_CONFIG = (
        "invalid_config"  # 원천의 설정이 그 커넥터가 받는 모양이 아니다. 만들 때만 난다
    )
    UNREADABLE = "unreadable"  # 원천이나 그 항목을 읽을 수 없다
    REJECTED = "rejected"  # 경로 확인에 걸렸다
    NOT_FOUND = "not_found"  # 그 키의 문서가 없다
    TOO_LARGE = "too_large"  # 받을 수 있는 크기를 넘는다


class ConnectorError(Exception):
    """커넥터 인터페이스가 정하는 예외 하나. 사유 값만 들고, 글은 사유 값 그대로다. 설치처가 만든
    커넥터의 예외 글에는 토큰이나 연결 문자열이 섞일 수 있어 글을 받지 않는다(원칙 V)."""

    def __init__(self, reason: ConnectorFailureReason) -> None:
        # 인자를 사유 그대로 넘겨야 `copy`와 pickle이 같은 인자로 다시 만든다. 글은 사유의 값이다.
        super().__init__(reason)
        self.reason = reason


class ConnectorUnavailableError(Exception):
    """그 이름의 커넥터를 만들 수 없다. 설치되지 않았거나, 인터페이스 버전의 major가 다르거나,
    불러오다 깨졌다. `ConnectorRegistry`가 올리고 `ConnectorError`와 다른 종류다. 뒤의 티켓이 원천을
    만드는 요청의 422와 동기화의 `connector_unavailable`로 옮긴다. 이름은 글에 싣지 않는다. 인자를
    받지 않아 `args`가 비므로 `copy`와 pickle이 같은 예외를 다시 만든다."""

    def __str__(self) -> str:
        return "커넥터를 쓸 수 없다"


@dataclass(frozen=True, slots=True)
class ListedItem:
    """`list()`가 내는 항목. 변경 확인값은 커넥터가 준 문자열 그대로이고 서버가 해석하지 않는다.
    크기(바이트)는 모르면 비운다."""

    key: str
    change_marker: str
    size_bytes: int | None


@dataclass(frozen=True, slots=True)
class FetchedItem:
    """`fetch(key)`의 결과. MIME은 모르면 비우고 서버가 키의 확장자로 가른다. 갱신 시각은 없으면
    비우고 서버가 수집 시각을 쓴다. 메타데이터는 JSON 객체이고 `title`이 문자열이면 문서의
    제목이다."""

    data: bytes
    mime: str | None
    updated_at: datetime | None
    metadata: Mapping[str, JsonValue]


class Connector(Protocol):
    """원천 하나의 열거와 받기. 원천의 설정으로 만들어지고 상태를 들지 않는다.

    `interface_version`은 이 인터페이스의 버전(`CONNECTOR_INTERFACE_VERSION`을 따르는 semver)이다.
    """

    @property
    def interface_version(self) -> str: ...

    def list(self) -> AsyncIterator[ListedItem]:
        """원천 안의 항목을 하나씩 낸다. 읽을 수 없으면 `unreadable`을 올린다."""
        ...

    async def fetch(self, key: str) -> FetchedItem:
        """그 키의 문서를 받는다. 없으면 `not_found`, 크기가 넘으면 `too_large`, 경로 확인에 걸리면
        `rejected`, 읽을 수 없으면 `unreadable`을 올린다."""
        ...

    async def check(self) -> None:
        """원천을 읽을 수 있는지 보고, 안 되면 `ConnectorError`를 올린다."""
        ...


# entry point가 가리키는 것. 원천의 설정을 받아 커넥터를 돌려주는 보통 함수다.
type ConnectorFactory = Callable[[Mapping[str, JsonValue]], Connector]
