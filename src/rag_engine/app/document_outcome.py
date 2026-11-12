"""문서의 색인 결과가 실패인지 가르는 판정(명세 "수집 API"의 `requeued` 조건, "관리 명령"의
`ingest --wait`).

작업의 상태는 문서의 결과가 아니다(수집 파이프라인의 넷째 단계). 문서의 결과는 문서 상태와 살아 있는
판마다의 색인 상태가 원천이고, 수집은 `requeued`를 가르는 데, 관리 명령은 종료 코드를 정하는 데 같은
판정을 쓴다. 관리 API의 작업 조회와 문서 조회는 이 판정을 거치지 않고 같은 원천(문서 상태와 판마다의
색인 상태)을 그대로 낸다.
"""

from rag_engine.app.live_versions import live_index_versions
from rag_engine.domain.entities import Document, DocumentStatus, IndexStateStatus
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.ports import Transaction


async def index_failure_code(transaction: Transaction, document: Document) -> ErrorCode | None:
    """색인이 실패했으면 그 까닭의 오류 코드를, 아니면 `None`을 낸다.

    문서 상태가 `failed`이거나, 문서가 드는 지식베이스의 살아 있는 판 가운데 색인 상태가 `failed`인
    판이 있으면 실패다. 오류 코드가 적히지 않은 실패는 `internal_error`로 낸다.
    """
    if document.status is DocumentStatus.FAILED:
        return document.error_code or ErrorCode.INTERNAL_ERROR
    for version in await live_index_versions(transaction, document.group_id):
        state = await transaction.index.get_state(document.id, version.id)
        if state is not None and state.status is IndexStateStatus.FAILED:
            return state.error_code or ErrorCode.INTERNAL_ERROR
    return None
