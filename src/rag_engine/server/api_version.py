"""수집 API와 관리 API의 경로에 든 판(`/api/v1/...`의 `v1`). 라우터의 접두사와
`rag-engine --version`이 이 한 값을 읽는다. 판을 올릴 때 한쪽이 남지 않게
하려는 것이다(원칙 VII)."""

from typing import Final

API_VERSION: Final = "v1"
