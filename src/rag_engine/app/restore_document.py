"""문서 복구의 유스케이스(source-sync 명세 "문서 되살리기", 티켓 13).

밀어 넣는 원천의 지운 문서 하나를 작업 단위 하나에서 복구한다. 그룹, 제목, 메타데이터, 원본은 문서
행의 것 그대로이고, 조각을 되돌리는 단계는 수집 API의 같은 키 복구와 같다(`restore_chunks`).
원천과 함께 지워졌다는 표시가 남아 있던 문서면 그 표시도 지운다.

잠금 순서는 원천 행(공유), 문서 행, 지식베이스 행, 작업 행이다. 거절은 넷이다. 없는 문서와 삭제
기록(보관 기간이 지나 내용을 지운 문서)은 `document_not_found`, 지워지지 않은 문서는
`document_not_deleted`, 가져오는 원천의 문서는 `wrong_source_kind`, 지운 원천의 문서는
`source_deleted`다. 둘 이상에 걸리면 이 순서로 찾아 먼저 걸린 쪽을 낸다(없는 문서, 지운 원천,
가져오는 원천, 지워지지 않은 문서). 명세는 순서를 정하지 않았다. 원천 복구와 달리 보관 기간이
지났는지는 보지 않는다. 명세는 정리 작업(티켓 14)이 문서 행을 잠근 작업 단위에서 문서를 지우도록
정한다(50건씩 묶는다). 그러면 문서 하나를 지우는 도중에 끼어들 틈이 없고, 둘이 겹치면 먼저 잠근
쪽대로 정해진다. 이 문서 행 잠금과 `deleted_at`, `purged_at` 재확인이 그 약속의 이쪽 절반이다. 문서
행이나 원천 행이 이미 사라진 뒤에 만나는 경우(정리 작업이 원천과 그 문서를 지우는 사이에 끼어든
요청)는 원천 행을 잠그는 자리에서 사라진 원천을 보고 `document_not_found`로 끝낸다. 문서 행을
잠글 때 사라진 것을 만나는 경우는 원천 행 잠금이 막는다(정리 작업은 원천 행을 잠근 채 문서를
지운다).
"""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from rag_engine.app.restore_chunks import restore_chunks
from rag_engine.app.source_lookup import ensure_not_deleted
from rag_engine.domain.entities import SourceKind
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import UnitOfWork


@dataclass(frozen=True, slots=True)
class DocumentRestored:
    """복구한 문서의 식별자와, 되돌릴 조각이 없는 판이 있어 넣은 색인 작업의 식별자(없으면
    `None`)."""

    document_id: UUID
    job_id: UUID | None


async def restore_document(
    unit_of_work: UnitOfWork, document_id: UUID, *, request_id: UUID, now: datetime
) -> DocumentRestored:
    async with unit_of_work.begin() as transaction:
        found = await transaction.documents.get(document_id)
        if found is None or found.purged_at is not None:
            raise RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "문서를 찾을 수 없다")
        source = await transaction.catalog.lock_source_shared(found.source_id)
        if source is None:
            # 문서를 읽은 뒤 잠그기 전에 정리 작업이 원천과 그 문서를 함께 지웠다.
            raise RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "문서를 찾을 수 없다")
        ensure_not_deleted(source)
        if source.kind is not SourceKind.PUSH:
            raise RequestError(ErrorCode.WRONG_SOURCE_KIND, "밀어 넣는 원천의 문서가 아니다")
        document = await transaction.documents.lock(found.id)
        if document is None:
            raise RuntimeError("문서 행이 잠그는 사이에 사라졌다")
        if document.purged_at is not None:
            raise RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "문서를 찾을 수 없다")
        if document.deleted_at is None:
            raise RequestError(ErrorCode.DOCUMENT_NOT_DELETED, "지워지지 않은 문서다")
        revived = replace(
            document,
            deleted_at=None,
            deleted_with_source=False,
            generation=document.generation + 1,
            modified_at=now,
        )
        job_id = await restore_chunks(transaction, revived, request_id, now)
        return DocumentRestored(document.id, job_id)
