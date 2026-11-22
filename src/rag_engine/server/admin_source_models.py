"""원천 관리 API의 요청·응답 모델(source-sync 명세 "관리 API"). 경로의 `v1`이 버전이다(원칙 VII).

원천 응답의 칸은 목록과 하나 보기가 같다. 밀어 넣는 원천에서는 가져오는 원천만 쓰는 칸(`connector`,
`config`, `group`, `schedule`, `next_run_at`, `paused`, `exclude_patterns`)이 null이다.
`last_sync`는 동기화 기록이 생기기 전이라 늘 null이다. 시각은 UTC `Z`로 낸다(ADR 0015).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from rag_engine.app.admin_sources import SourceReport
from rag_engine.domain.entities import SourceKind
from rag_engine.server.admin_models import UtcTime
from rag_engine.server.source_name import SourceName


class CreateSourceRequest(BaseModel):
    """`POST /sources`의 본문. 받는 칸은 `name`과 `kind` 둘이므로 그 밖의 칸은 모두 422다."""

    model_config = ConfigDict(extra="forbid")

    name: SourceName
    kind: Literal["push"] = Field(description="원천의 갈래. 밀어 넣는 원천(`push`)만 만든다")


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
    last_sync: None = Field(description="가장 최근 동기화 기록. 동기화 기록이 없으면 null")

    @staticmethod
    def of(report: SourceReport) -> "SourceResponse":
        source = report.source
        return SourceResponse(
            name=source.name,
            kind=source.kind,
            connector=None,
            config=None,
            group=None,
            schedule=None,
            next_run_at=None,
            paused=None,
            exclude_patterns=None,
            created_at=source.created_at,
            deleted_at=source.deleted_at,
            documents=DocumentCountsResponse(
                total=report.documents.total,
                failed=report.documents.failed,
                skipped=report.documents.skipped,
            ),
            last_sync=None,
        )


class SourceListResponse(BaseModel):
    sources: list[SourceResponse]
