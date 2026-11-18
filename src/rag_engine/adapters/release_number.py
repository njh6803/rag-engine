"""이 서버의 릴리스 번호를 설치된 패키지의 메타데이터(`importlib.metadata`)에서 읽는다.

`rag-engine --version`, 서버가 만드는 API 문서의 판 칸, MCP 초기화 응답의 서버 정보
(`serverInfo.version`)가 모두 이 함수를 거친다. 번호를 코드에 따로 적지 않으므로 세 자리가 어긋날
수 없다. 이미지 안에서는 이미지를 지을 때 넘긴 번호(`APP_VERSION`)이고, 개발 체크아웃에서는
`0.0.0`이다(release-image 명세 "번호가 보이는 자리").
"""

from importlib.metadata import version

_DISTRIBUTION = "rag-engine"


def release_number() -> str:
    return version(_DISTRIBUTION)
