"""전환 검사의 자리(명세 "수집 파이프라인과 작업").

건설 중인 판에서 문서의 색인 상태를 쓰거나 지운 작업 단위가 그 뒤에 부른다. 부르는 곳은 색인
작업(`index_document`)의 색인 상태 쓰기와 파싱 영구 실패, 그룹을 바꾸는 수집(`ingest`)의 색인 상태
지우기, 삭제(`delete_document`)의 색인 상태 지우기다.
"""

from rag_engine.domain.entities import IndexVersion
from rag_engine.domain.ports import Transaction


async def check_version_switch(transaction: Transaction, version: IndexVersion) -> None:
    """색인 상태를 쓰거나 지운 뒤 그 판이 건설 중이면 하는 전환 검사다. 지식베이스 행을 잠그고
    그 판의 모든 색인 상태가 `indexed`나 `failed`면 판을 전환한다. 14가 채운다."""
