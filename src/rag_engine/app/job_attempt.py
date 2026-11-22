"""작업 행 조건(명세 "수집 파이프라인과 작업"의 잠금 규칙).

색인 작업이 쓰는 작업 단위는 모두 문서 행을 먼저 잠그고 마지막에 작업 행을 잠가, 작업자 ID와 시도
횟수가 그 시도가 꺼낼 때 쓴 값 그대로인지 본다. 아니면 작업 담당 기록의 기한이 끝나 다른 작업자가 그
작업을 가져간 것이라 그 작업 단위를 롤백하고 시도를 버린다. 둘 사이에서 지식베이스 행을 잠그는 작업
단위는 다시 예약하기와 재시도 소진(`job_failure`), 영구 실패의 마무리(`index_document`의
`_record_permanent_failure`), 건설 중인 판에 조각을 쓰는 색인 작업 자신의 작업 단위다. 문서를
가리키지 않는 동기화 작업이 기록을 쓰는 작업 단위는 문서 행 대신 동기화 기록 행을 먼저 잠그고 작업
행을 마지막에 잠근다. 파일 하나를 처리하는 작업 단위(변경 확인값 갱신, 가져온 문서 넣기)는 기록 행을
잠그지 않고 색인 작업과 같이 문서 행을 먼저 잠근다.
"""

from rag_engine.domain.entities import Job
from rag_engine.domain.errors import AttemptLostError
from rag_engine.domain.ports import Transaction


async def hold_attempt(transaction: Transaction, job: Job) -> None:
    if not await transaction.jobs.hold_attempt(job):
        raise AttemptLostError
