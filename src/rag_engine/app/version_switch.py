"""전환 검사의 자리(명세 "수집 파이프라인과 작업").

건설 중인 판에서 문서의 색인 상태를 쓰거나 지운 작업 단위가 그 뒤에 부른다. 부르는 곳은 색인
작업(`index_document`)의 색인 상태 쓰기와 파싱 영구 실패, 그룹을 바꾸는 수집(`ingest`)의 색인 상태
지우기, 삭제(`delete_document`)의 색인 상태 지우기다. 같은 내용의 되살림(`ingest._restore_chunks`)은
건설 중인 판에 `indexed`를 써도 부르지 않는다(까닭은 티켓 14의 07이 넘긴 것 항목).
"""

from rag_engine.domain.entities import IndexVersion
from rag_engine.domain.ports import Transaction


async def check_version_switch(transaction: Transaction, version: IndexVersion) -> None:
    """색인 상태를 쓰거나 지운 뒤 그 판이 건설 중이면 하는 전환 검사다. 지식베이스 행을 잠그고
    그 판의 모든 색인 상태가 `indexed`나 `failed`면 판을 전환한다. 14가 채운다."""
