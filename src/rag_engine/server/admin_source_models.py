"""원천 관리 API의 요청·응답 모델(source-sync 명세 "관리 API"). 경로의 `v1`이 버전이다(원칙 VII).

원천 응답의 칸은 목록과 하나 보기가 같다. 밀어 넣는 원천에서는 가져오는 원천만 쓰는 칸(`connector`,
`config`, `group`, `schedule`, `next_run_at`, `paused`, `exclude_patterns`)이 null이다.
`last_sync`는 가장 최근 동기화 기록이고 기록이 없으면 null이다. 시각은 UTC `Z`로 낸다(ADR 0015).
"""

from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator

from rag_engine.app.admin_sources import SourceReport
from rag_engine.app.delete_source import SourceDeletionRequested
from rag_engine.app.pull_sources import ConnectionCheck, PullRestoration
from rag_engine.app.restore_source import SourceRestorationRequested
from rag_engine.domain.connectors import ConnectionCheckCode
from rag_engine.domain.entities import SourceKind
from rag_engine.server.admin_models import UtcTime
from rag_engine.server.admin_sync_models import SyncRecordResponse
from rag_engine.server.source_name import SourceName

# 제외 패턴의 규칙(명세 "수집 정책"). 원천 하나에 50개, 패턴 하나는 200자까지다.
MAX_EXCLUDE_PATTERNS: Final = 50
MAX_EXCLUDE_PATTERN_LENGTH: Final = 200
_CONFIG: Final = TypeAdapter(dict[str, JsonValue])
_SCHEDULE_DESCRIPTION: Final = (
    "일정. 분, 시, 일, 월, 요일 다섯 칸의 cron 표현식(예: `0 2 * * *`). 시각은 서버 설정의 "
    "시간대(`RAG_SCHEDULE_TIMEZONE`)로 읽는다"
)


def _check_exclude_patterns(patterns: list[str]) -> list[str]:
    if len(patterns) > MAX_EXCLUDE_PATTERNS:
        raise ValueError(f"제외 패턴은 원천 하나에 {MAX_EXCLUDE_PATTERNS}개까지다")
    if any(not pattern or len(pattern) > MAX_EXCLUDE_PATTERN_LENGTH for pattern in patterns):
        raise ValueError(f"제외 패턴 하나는 1자 이상 {MAX_EXCLUDE_PATTERN_LENGTH}자 이하다")
    return patterns


class CreatePushSourceRequest(BaseModel):
    """밀어 넣는 원천을 만드는 본문. 받는 칸은 `name`과 `kind` 둘이므로 그 밖의 칸은 모두 422다."""

    model_config = ConfigDict(extra="forbid")

    name: SourceName
    kind: Literal["push"] = Field(description="원천의 갈래. 밀어 넣는 원천")


class CreatePullSourceRequest(BaseModel):
    """가져오는 원천을 만드는 본문. `schedule`은 다섯 칸 cron 표현식이고 적지 않으면 일정이 없다."""

    model_config = ConfigDict(extra="forbid")

    name: SourceName
    kind: Literal["pull"] = Field(description="원천의 갈래. 가져오는 원천")
    connector: str = Field(min_length=1, description="커넥터 이름. 서버 경로 원천은 `server_path`")
    config: dict[str, JsonValue] = Field(
        description="커넥터 설정(JSON 객체). 비밀 값을 넣지 않는다. 서버 경로 원천은 `folder` 하나"
    )
    group: str | None = Field(
        default=None, description="문서가 드는 그룹 이름. 적지 않으면 기본 그룹"
    )
    exclude_patterns: list[str] = Field(
        default_factory=list, description="이 패턴에 맞는 키는 동기화에서 거른다"
    )
    schedule: str | None = Field(default=None, description=_SCHEDULE_DESCRIPTION)

    @field_validator("exclude_patterns")
    @classmethod
    def _patterns(cls, patterns: list[str]) -> list[str]:
        return _check_exclude_patterns(patterns)


CreateSourceRequest = Annotated[
    CreatePushSourceRequest | CreatePullSourceRequest, Field(discriminator="kind")
]


class UpdateSourceRequest(BaseModel):
    """가져오는 원천을 고치는 본문. 적은 칸만 고친다. 이름, 갈래, 커넥터, 그룹은 받지 않는다.
    `schedule`은 적지 않으면 그대로 두고, `null`로 적으면 일정을 없앤다(`schedule_given`)."""

    model_config = ConfigDict(extra="forbid")

    config: dict[str, JsonValue] | None = Field(
        default=None, description="새 커넥터 설정. 만들 때와 같은 확인을 다시 한다"
    )
    exclude_patterns: list[str] | None = Field(default=None, description="새 제외 패턴 목록")
    schedule: str | None = Field(
        default=None,
        description=_SCHEDULE_DESCRIPTION + " `null`로 적으면 일정을 없앤다. 적지 않으면 그대로다.",
    )

    @property
    def schedule_given(self) -> bool:
        """요청에 `schedule` 칸이 있었는지. 없는 것(그대로 둔다)과 `null`(없앤다)을 가른다."""
        return "schedule" in self.model_fields_set

    @field_validator("exclude_patterns")
    @classmethod
    def _patterns(cls, patterns: list[str] | None) -> list[str] | None:
        return None if patterns is None else _check_exclude_patterns(patterns)


class ConnectionCheckResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool = Field(description="원천을 읽을 수 있으면 참")
    code: ConnectionCheckCode | None = Field(
        description="읽을 수 없을 때의 까닭. 읽을 수 있으면 null"
    )

    @staticmethod
    def of(check: ConnectionCheck) -> "ConnectionCheckResponse":
        return ConnectionCheckResponse(ok=check.ok, code=check.code)


class DocumentCountsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int = Field(description="지워지지 않은 문서 모두")
    failed: int = Field(description="그 가운데 문서 상태가 `failed`인 문서")
    skipped: int = Field(description="그 가운데 문서 상태가 `skipped`인 문서")


class SourceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    kind: SourceKind
    connector: str | None = Field(description="가져오는 원천의 커넥터 이름")
    config: dict[str, JsonValue] | None = Field(description="가져오는 원천의 커넥터 설정")
    group: str | None = Field(description="가져오는 원천의 문서가 드는 그룹 이름")
    schedule: str | None = Field(description="가져오는 원천의 일정 표현식. 일정이 없으면 null")
    next_run_at: UtcTime | None = Field(description="다음 동기화 시각")
    paused: bool | None = Field(description="가져오는 원천의 일시 중지 여부")
    exclude_patterns: list[str] | None = Field(description="가져오는 원천의 제외 패턴")
    created_at: UtcTime
    deleted_at: UtcTime | None = Field(description="지운 원천이 아니면 null")
    documents: DocumentCountsResponse
    last_sync: SyncRecordResponse | None = Field(
        description="가장 최근 동기화 기록. 동기화 기록이 없으면 null"
    )

    @staticmethod
    def of(report: SourceReport) -> "SourceResponse":
        source = report.source
        pulls = source.kind is SourceKind.PULL
        return SourceResponse(
            name=source.name,
            kind=source.kind,
            connector=source.connector,
            config=None if source.config is None else _CONFIG.validate_python(source.config),
            group=report.group,
            schedule=source.schedule,
            next_run_at=source.next_run_at,
            paused=source.paused if pulls else None,
            exclude_patterns=list(source.exclude_patterns) if pulls else None,
            created_at=source.created_at,
            deleted_at=source.deleted_at,
            documents=DocumentCountsResponse(
                total=report.documents.total,
                failed=report.documents.failed,
                skipped=report.documents.skipped,
            ),
            last_sync=(
                None
                if report.last_sync is None
                else SyncRecordResponse.of(report.last_sync, source.name)
            ),
        )


class SourceListResponse(BaseModel):
    sources: list[SourceResponse]


class SourceDeletionResponse(BaseModel):
    """원천 삭제 요청의 응답(202). 문서를 옮기는 일은 뒤에서 이 작업이 한다."""

    model_config = ConfigDict(frozen=True)

    job_id: UUID = Field(description="대기열에 넣은 원천 삭제 작업의 식별자")

    @staticmethod
    def of(requested: SourceDeletionRequested) -> "SourceDeletionResponse":
        return SourceDeletionResponse(job_id=requested.job_id)


class SourceRestorationResponse(BaseModel):
    """원천 되살리기 요청의 응답(202). 문서를 되살리는 일은 뒤에서 이 작업이 한다."""

    model_config = ConfigDict(frozen=True)

    job_id: UUID = Field(description="대기열에 넣은 원천 되살리기 작업의 식별자")
    connection_check: ConnectionCheckResponse | None = Field(
        description="가져오는 원천은 되살린 직후의 연결 확인. 밀어 넣는 원천은 null"
    )

    @staticmethod
    def of_push(requested: SourceRestorationRequested) -> "SourceRestorationResponse":
        return SourceRestorationResponse(job_id=requested.job_id, connection_check=None)

    @staticmethod
    def of_pull(restored: PullRestoration) -> "SourceRestorationResponse":
        return SourceRestorationResponse(
            job_id=restored.job_id, connection_check=ConnectionCheckResponse.of(restored.connection)
        )
