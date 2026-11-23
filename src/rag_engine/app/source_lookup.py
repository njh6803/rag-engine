"""요청이 가리킨 원천을 찾는다(source-sync 명세 "수집 API", "관리 API"). 이름을 주지 않은 요청은
기본 원천 `default`다. 없는 이름은 404 `source_not_found`이고, 이름을 주지 않았는데 `default`가
없으면 `migrate`를 돌리지 않은 설치라 요청의 잘못이 아니다."""

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.domain.entities import Source, SourceKind
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import Transaction


async def require_source(transaction: Transaction, name: str | None) -> Source:
    source = await transaction.catalog.get_source(DEFAULT_NAME if name is None else name)
    if source is not None:
        return source
    if name is None:
        raise RuntimeError("기본 원천이 없다. migrate를 돌려야 한다")
    raise RequestError(ErrorCode.SOURCE_NOT_FOUND, "그 이름의 원천이 없다")


async def require_push_source(transaction: Transaction, name: str | None) -> Source:
    """수집 API가 가리킨 원천. 가져오는 원천에는 넣거나 지울 수 없어 409 `wrong_source_kind`다."""
    source = await require_source(transaction, name)
    if source.kind is not SourceKind.PUSH:
        raise RequestError(ErrorCode.WRONG_SOURCE_KIND, "밀어 넣는 원천이 아니다")
    return source


async def require_pull_source(transaction: Transaction, name: str) -> Source:
    """관리 API의 고치기, 연결 확인, 일시 중지, 다시 시작이 가리킨 원천. 밀어 넣는 원천이면 409
    `wrong_source_kind`다."""
    source = await require_source(transaction, name)
    if source.kind is not SourceKind.PULL:
        raise RequestError(ErrorCode.WRONG_SOURCE_KIND, "가져오는 원천이 아니다")
    return source
