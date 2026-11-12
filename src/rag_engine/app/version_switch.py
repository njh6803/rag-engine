"""전환 검사와 판 전환(명세 "수집 파이프라인과 작업").

건설 중인 판에서 문서의 색인 상태를 쓰거나 지운 작업 단위가 그 뒤에 부른다. 부르는 곳은 색인
작업(`index_document`)의 색인 상태 쓰기, 파싱과 임베딩의 영구 실패와 재시도 소진(셋 다
`index_failure.mark_version_failed`를 거친다), 그룹을 바꾸는 수집(`ingest`)의 색인 상태 지우기,
삭제(`delete_document`)의 색인 상태 지우기, 재색인 시작(문서가 하나도 없는 지식베이스)이다. 같은
내용의 되살림(`ingest._restore_chunks`)은 건설 중인 판에 `indexed`를 써도 부르지 않는다. 그 판에
색인 상태가 없던 문서의 `indexed` 한 행은 전환 조건을 새로 채우지 못하고, 되살림은 지식베이스 행을
`FOR SHARE`로 잠그므로 `FOR UPDATE`로 올리다 같은 지식베이스의 되살림끼리 교착할 수 있어서다.
"""

from rag_engine.domain.entities import IndexStateStatus, IndexVersion, IndexVersionStatus
from rag_engine.domain.ports import LockMode, Transaction


async def check_version_switch(transaction: Transaction, version: IndexVersion) -> None:
    """지식베이스 행을 `FOR UPDATE`로 잠그고, 그 판이 아직 건설 중이며 색인 상태가 모두 `indexed`나
    `failed`면(`pending`이 없으면) 같은 작업 단위에서 판을 전환한다. 잠금이 검사부터 전환까지를
    지식베이스마다 직렬화해, 마지막 두 문서를 동시에 끝낸 작업자 둘이 서로를 `pending`으로 보고 둘
    다 전환하지 않는 일이 없다. 부르는 쪽이 들고 있는 `version`은 잠그기 전에 읽은 것일 수 있어,
    잠근 뒤에 판의 상태를 다시 읽는다(그사이 다른 쪽이 전환했으면 아무것도 하지 않는다)."""
    await transaction.catalog.lock_knowledge_bases([version.knowledge_base_id], LockMode.UPDATE)
    locked = await transaction.catalog.get_index_version(version.id)
    if locked is None or locked.status is not IndexVersionStatus.BUILDING:
        return
    counts = await transaction.index.count_states(version.id)
    if counts.get(IndexStateStatus.PENDING, 0) > 0:
        return
    await transaction.catalog.switch_current_version(version.knowledge_base_id, version.id)
