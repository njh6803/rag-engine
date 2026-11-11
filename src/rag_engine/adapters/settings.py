"""설정 객체. 환경 변수 `RAG_*`, `.env`, 비밀 파일에서 읽는다(ADR 0015, 명세 "설정").

바깥 환경을 읽는 일이라 `adapters`에 둔다. `app`과 `domain`은 이 모듈을 import하지 않고, 기본
지식베이스의 설정만 값 객체(`default_knowledge_base`)로 넘겨받는다.

필수는 `RAG_DATABASE_URL`, `RAG_DATA_DIR`, `RAG_ALLOWED_HOSTS` 셋이고 없으면 시작하지 않는다.
검증 오류의 메시지는 입력 값을 싣는다(연결 문자열의 비밀번호가 들 수 있다). 그래서 `load_settings`가
오류를 `ConfigurationError`로 바꿔 값이 아니라 칸 이름과 오류 종류만 싣고, `rag_engine.main`은 그
메시지만 찍는다.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from rag_engine.app.default_records import DefaultKnowledgeBaseSettings
from rag_engine.domain.entities import ChunkingConfig
from rag_engine.domain.errors import ConfigurationError

# 도커의 비밀 파일 자리. 없는 폴더를 가리키면 pydantic-settings가 경고를 내므로 있을 때만 쓴다.
_SECRETS_DIR: Final = Path("/run/secrets")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        secrets_dir=_SECRETS_DIR if _SECRETS_DIR.is_dir() else None,
        extra="ignore",
    )

    if TYPE_CHECKING:
        # pydantic가 필드에서 지어 내는 생성자 시그니처는 필수 칸을 인자로 요구하고 `_env_file` 같은
        # 설정 읽기 인자를 모른다. 필수 칸은 환경에서 읽으므로 타입 검사에는 키워드 인자만 받는다고
        # 알린다. 실행에는 `BaseSettings.__init__`이 쓰인다.
        def __init__(self, **values: object) -> None: ...

    database_url: str
    data_dir: Path
    # 쉼표로 여럿을 준다. 기본의 JSON 해석을 끈다(`NoDecode`).
    allowed_hosts: Annotated[list[str], NoDecode]

    log_format: Literal["json", "text"] = "json"
    deleted_retention_days: int = Field(default=30, gt=0)
    mcp_stateless: bool = True
    mcp_json_response: bool = False

    # 명세가 기본값을 정하지 않았다. 필수 셋에도 들지 않아 서버는 없이 뜨고, 기본 지식베이스를
    # 만드는 `migrate`가 없으면 설정 오류로 끝낸다(`default_knowledge_base`).
    default_embedding_url: str | None = None
    default_embedding_model: str = "BAAI/bge-m3"
    default_embedding_dimensions: int = Field(default=1024, gt=0)
    default_reranker_url: str | None = None
    default_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    default_chunking_strategy: str = "structure_first"
    default_chunk_tokens: int = Field(default=512, gt=0)
    default_chunk_overlap_tokens: int = Field(default=64, ge=0)

    max_upload_mb: int = Field(default=100, gt=0)
    worker_concurrency: int = Field(default=2, gt=0)
    worker_poll_seconds: int = Field(default=5, gt=0)
    job_lease_seconds: int = Field(default=600, gt=0)
    job_max_attempts: int = Field(default=6, gt=0)
    job_backoff_base_seconds: float = Field(default=30.0, gt=0)
    tei_batch_size: int = Field(default=32, gt=0)
    tei_timeout_seconds: int = Field(default=60, gt=0)

    parse_timeout_seconds: int = Field(default=300, gt=0)
    parse_memory_mb: int = Field(default=2048, gt=0)
    parse_max_pages: int = Field(default=1000, gt=0)
    parse_max_unzipped_mb: int = Field(default=512, gt=0)
    parse_max_compression_ratio: int = Field(default=100, gt=0)
    parse_max_text_mb: int = Field(default=64, gt=0)

    # pgvector의 `hnsw.ef_search`는 1부터 1000까지만 받고, 검색이 이 값을 그대로 그 설정에 넣는다.
    search_candidates: int = Field(default=50, gt=0, le=1000)
    search_default_top_k: int = Field(default=10, gt=0)
    search_max_top_k: int = Field(default=50, gt=0)
    search_timeout_seconds: int = Field(default=20, gt=0)
    # `get_document`가 한 번에 내는 전문 창의 최대 글자 수(코드 포인트). 클라이언트마다 도구 출력의
    # 상한이 있어, 전문 전체를 한 번에 내지 않고 이 크기로 나눠 낸다(명세 "MCP 도구").
    document_text_max_chars: int = Field(default=20000, gt=0)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_allowed_hosts(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return [host.strip() for host in value.split(",") if host.strip()]

    @field_validator("allowed_hosts")
    @classmethod
    def _require_allowed_hosts(cls, hosts: list[str]) -> list[str]:
        if not hosts:
            raise ValueError("RAG_ALLOWED_HOSTS가 비어 있다. 하나 이상 적어야 기동한다(ADR 0014)")
        return hosts

    @field_validator("default_reranker_url", mode="before")
    @classmethod
    def _empty_reranker_url_means_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _require_default_top_k_within_max(self) -> "Settings":
        # 검색이 `top_k`의 상한을 강제하므로, 기본값이 상한을 넘으면 `top_k`를 주지 않은 모든 검색이
        # 요청 때마다 `invalid_argument`가 된다. 기동 때 걸러 설정 오류를 바로 드러낸다.
        if self.search_default_top_k > self.search_max_top_k:
            raise ValueError(
                f"RAG_SEARCH_DEFAULT_TOP_K({self.search_default_top_k})가 "
                f"RAG_SEARCH_MAX_TOP_K({self.search_max_top_k})보다 크다"
            )
        return self

    def default_knowledge_base(self) -> DefaultKnowledgeBaseSettings:
        has_reranker = self.default_reranker_url is not None
        if self.default_embedding_url is None:
            raise ConfigurationError("RAG_DEFAULT_EMBEDDING_URL이 없다. 임베딩 끝점을 적어야 한다")
        return DefaultKnowledgeBaseSettings(
            embedding_url=self.default_embedding_url,
            embedding_model=self.default_embedding_model,
            embedding_dimensions=self.default_embedding_dimensions,
            reranker_url=self.default_reranker_url,
            reranker_model=self.default_reranker_model if has_reranker else None,
            chunking=ChunkingConfig(
                strategy=self.default_chunking_strategy,
                max_tokens=self.default_chunk_tokens,
                overlap_tokens=self.default_chunk_overlap_tokens,
            ),
        )


def load_settings() -> Settings:
    """환경에서 설정을 읽는다. 검증 오류의 메시지는 입력 값(연결 문자열의 비밀번호)을 싣고 원인
    사슬에도 남으므로, 칸 이름과 오류 유형만 담은 `ConfigurationError`로 바꾸고 사슬을 끊는다."""
    try:
        return Settings()
    except ValidationError as error:
        prefix = Settings.model_config.get("env_prefix", "")
        problems = (
            f"{prefix}{'.'.join(str(part) for part in problem['loc']).upper()}: {problem['type']}"
            for problem in error.errors()
        )
        raise ConfigurationError("; ".join(problems)) from None
