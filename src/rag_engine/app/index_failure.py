"""문서가 한 색인 판에 실패했다고 적는 자리(명세 "수집 파이프라인과 작업").

파싱의 영구 실패, 임베딩의 영구 실패, 재시도 소진이 모두 같은 세 가지를 한다. 그 (문서, 판)의 조각을
지우고(남은 조각은 문서의 지금 내용으로 만든 것이 아니라서 두면 원천에 없는 글을 답의 근거로 낸다.
원칙 VI), 색인 상태를 `failed`와 그 오류 코드로 쓰고, 판이 건설 중이면 전환 검사를 부른다. 부르는
쪽이 문서 행을 잠근 작업 단위 안에서 부르고, 세대 대조는 부르는 쪽이 한다.
"""

from datetime import datetime
from uuid import UUID

from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.entities import (
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
)
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.ports import Transaction


async def mark_version_failed(
    transaction: Transaction,
    document_id: UUID,
    version: IndexVersion,
    code: ErrorCode,
    now: datetime,
) -> None:
    await transaction.index.delete_chunks(document_id, version.id)
    await transaction.index.save_state(
        IndexState(
            document_id=document_id,
            index_version_id=version.id,
            status=IndexStateStatus.FAILED,
            chunk_count=0,
            built_content_hash=None,
            error_code=code,
            updated_at=now,
        )
    )
    if version.status is IndexVersionStatus.BUILDING:
        await check_version_switch(transaction, version)
