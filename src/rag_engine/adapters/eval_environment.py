"""평가 도구의 환경과 설정(명세 search-eval "자리와 층"의 구성 항목, "평가 전용 데이터베이스").

평가 도구는 평가를 위해 만든 데이터베이스에만 붙는다. 데이터베이스 주소, 데이터 폴더, 임베딩 끝점,
리랭커 끝점(없어도 된다)은 평가 전용 이름 `RAG_EVAL_*`로만 받고, 제품의 `RAG_DATABASE_URL`,
`RAG_DATA_DIR`, `RAG_DEFAULT_*`와 작업 폴더의 `.env`는 읽지 않는다. 제품의 설정 객체(`Settings`)는
그 환경 변수와 `.env`를 읽으므로, 이 모듈이 지은 설정 객체는 읽는 곳을 지어 준 값 하나로 좁힌다
(`_IsolatedSettings`). 그래서 `config.json`과 평가 전용 이름에서 오지 않은 칸(파싱 한도, TEI 배치
크기 같은)은 코드의 기본값이 된다.

데이터베이스의 이름이 `rag_eval`로 시작하지 않거나 주소에서 이름을 읽을 수 없으면 접속하기 전에
거부한다. 오류 문장은 주소를 싣지 않는다(연결 문자열의 비밀번호, 원칙 V).

못 보는 것. 이름은 관례라 그 머리로 이름을 지은 제품의 데이터베이스까지 막지는 못한다. 막으려는
것은 주소를 잘못 적는 실수다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import parse_qs, urlsplit

from pydantic import ValidationError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from rag_engine.adapters.settings import Settings
from rag_engine.domain.eval_set import EvalConfig

DATABASE_ENV: Final = "RAG_EVAL_DATABASE_URL"
DATA_DIR_ENV: Final = "RAG_EVAL_DATA_DIR"
EMBEDDING_ENV: Final = "RAG_EVAL_EMBEDDING_URL"
RERANKER_ENV: Final = "RAG_EVAL_RERANKER_URL"
# 데이터베이스에 붙는 하위 명령이 반드시 받는 이름이다. 리랭커는 없어도 된다.
REQUIRED_ENV: Final = (DATABASE_ENV, DATA_DIR_ENV, EMBEDDING_ENV)
DATABASE_NAME_PREFIX: Final = "rag_eval"
_SCHEME: Final = "postgresql://"
# 주소의 질의 칸 가운데 연결의 목적지(데이터베이스, 호스트, 포트, 서비스 파일)를 바꾸지 않는 것만
# 받는다. 거부 목록으로 짜면 libpq가 받는 칸이 늘 때마다 새 우회가 생긴다.
_SAFE_QUERY_KEYS: Final = frozenset({"sslmode", "connect_timeout", "application_name"})


class EvalEnvironmentError(Exception):
    """평가 환경의 오류. 메시지는 값이 아니라 이름과 규칙만 싣는다."""


@dataclass(frozen=True, slots=True)
class EvalEnvironment:
    database_url: str
    data_dir: Path
    embedding_url: str
    reranker_url: str | None


def read_eval_environment(environ: Mapping[str, str]) -> EvalEnvironment:
    """평가 전용 이름에서 환경을 읽는다. 앞의 셋 가운데 빠진 것이 있으면 빠진 이름을 알리고,
    데이터베이스 의 이름이 규칙에 맞지 않으면 알린다. 어느 쪽도 데이터베이스에 접속하지 않는다."""
    missing = [name for name in REQUIRED_ENV if not environ.get(name)]
    if missing:
        raise EvalEnvironmentError(f"평가 전용 환경 변수가 없다: {', '.join(missing)}")
    database_url = environ[DATABASE_ENV]
    check_database_name(database_url)
    return EvalEnvironment(
        database_url=database_url,
        data_dir=Path(environ[DATA_DIR_ENV]),
        embedding_url=environ[EMBEDDING_ENV],
        reranker_url=environ.get(RERANKER_ENV) or None,
    )


def check_database_name(database_url: str) -> None:
    """데이터베이스의 이름이 `rag_eval`로 시작하는지 본다. 주소에서 이름을 읽을 수 없는 것도
    거부한다. libpq가 경로의 이름이나 호스트를 덮어쓸 수 있는 질의 칸(`dbname`, `host`, `service`
    같은)이 든 주소도 이름을 읽을 수 없는 것으로 본다. 질의 칸은 `_SAFE_QUERY_KEYS`의 것만
    받는다."""
    rule = (
        f"{DATABASE_ENV}가 가리키는 데이터베이스의 이름은 '{DATABASE_NAME_PREFIX}'로 시작해야 한다."
        f" 평가 전용 데이터베이스에만 붙는다(주소는 {_SCHEME}로 시작하고 경로에 이름을 적는다)"
    )
    if not database_url.startswith(_SCHEME):
        raise EvalEnvironmentError(rule)
    try:
        parsed = make_url(database_url)
    except ArgumentError:
        raise EvalEnvironmentError(rule) from None
    name = parsed.database
    # `make_url`은 값이 빈 `?dbname=`을 질의에서 버리므로 글자 그대로의 질의에서 칸의 이름을 본다.
    keys = {key.lower() for key in parse_qs(urlsplit(database_url).query, keep_blank_values=True)}
    if not name or not keys <= _SAFE_QUERY_KEYS or not name.startswith(DATABASE_NAME_PREFIX):
        raise EvalEnvironmentError(rule)


class _IsolatedSettings(Settings):
    """환경 변수, `.env`, 비밀 파일을 읽지 않고 지어 준 값만 받는 제품의 설정 객체."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


def eval_settings(environment: EvalEnvironment, config: EvalConfig) -> Settings:
    """`config.json`과 평가 전용 환경에서 제품의 설정 객체를 짓는다. 검증 오류는 칸 이름과 종류만
    싣는다 (값은 싣지 않는다)."""
    try:
        return _IsolatedSettings(
            database_url=environment.database_url,
            data_dir=environment.data_dir,
            # 평가 도구는 서버를 띄우지 않지만 필수 칸이라 채운다.
            allowed_hosts=["localhost"],
            default_embedding_url=environment.embedding_url,
            default_embedding_model=config.embedding_model,
            default_embedding_dimensions=config.embedding_dimensions,
            default_reranker_url=environment.reranker_url,
            default_reranker_model=config.reranker_model,
            default_chunking_strategy=config.chunking.strategy,
            default_chunk_tokens=config.chunking.max_tokens,
            default_chunk_overlap_tokens=config.chunking.overlap_tokens,
            search_candidates=config.search_candidates,
        )
    except ValidationError as error:
        problems = ", ".join(
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['type']}"
            for problem in error.errors()
        )
        raise EvalEnvironmentError(f"config.json의 값이 설정에 맞지 않는다: {problems}") from None
