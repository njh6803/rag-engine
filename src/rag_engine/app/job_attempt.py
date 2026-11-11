"""작업 행 조건(명세 "수집 파이프라인과 작업"의 잠금 규칙).

색인 작업이 쓰는 작업 단위는 모두 문서 행을 먼저 잠그고 마지막에 작업 행을 잠가, 작업자 ID와 시도
횟수가 그 시도가 꺼낼 때 쓴 값 그대로인지 본다. 아니면 임대가 끝나 다른 작업자가 그 작업을 가져간
것이라 그 작업 단위를 롤백하고 시도를 버린다. 둘 사이에서 지식베이스 행을 잠그는 작업 단위는 지금
다시 예약하기와 재시도 소진(`job_failure`)이다. 색인 작업 자신의 작업 단위가 잠그는 일은 14가 한다.
"""

from rag_engine.domain.entities import Job
from rag_engine.domain.errors import AttemptLostError
from rag_engine.domain.ports import Transaction


async def hold_attempt(transaction: Transaction, job: Job) -> None:
    if not await transaction.jobs.hold_attempt(job):
        raise AttemptLostError
