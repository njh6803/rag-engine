"""파서 레지스트리. entry point 그룹 `rag_engine.parsers`에서 파서를 찾는다(ADR 0012).

내장 파서 셋도 같은 길로 등록한다. 인터페이스 판의 major가 다르면 그 파서를 거부하고 기록한다.
파싱은 자식 프로세스가 하므로 레지스트리는 파서의 이름과 불러올 자리(`모듈:클래스`)를 알려 주고,
자식이 그 자리를 스스로 불러 쓴다. 부모는 받는 MIME과 판을 알려고 한 번 불러 본다.
"""

import logging
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, entry_points, version
from typing import Final

from rag_engine.adapters.log_format import log_event
from rag_engine.domain.parsing import PARSER_INTERFACE_VERSION, Parser

logger = logging.getLogger(__name__)

PARSER_ENTRY_POINT_GROUP: Final = "rag_engine.parsers"
# 내장 파서가 감싸는 라이브러리의 배포 이름. 파싱 결과 행의 "라이브러리 판"이 이 배포의 판이다.
_BUILTIN_LIBRARIES: Final = {"docx": "python-docx", "pdf": "pdfplumber", "hwpx": "python-hwpx"}


@dataclass(frozen=True, slots=True)
class ParserSpec:
    """파서 하나의 이름과 불러올 자리. `library`는 파서가 감싸는 라이브러리의 배포 이름이다."""

    name: str
    target: str
    library: str


@dataclass(frozen=True, slots=True)
class RegisteredParser:
    spec: ParserSpec
    interface_version: str
    mime_types: tuple[str, ...]


def discover_parser_specs() -> list[ParserSpec]:
    """entry point 그룹에 등록된 파서를 모은다."""
    specs: list[ParserSpec] = []
    for entry in entry_points(group=PARSER_ENTRY_POINT_GROUP):
        library = _BUILTIN_LIBRARIES.get(entry.name) or (
            entry.dist.name if entry.dist is not None else entry.name
        )
        specs.append(ParserSpec(name=entry.name, target=entry.value, library=library))
    return specs


def load_parser(target: str) -> Parser:
    """`모듈:클래스`를 불러 인스턴스를 만든다. 자식 프로세스도 이 함수로 파서를 얻는다."""
    module_name, _, class_name = target.partition(":")
    parser_class: type[Parser] = getattr(import_module(module_name), class_name)
    return parser_class()


def library_version(library: str) -> str:
    try:
        return version(library)
    except PackageNotFoundError:
        return "unknown"


def _major(semver: str) -> str:
    return semver.partition(".")[0]


class ParserRegistry:
    def __init__(self, specs: list[ParserSpec]) -> None:
        self._parsers: list[RegisteredParser] = []
        for spec in specs:
            registered = self._register(spec)
            if registered is not None:
                self._parsers.append(registered)

    def names(self) -> list[str]:
        return [parser.spec.name for parser in self._parsers]

    def for_mime(self, mime: str) -> RegisteredParser | None:
        return next((parser for parser in self._parsers if mime in parser.mime_types), None)

    @staticmethod
    def _register(spec: ParserSpec) -> RegisteredParser | None:
        try:
            parser = load_parser(spec.target)
            interface_version = parser.interface_version
            mime_types = tuple(parser.mime_types)
        except Exception as error:  # 플러그인이 어떻게 깨져도 서버는 기동한다
            log_event(logger, "parser_rejected", level=logging.WARNING, exception=error)
            return None
        if _major(interface_version) != _major(PARSER_INTERFACE_VERSION):
            log_event(
                logger,
                "parser_rejected",
                level=logging.WARNING,
                parser=spec.name,
                interface_version=interface_version,
            )
            return None
        return RegisteredParser(spec, interface_version, mime_types)
