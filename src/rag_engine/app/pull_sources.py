"""가져오는 원천(`pull`)을 만들고 고치고 확인하는 유스케이스(source-sync 명세 "관리 API", "서버 경로
커넥터와 원천 폴더", 스토리 6, 8, 9, 24).

**폴더 확인은 레지스트리 포트가 한다.** 서버 경로 원천의 폴더 찾기, 경로 확인, 읽어 보기는 커넥터
인터페이스 밖에서 서버가 부른다. 커넥터마다 하는 확인이 아니라서 새 포트를 만들지 않고
`ConnectorRegistry`의 메서드로 둔다(포트는 넷이라는 명세와 ADR 0007의 열거를 지킨다). 호출 장치와
10초 한도는 그 구현이 건다.

**겹침 확인과 저장은 한 작업 단위에서 하고, 그 작업 단위가 맨 먼저 자문 잠금을 잡는다.** 폴더를
정하는 요청(만들기, 폴더 고치기)끼리는 이 서비스가 쥔 프로세스 안의 잠금으로 먼저 차례를 세운 뒤에야
데이터베이스 연결을 잡는다. 차례를 기다리는 요청이 연결을 쥐면 풀이 차서 검색이 기다리기 때문이다.
새 폴더의 확인은 이 차례 앞에서 한다. 그 확인에 걸리는 시간은 잠금을 쥔 시간에 들지 않고, 한도를
넘긴 요청은 아무것도 쓰지 않은 채 끝난다. 겹침을 가리려고 다른 원천의 폴더를 살펴보는 확인은 이
차례와 작업 단위 안에서 돈다. 답하지 않는 원천이 있으면 그 한도(10초)만큼 잠금과 연결을 쥔다(명세
"서버 경로 커넥터와 원천 폴더"가 받아들인 비용이다).

오류 글에는 폴더 이름과 커넥터 설정을 싣지 않는다(원칙 V).
"""

import asyncio
import unicodedata
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rag_engine.app.admin_sources import SourceReport, source_report
from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.app.source_lookup import ensure_not_deleted, require_pull_source
from rag_engine.domain.connectors import (
    SERVER_PATH_CONNECTOR,
    ConnectionCheckCode,
    ConnectorBrokenError,
    ConnectorCallBlockedError,
    ConnectorCallTimedOutError,
    ConnectorError,
    ConnectorFailureReason,
    ConnectorUnavailableError,
    FolderLocation,
    FolderTarget,
)
from rag_engine.domain.entities import (
    DocumentCounts,
    JsonValue,
    Source,
    SourceKind,
)
from rag_engine.domain.errors import (
    ErrorCode,
    InvalidInput,
    InvalidScheduleError,
    RequestError,
    SourceAlreadyExistsError,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import (
    Catalog,
    ConnectorRegistry,
    ScheduleCalculator,
    Transaction,
    UnitOfWork,
)

_FOLDER_FAILURE_KINDS = {
    ConnectorFailureReason.INVALID_CONFIG: "invalid_config",
    ConnectorFailureReason.NOT_FOUND: "not_found",
    ConnectorFailureReason.REJECTED: "rejected",
}


@dataclass(frozen=True, slots=True)
class ConnectionCheck:
    """연결 확인의 결과. 읽지 못해도 요청은 성공이고 `ok`가 거짓이며 까닭이 `code`에 든다."""

    ok: bool
    code: ConnectionCheckCode | None


@dataclass(frozen=True, slots=True)
class ScheduleChange:
    """일정을 고치라는 요청. `expression`이 `None`이면 일정을 없앤다. 요청에 일정 칸이 없으면 이
    값 자체를 만들지 않고 `None`을 넘긴다(고치지 않는다)."""

    expression: str | None


def _nfc_segments(folder: str) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part) for part in folder.split("/"))


def _text_overlaps(first: str, second: str) -> bool:
    """저장해 둔 경로의 글자로 견준다. 같거나 한쪽이 다른 쪽의 토막 단위 앞머리면 겹친다."""
    a, b = _nfc_segments(first), _nfc_segments(second)
    shorter = min(len(a), len(b))
    return a[:shorter] == b[:shorter]


def _folder_of(config: Mapping[str, JsonValue] | None) -> str | None:
    folder = None if config is None else config.get("folder")
    return folder if isinstance(folder, str) else None


def _invalid_config() -> InvalidInput:
    return InvalidInput(
        ("config",), "invalid_config", "원천의 설정이 그 커넥터가 받는 모양이 아니다"
    )


def _connector_unavailable() -> InvalidInput:
    return InvalidInput(("connector",), "connector_unavailable", "그 커넥터를 쓸 수 없다")


class PullSources:
    """가져오는 원천의 유스케이스. 폴더를 정하는 요청의 차례를 세우는 잠금을 쥐므로 서버
    프로세스마다 하나만 만들어 쓴다."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        registry: ConnectorRegistry,
        calculator: ScheduleCalculator,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._registry = registry
        self._calculator = calculator
        self._folder_turn = asyncio.Lock()

    async def create(
        self,
        *,
        name: str,
        connector: str,
        config: Mapping[str, JsonValue],
        group: str | None,
        exclude_patterns: Sequence[str],
        schedule: str | None,
        now: datetime,
    ) -> SourceReport:
        """원천을 만든다. 일정을 적었으면 다음 실행 시각을 `now` 다음의 시각으로 채운다."""
        self._check_schedule(schedule)
        self._validate(connector, config)
        location = await self._locate(connector, config)
        stored = _stored_config(config, location)
        try:
            return await self._create_in_turn(
                name, connector, stored, location, group, exclude_patterns, schedule, now
            )
        except SourceAlreadyExistsError:
            raise RequestError(
                ErrorCode.SOURCE_ALREADY_EXISTS, "같은 이름의 원천이 이미 있다"
            ) from None

    async def _create_in_turn(
        self,
        name: str,
        connector: str,
        stored: Mapping[str, JsonValue],
        location: FolderLocation | None,
        group: str | None,
        exclude_patterns: Sequence[str],
        schedule: str | None,
        now: datetime,
    ) -> SourceReport:
        async with self._turn(location), self._unit_of_work.begin() as transaction:
            catalog = transaction.catalog
            if location is not None:
                await catalog.lock_source_folders()
            found = await catalog.get_group(DEFAULT_NAME if group is None else group)
            if found is None:
                raise RequestError(ErrorCode.GROUP_NOT_FOUND, "그 이름의 그룹이 없다")
            if await catalog.get_source(name) is not None:
                raise SourceAlreadyExistsError
            if location is not None:
                await self._reject_overlap(catalog, stored, location, own=None)
            source = Source(
                new_id(),
                name,
                SourceKind.PULL,
                now,
                connector=connector,
                config=stored,
                group_id=found.id,
                exclude_patterns=tuple(exclude_patterns),
                schedule=schedule,
                next_run_at=self._next_due(schedule, now),
            )
            await catalog.create_source(source)
            return SourceReport(source, DocumentCounts(total=0, failed=0, skipped=0), found.name)

    async def update(
        self,
        name: str,
        *,
        config: Mapping[str, JsonValue] | None,
        exclude_patterns: Sequence[str] | None,
        schedule: ScheduleChange | None,
        now: datetime,
    ) -> SourceReport:
        """적은 칸만 고친다. 설정을 고치면 만들 때와 같은 확인을 다시 한다. `schedule`을 주면 일정을
        바꾸고(`expression`이 없으면 없애고), 다음 실행 시각을 `now` 다음의 시각으로 다시 계산한다.
        일시 중지한 원천은 시각이 빈 채로 둔다."""
        async with self._unit_of_work.begin() as transaction:
            current = await require_pull_source(transaction, name)
        if schedule is not None:
            self._check_schedule(schedule.expression)
        connector = current.connector
        if connector is None:
            raise RuntimeError("가져오는 원천에 커넥터가 없다")
        location: FolderLocation | None = None
        stored: Mapping[str, JsonValue] | None = None
        if config is not None:
            self._validate(connector, config)
            location = await self._locate(connector, config)
            stored = _stored_config(config, location)
        async with self._turn(location):
            async with self._unit_of_work.begin() as transaction:
                catalog = transaction.catalog
                if location is not None:
                    await catalog.lock_source_folders()
                latest = await require_pull_source(transaction, name)
                # 원천을 지우는 요청과 겹치면 잠금을 기다린 뒤 지움 표시를 다시 본다.
                ensure_not_deleted(await catalog.lock_source(latest.id) or latest)
                if location is not None and stored is not None:
                    await self._reject_overlap(catalog, stored, location, own=latest.id)
                await catalog.update_pull_source(
                    latest.id, config=stored, exclude_patterns=exclude_patterns
                )
                if schedule is not None:
                    await self._change_schedule(catalog, latest, schedule, now)
                return await _report_after_write(transaction, name)

    async def set_paused(self, name: str, *, paused: bool, now: datetime) -> SourceReport:
        """일시 중지 칸을 바꾼다. 이미 그 상태여도 그대로 답한다. 일시 중지하면 다음 실행 시각을
        비우고, 일시 중지에서 다시 시작하면 `now` 다음의 시각으로 채운다. 이미 돌고 있던 원천을 다시
        시작하는 요청은 시각을 건드리지 않는다. 시각이 이미 지나 있는 원천의 시작이 미뤄지기
        때문이다."""
        async with self._unit_of_work.begin() as transaction:
            catalog = transaction.catalog
            current = await require_pull_source(transaction, name)
            locked = await catalog.lock_source(current.id) or current
            ensure_not_deleted(locked)
            await catalog.set_source_paused(current.id, paused=paused)
            if paused:
                await catalog.set_next_run_at(current.id, None)
            elif locked.paused:
                await catalog.set_next_run_at(current.id, self._next_due(locked.schedule, now))
            return await _report_after_write(transaction, name)

    async def _change_schedule(
        self, catalog: Catalog, source: Source, change: ScheduleChange, now: datetime
    ) -> None:
        """일정과 다음 실행 시각을 한 번에 쓴다. 원천 행을 잠가, 같은 원천의 일정 확인이나 다른
        요청이 커밋한 일시 중지 칸을 읽은 값으로 되돌리지 않게 한다."""
        locked = await catalog.lock_source(source.id) or source
        await catalog.set_source_schedule(source.id, change.expression)
        due = self._next_due(change.expression, now, paused=locked.paused)
        await catalog.set_next_run_at(source.id, due)

    def _next_due(
        self, expression: str | None, now: datetime, *, paused: bool = False
    ) -> datetime | None:
        """다음 실행 시각. 일정이 없거나 일시 중지한 원천은 비고, 아니면 `now` 다음의 시각이다."""
        if expression is None or paused:
            return None
        return self._calculator.next_run(expression, now)

    def _check_schedule(self, expression: str | None) -> None:
        """일정 표현식을 저장하기 전에 확인한다. 받지 않으면 422 `validation_error`(종류는
        `invalid_schedule`)다. 글은 이 저장소가 쓴 것이고 라이브러리의 예외 글은 싣지 않는다."""
        if expression is None:
            return
        failure: InvalidInput | None = None
        try:
            self._calculator.validate(expression)
        except InvalidScheduleError as error:
            failure = InvalidInput(("schedule",), "invalid_schedule", str(error))
        if failure is not None:
            raise failure

    async def check(self, name: str) -> ConnectionCheck:
        """저장해 둔 설정으로 커넥터의 `check()`를 요청 안에서 부른다. 원천을 읽지 못해도 오류가
        아니라 결과로 답한다."""
        async with self._unit_of_work.begin() as transaction:
            source = await require_pull_source(transaction, name)
        if source.connector is None or source.config is None:
            raise RuntimeError("가져오는 원천에 커넥터나 설정이 없다")
        code = await self._check_code(source.connector, source.config, name)
        return ConnectionCheck(ok=code is None, code=code)

    async def _check_code(
        self, connector: str, config: Mapping[str, JsonValue], source: str
    ) -> ConnectionCheckCode | None:
        failure = ConnectionCheckCode.CONNECTOR_ERROR
        try:
            await self._registry.check_connection(connector, config, source)
        except ConnectorUnavailableError:
            failure = ConnectionCheckCode.CONNECTOR_UNAVAILABLE
        except ConnectorError as error:
            failure = _check_failure(error.reason)
        except (ConnectorCallTimedOutError, ConnectorCallBlockedError):
            failure = ConnectionCheckCode.SOURCE_UNREADABLE
        except ConnectorBrokenError:
            failure = ConnectionCheckCode.CONNECTOR_ERROR
        else:
            return None
        return failure

    def _validate(self, connector: str, config: Mapping[str, JsonValue]) -> None:
        """커넥터를 만들어 본다. 설치되지 않았거나 인터페이스가 맞지 않으면 `connector`가, 설정이
        틀리면 `config`가 422다."""
        failure: InvalidInput | None = None
        try:
            self._registry.create(connector, config)
        except ConnectorUnavailableError:
            failure = _connector_unavailable()
        except ConnectorError:
            failure = _invalid_config()
        if failure is not None:
            raise failure

    async def _locate(
        self, connector: str, config: Mapping[str, JsonValue]
    ) -> FolderLocation | None:
        """서버 경로 커넥터면 폴더를 찾고 확인한다. 다른 커넥터는 폴더 확인이 없다."""
        if connector != SERVER_PATH_CONNECTOR:
            return None
        failure: InvalidInput | None = None
        try:
            return await self._registry.locate_folder(connector, config)
        except ConnectorUnavailableError:
            failure = _connector_unavailable()
        except ConnectorError as error:
            kind = _FOLDER_FAILURE_KINDS.get(error.reason, "unreadable")
            failure = InvalidInput(("config",), kind, "원천의 폴더를 쓸 수 없다")
        raise failure

    def _turn(self, location: FolderLocation | None) -> AbstractAsyncContextManager[object]:
        """폴더를 정하는 요청이면 프로세스 안의 잠금으로 차례를 세운다."""
        if location is None:
            return nullcontext()
        return self._folder_turn

    async def _reject_overlap(
        self,
        catalog: Catalog,
        folder_config: Mapping[str, JsonValue],
        location: FolderLocation,
        *,
        own: UUID | None,
    ) -> None:
        """다른 원천의 폴더와 같거나 그 안에 있거나 그것을 품으면 409다. 실제 폴더로 가르고, 폴더가
        지금 없거나 답하지 않는 원천과는 저장해 둔 경로의 글자로 견준다."""
        folder = _folder_of(folder_config)
        others = [
            source
            for source in await catalog.list_sources()
            if source.kind is SourceKind.PULL
            and source.deleted_at is None
            and source.connector == SERVER_PATH_CONNECTOR
            and source.config is not None
            and source.id != own
        ]
        targets = [
            FolderTarget(source.name, SERVER_PATH_CONNECTOR, source.config)
            for source in others
            if source.config is not None
        ]
        found = await self._registry.survey_folders(targets)
        for other, other_location in zip(others, found, strict=True):
            other_folder = _folder_of(other.config)
            if other_location is not None:
                overlaps = (
                    location.final in other_location.chain or other_location.final in location.chain
                )
            else:
                overlaps = (
                    folder is not None
                    and other_folder is not None
                    and _text_overlaps(folder, other_folder)
                )
            if overlaps:
                raise RequestError(ErrorCode.SOURCE_FOLDER_OVERLAP, "다른 원천의 폴더와 겹친다")


async def _report_after_write(transaction: Transaction, name: str) -> SourceReport:
    """칸 단위로 쓴 뒤 원천을 다시 읽어 답한다. 읽어 둔 값에 고친 칸만 덧입히면, 같은 원천을
    동시에 바꾼 다른 요청이 커밋한 칸이 응답에서 옛 값으로 보인다."""
    return await source_report(transaction, await require_pull_source(transaction, name))


def _stored_config(
    config: Mapping[str, JsonValue], location: FolderLocation | None
) -> Mapping[str, JsonValue]:
    """저장할 설정. 서버 경로 원천은 폴더를 폴더 확인이 낸 저장 경로(NFC로 맞춰 찾은 토막은 디스크의
    이름)로 바꿔 저장한다."""
    if location is None:
        return config
    return {**config, "folder": location.folder}


def _check_failure(reason: ConnectorFailureReason) -> ConnectionCheckCode:
    if reason is ConnectorFailureReason.UNREADABLE:
        return ConnectionCheckCode.SOURCE_UNREADABLE
    if reason is ConnectorFailureReason.REJECTED:
        return ConnectionCheckCode.SOURCE_PATH_REJECTED
    if reason is ConnectorFailureReason.INVALID_CONFIG:
        # 저장해 둔 설정을 만드는 함수가 받지 않는다. 그 커넥터를 쓸 수 없는 것으로 다룬다.
        return ConnectionCheckCode.CONNECTOR_UNAVAILABLE
    return ConnectionCheckCode.CONNECTOR_ERROR
