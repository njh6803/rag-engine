"""지금 동기화와 동기화 기록의 요청·응답 모델(source-sync 명세 "관리 API", "동기화 기록"). 경로의
`v1`이 버전이다(원칙 VII).

기록의 `failure_code`는 닫힌 코드만 싣는다. 커넥터 예외의 글, 폴더 이름, 문서의 키와 제목은 어느
칸에도 싣지 않는다(원칙 V). 시각은 UTC `Z`로 낸다(ADR 0015).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from rag_engine.app.sync_requests import SyncRequested
from rag_engine.domain.entities import SyncRecord, SyncRecordStatus, SyncTrigger
from rag_engine.server.admin_models import UtcTime

_OPTIONS = TypeAdapter(dict[str, JsonValue])


class SyncRequest(BaseModel):
    """지금 동기화의 본문. 두 옵션 모두 고르지 않으면 거짓이다. 본문을 통째로 비워도 된다."""

    model_config = ConfigDict(extra="forbid")

    apply_empty: bool = Field(
        default=False, description="빈 목록도 반영한다(문서가 될 파일이 하나도 없어도 삭제를 반영)"
    )
    reread: bool = Field(
        default=False,
        description="모두 다시 읽는다(변경 확인값이 같아도 파일을 읽어 내용을 견준다)",
    )


class SyncRequestedResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sync_record_id: UUID = Field(description="동기화 기록의 식별자")
    job_id: UUID = Field(description="대기열에 넣은 동기화 작업의 식별자")

    @staticmethod
    def of(requested: SyncRequested) -> "SyncRequestedResponse":
        return SyncRequestedResponse(
            sync_record_id=requested.sync_record_id, job_id=requested.job_id
        )


class SyncRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    source: str = Field(description="동기화한 원천의 이름")
    job_id: UUID | None = Field(description="동기화 작업. 작업을 넣지 않은 회차는 null")
    trigger: SyncTrigger = Field(description="시작시킨 것. `schedule`이나 `manual`")
    options: dict[str, JsonValue] = Field(description="켠 옵션(`apply_empty`, `reread`)")
    status: SyncRecordStatus
    failure_code: str | None = Field(description="실패 사유의 닫힌 코드. 실패가 아니면 null")
    created_at: UtcTime
    started_at: UtcTime | None
    finished_at: UtcTime | None
    listed: int | None = Field(description="받은 목록의 건수. 목록을 받지 못했으면 null")
    added: int = Field(description="새 문서로 넣은 파일(되살린 것 포함)")
    updated: int = Field(description="내용이 바뀌어 다시 넣은 파일")
    deleted: int = Field(description="삭제 반영으로 임시 삭제한 문서")
    unchanged: int = Field(description="내용이 그대로인 파일")
    skipped: dict[str, int] = Field(description="건너뜀 문서의 사유별 개수")
    not_accepted: dict[str, int] = Field(description="수집 정책에 걸린 파일의 사유별 개수")
    failed: dict[str, int] = Field(description="실패한 파일이나 문서의 오류 코드별 개수")

    @staticmethod
    def of(record: SyncRecord, source: str) -> "SyncRecordResponse":
        return SyncRecordResponse(
            id=record.id,
            source=source,
            job_id=record.job_id,
            trigger=record.trigger,
            options=_OPTIONS.validate_python(record.options),
            status=record.status,
            failure_code=record.failure_code,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            listed=record.listed,
            added=record.added,
            updated=record.updated,
            deleted=record.deleted,
            unchanged=record.unchanged,
            skipped=dict(record.skipped),
            not_accepted=dict(record.not_accepted),
            failed=dict(record.failed),
        )


class SyncRecordListResponse(BaseModel):
    sync_records: list[SyncRecordResponse]
