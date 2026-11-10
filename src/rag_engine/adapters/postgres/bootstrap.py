"""`migrate`의 조립. 스키마를 올리고 기본 레코드를 보장한다(명세 "관리 명령").

관리 명령과 시험의 세션 픽스처가 같은 길을 쓴다. 이벤트 루프를 스스로 열므로 실행 중인 루프 안에서는
부를 수 없다(`migrate.upgrade_to_head`처럼 스레드로 넘겨 부른다).
"""

from datetime import UTC, datetime

from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.adapters.postgres.engine import create_engine, run_in_selector_loop
from rag_engine.adapters.postgres.migrate import upgrade_to_head
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.app.default_records import DefaultKnowledgeBaseSettings, ensure_default_records


async def _run_default_records_use_case(
    database_url: str, default_knowledge_base: DefaultKnowledgeBaseSettings
) -> None:
    engine = create_engine(database_url)
    try:
        await ensure_default_records(
            PostgresUnitOfWork(engine),
            default_knowledge_base,
            compute_index_elements,
            datetime.now(UTC),
        )
    finally:
        await engine.dispose()


def migrate_database(settings: Settings) -> None:
    # 설정이 모자라면 스키마를 올리기 전에 멈춘다.
    default_knowledge_base = settings.default_knowledge_base()
    upgrade_to_head(settings.database_url)
    run_in_selector_loop(
        _run_default_records_use_case(settings.database_url, default_knowledge_base)
    )
