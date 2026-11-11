"""설정 객체는 명세 "설정" 절의 `RAG_*` 를 모두 읽는다(ADR 0015).

환경 변수는 시험마다 `monkeypatch` 로 두고, `.env` 는 읽지 않는다(`_env_file=None`).
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_engine.adapters.settings import Settings
from rag_engine.domain.errors import ConfigurationError

REQUIRED = {
    "RAG_DATABASE_URL": "postgresql://u:p@db:5432/rag",
    "RAG_DATA_DIR": "/data",
    "RAG_ALLOWED_HOSTS": "rag.example.org",
}

# (환경 변수, 값, 칸 이름, 읽은 값). 기본값과 다른 값을 줘서 읽었는지 가린다.
OPTIONAL_SETTINGS = [
    ("RAG_LOG_FORMAT", "text", "log_format", "text"),
    ("RAG_DELETED_RETENTION_DAYS", "7", "deleted_retention_days", 7),
    ("RAG_MCP_STATELESS", "false", "mcp_stateless", False),
    ("RAG_MCP_JSON_RESPONSE", "true", "mcp_json_response", True),
    ("RAG_DEFAULT_EMBEDDING_URL", "http://emb:80", "default_embedding_url", "http://emb:80"),
    ("RAG_DEFAULT_EMBEDDING_MODEL", "org/model", "default_embedding_model", "org/model"),
    ("RAG_DEFAULT_EMBEDDING_DIMENSIONS", "768", "default_embedding_dimensions", 768),
    ("RAG_DEFAULT_RERANKER_URL", "http://rr:80", "default_reranker_url", "http://rr:80"),
    ("RAG_DEFAULT_RERANKER_MODEL", "org/rr", "default_reranker_model", "org/rr"),
    ("RAG_DEFAULT_CHUNKING_STRATEGY", "other", "default_chunking_strategy", "other"),
    ("RAG_DEFAULT_CHUNK_TOKENS", "256", "default_chunk_tokens", 256),
    ("RAG_DEFAULT_CHUNK_OVERLAP_TOKENS", "32", "default_chunk_overlap_tokens", 32),
    ("RAG_MAX_UPLOAD_MB", "10", "max_upload_mb", 10),
    ("RAG_WORKER_CONCURRENCY", "4", "worker_concurrency", 4),
    ("RAG_WORKER_POLL_SECONDS", "9", "worker_poll_seconds", 9),
    ("RAG_JOB_LEASE_SECONDS", "60", "job_lease_seconds", 60),
    ("RAG_JOB_MAX_ATTEMPTS", "3", "job_max_attempts", 3),
    ("RAG_JOB_BACKOFF_BASE_SECONDS", "0.5", "job_backoff_base_seconds", 0.5),
    ("RAG_TEI_BATCH_SIZE", "8", "tei_batch_size", 8),
    ("RAG_TEI_TIMEOUT_SECONDS", "15", "tei_timeout_seconds", 15),
    ("RAG_PARSE_TIMEOUT_SECONDS", "30", "parse_timeout_seconds", 30),
    ("RAG_PARSE_MEMORY_MB", "256", "parse_memory_mb", 256),
    ("RAG_PARSE_MAX_PAGES", "50", "parse_max_pages", 50),
    ("RAG_PARSE_MAX_UNZIPPED_MB", "64", "parse_max_unzipped_mb", 64),
    ("RAG_PARSE_MAX_COMPRESSION_RATIO", "20", "parse_max_compression_ratio", 20),
    ("RAG_PARSE_MAX_TEXT_MB", "8", "parse_max_text_mb", 8),
    ("RAG_SEARCH_CANDIDATES", "30", "search_candidates", 30),
    ("RAG_SEARCH_DEFAULT_TOP_K", "5", "search_default_top_k", 5),
    ("RAG_SEARCH_MAX_TOP_K", "20", "search_max_top_k", 20),
    ("RAG_SEARCH_TIMEOUT_SECONDS", "10", "search_timeout_seconds", 10),
    ("RAG_DOCUMENT_TEXT_MAX_CHARS", "5000", "document_text_max_chars", 5000),
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [*REQUIRED, *(entry[0] for entry in OPTIONAL_SETTINGS)]:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)


def test_필수_셋만_주면_나머지는_명세의_기본값이다(required_environment: None) -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://u:p@db:5432/rag"
    assert settings.data_dir == Path("/data")
    assert settings.allowed_hosts == ["rag.example.org"]
    assert settings.log_format == "json"
    assert settings.deleted_retention_days == 30
    assert settings.mcp_stateless is True
    assert settings.mcp_json_response is False
    assert settings.default_embedding_url is None
    assert settings.default_embedding_model == "BAAI/bge-m3"
    assert settings.default_embedding_dimensions == 1024
    assert settings.default_reranker_model == "BAAI/bge-reranker-v2-m3"
    assert settings.default_chunking_strategy == "structure_first"
    assert (settings.default_chunk_tokens, settings.default_chunk_overlap_tokens) == (512, 64)
    assert settings.max_upload_mb == 100
    assert settings.worker_concurrency == 2
    assert settings.worker_poll_seconds == 5
    assert settings.job_lease_seconds == 600
    assert settings.job_max_attempts == 6
    assert settings.job_backoff_base_seconds == 30
    assert settings.tei_batch_size == 32
    assert settings.tei_timeout_seconds == 60
    assert settings.parse_timeout_seconds == 300
    assert settings.parse_memory_mb == 2048
    assert settings.parse_max_pages == 1000
    assert settings.parse_max_unzipped_mb == 512
    assert settings.parse_max_compression_ratio == 100
    assert settings.parse_max_text_mb == 64
    assert settings.search_candidates == 50
    assert settings.search_default_top_k == 10
    assert settings.search_max_top_k == 50
    assert settings.search_timeout_seconds == 20
    assert settings.document_text_max_chars == 20000


@pytest.mark.parametrize(
    ("variable", "value", "field", "expected"),
    OPTIONAL_SETTINGS,
    ids=[entry[0] for entry in OPTIONAL_SETTINGS],
)
def test_환경_변수_RAG_는_해당_칸으로_읽힌다(
    required_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
    field: str,
    expected: object,
) -> None:
    monkeypatch.setenv(variable, value)

    settings = Settings(_env_file=None)

    assert getattr(settings, field) == expected


@pytest.mark.parametrize("missing", sorted(REQUIRED))
def test_필수_설정이_하나라도_없으면_시작하지_않는다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)

    assert [error["loc"] for error in caught.value.errors()] == [
        (missing.removeprefix("RAG_").lower(),)
    ]


def test_허용_호스트가_비어_있으면_시작하지_않는다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_ALLOWED_HOSTS", " , ")

    with pytest.raises(ValidationError, match="RAG_ALLOWED_HOSTS"):
        Settings(_env_file=None)


def test_허용_호스트는_쉼표로_여럿을_준다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_ALLOWED_HOSTS", "rag.example.org, internal:8000")

    assert Settings(_env_file=None).allowed_hosts == ["rag.example.org", "internal:8000"]


def test_작업_재시도_백오프의_바탕은_실수를_받는다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_JOB_BACKOFF_BASE_SECONDS", "0.01")

    assert Settings(_env_file=None).job_backoff_base_seconds == 0.01


def test_리랭커_끝점을_비우면_리랭커가_없다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_DEFAULT_RERANKER_URL", "")

    assert Settings(_env_file=None).default_reranker_url is None


def test_모르는_로그_형식은_거부한다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_LOG_FORMAT", "xml")

    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)

    assert [(error["loc"], error["type"]) for error in caught.value.errors()] == [
        (("log_format",), "literal_error")
    ]


def test_임베딩_끝점이_없으면_기본_지식베이스를_만들_설정이_모자라다(
    required_environment: None,
) -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ConfigurationError, match="RAG_DEFAULT_EMBEDDING_URL"):
        settings.default_knowledge_base()


def test_기본_지식베이스의_설정을_묶어_낸다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_DEFAULT_EMBEDDING_URL", "http://emb:80")
    monkeypatch.setenv("RAG_DEFAULT_RERANKER_URL", "")

    default = Settings(_env_file=None).default_knowledge_base()

    assert default.embedding_url == "http://emb:80"
    assert default.embedding_model == "BAAI/bge-m3"
    assert default.embedding_dimensions == 1024
    assert (default.reranker_url, default.reranker_model) == (None, None)
    assert (default.chunking.strategy, default.chunking.max_tokens) == ("structure_first", 512)
    assert default.chunking.overlap_tokens == 64


def test_후보_수는_pgvector가_받는_ef_search_상한까지만_받는다(
    required_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_SEARCH_CANDIDATES", "1000")
    accepted = Settings(_env_file=None).search_candidates
    monkeypatch.setenv("RAG_SEARCH_CANDIDATES", "1001")

    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)

    assert accepted == 1000
    assert [error["loc"] for error in caught.value.errors()] == [("search_candidates",)]
