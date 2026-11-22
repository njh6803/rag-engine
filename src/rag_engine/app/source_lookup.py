"""요청이 가리킨 원천을 찾는다(source-sync 명세 "수집 API", "관리 API"). 이름을 주지 않은 요청은
기본 원천 `default`다. 없는 이름은 404 `source_not_found`이고, 이름을 주지 않았는데 `default`가
없으면 `migrate`를 돌리지 않은 설치라 요청의 잘못이 아니다."""

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.domain.entities import Source
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import Transaction


async def require_source(transaction: Transaction, name: str | None) -> Source:
    source = await transaction.catalog.get_source(DEFAULT_NAME if name is None else name)
    if source is not None:
        return source
    if name is None:
        raise RuntimeError("기본 원천이 없다. migrate를 돌려야 한다")
    raise RequestError(ErrorCode.SOURCE_NOT_FOUND, "그 이름의 원천이 없다")
