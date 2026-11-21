"""커넥터 레지스트리. entry point 그룹 `rag_engine.connectors`에서 이름으로 커넥터를 찾고 인터페이스
버전의 major 가 1이 아니면 거부한다(명세 "커넥터 인터페이스 1.0", ADR 0012).

가짜 entry point 는 `importlib.metadata.EntryPoint` 를 직접 만들어 쓴다. 설치된 패키지가 없어도
같은 `load()` 길을 지난다.
"""

import logging
from importlib.metadata import EntryPoint

import pytest
from tests.support.fake_connectors import LEAKED_TEXT, FakeConnector

from rag_engine.adapters.connectors import registry as registry_module
from rag_engine.adapters.connectors.registry import (
    CONNECTOR_ENTRY_POINT_GROUP,
    EntryPointConnectorRegistry,
)
from rag_engine.domain.connectors import (
    ConnectorError,
    ConnectorFailureReason,
    ConnectorUnavailableError,
)
from rag_engine.domain.ports import ConnectorRegistry

_MODULE = "tests.support.fake_connectors"


def _entry(name: str, function: str) -> EntryPoint:
    return EntryPoint(name=name, value=f"{_MODULE}:{function}", group=CONNECTOR_ENTRY_POINT_GROUP)


def _registry(*entries: EntryPoint) -> EntryPointConnectorRegistry:
    return EntryPointConnectorRegistry(lambda: entries)


def test_그룹_이름은_rag_engine_connectors다() -> None:
    assert CONNECTOR_ENTRY_POINT_GROUP == "rag_engine.connectors"


def test_이름으로_찾아_원천의_설정을_넘겨_커넥터를_만든다() -> None:
    registry: ConnectorRegistry = _registry(_entry("fake", "create_fake"))

    connector = registry.create("fake", {"folder": "a", "depth": 2})

    assert isinstance(connector, FakeConnector)
    assert connector.config == {"folder": "a", "depth": 2}
    assert connector.interface_version == "1.0.0"


def test_이름이_다른_커넥터_여럿_가운데_이름이_맞는_것을_만든다() -> None:
    registry = _registry(
        _entry("first", "create_requiring_folder"), _entry("second", "create_fake")
    )

    connector = registry.create("second", {})

    assert isinstance(connector, FakeConnector)


def test_설치되지_않은_이름은_쓸_수_없는_커넥터로_거부한다() -> None:
    registry = _registry(_entry("fake", "create_fake"))

    with pytest.raises(ConnectorUnavailableError):
        registry.create("not-installed", {})


def test_entry_point가_하나도_없으면_모든_이름이_쓸_수_없다() -> None:
    with pytest.raises(ConnectorUnavailableError):
        _registry().create("fake", {})


def test_인터페이스_버전의_major가_다르면_쓸_수_없는_커넥터로_거부한다() -> None:
    registry = _registry(_entry("next", "create_next_major"))

    with pytest.raises(ConnectorUnavailableError):
        registry.create("next", {})


def test_minor가_높은_커넥터는_받는다() -> None:
    registry = _registry(_entry("minor", "create_next_minor"))

    connector = registry.create("minor", {})

    assert connector.interface_version == "1.7.2"


def test_거부는_두_경우가_같은_예외이고_사유_예외가_아니다() -> None:
    registry = _registry(_entry("next", "create_next_major"))

    with pytest.raises(ConnectorUnavailableError) as major:
        registry.create("next", {})
    with pytest.raises(ConnectorUnavailableError) as missing:
        registry.create("none", {})

    assert type(major.value) is type(missing.value)
    assert not isinstance(major.value, ConnectorError)


def test_만드는_함수가_invalid_config를_올리면_그_사유를_그대로_전한다() -> None:
    registry = _registry(_entry("strict", "create_requiring_folder"))

    with pytest.raises(ConnectorError) as caught:
        registry.create("strict", {"folder": 3})

    assert caught.value.reason is ConnectorFailureReason.INVALID_CONFIG


def test_사유_예외에_원인이_묶여_있으면_끊고_사유만_전한다() -> None:
    registry = _registry(_entry("chained", "create_chained"))

    with pytest.raises(ConnectorError) as caught:
        registry.create("chained", {})

    assert caught.value.reason is ConnectorFailureReason.INVALID_CONFIG
    # `from None`만으로는 `__context__`에 원래 예외가 남아, 그 원인의 글을 사슬로 걸어 읽을 수 있다.
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert LEAKED_TEXT not in str(caught.value)


def test_만들_때_invalid_config가_아닌_사유는_쓸_수_없는_커넥터로_거부한다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = _registry(_entry("unreadable", "create_unreadable"))

    with caplog.at_level(logging.DEBUG), pytest.raises(ConnectorUnavailableError) as caught:
        registry.create("unreadable", {})

    logged = " ".join(repr(record.__dict__) for record in caplog.records)
    assert "connector_rejected" in logged
    assert "ConnectorError" in logged
    assert caught.value.__context__ is None


def test_설정이_맞으면_같은_커넥터가_만들어진다() -> None:
    registry = _registry(_entry("strict", "create_requiring_folder"))

    connector = registry.create("strict", {"folder": "a"})

    assert isinstance(connector, FakeConnector)


def test_만드는_함수가_인터페이스_밖의_예외를_내면_쓸_수_없는_커넥터로_거부하고_글은_없다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = _registry(_entry("broken", "create_broken"))

    with caplog.at_level(logging.DEBUG), pytest.raises(ConnectorUnavailableError) as caught:
        registry.create("broken", {})

    logged = " ".join(repr(record.__dict__) for record in caplog.records)
    assert LEAKED_TEXT not in str(caught.value)
    assert LEAKED_TEXT not in logged
    assert "RuntimeError" in logged
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_인터페이스_버전이_문자열이_아니면_쓸_수_없는_커넥터로_거부한다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = _registry(_entry("numeric", "create_numeric_version"))

    with caplog.at_level(logging.DEBUG), pytest.raises(ConnectorUnavailableError):
        registry.create("numeric", {})

    assert "AttributeError" in " ".join(repr(record.__dict__) for record in caplog.records)


def test_불러올_수_없는_entry_point는_쓸_수_없는_커넥터로_거부한다() -> None:
    registry = _registry(
        EntryPoint(name="gone", value="no_such_module_xyz:make", group=CONNECTOR_ENTRY_POINT_GROUP)
    )

    with pytest.raises(ConnectorUnavailableError):
        registry.create("gone", {})


def test_거부한_커넥터는_이름과_버전을_기록하고_설정은_기록하지_않는다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = _registry(_entry("next", "create_next_major"))

    with caplog.at_level(logging.WARNING), pytest.raises(ConnectorUnavailableError):
        registry.create("next", {"folder": "민감한-폴더-이름"})

    logged = " ".join(repr(record.__dict__) for record in caplog.records)
    assert "connector_rejected" in logged
    assert "2.0.0" in logged
    assert "민감한-폴더-이름" not in logged


def test_기본_탐색은_설치된_entry_point의_그룹_rag_engine_connectors를_읽는다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []

    def fake_entry_points(*, group: str) -> list[EntryPoint]:
        asked.append(group)
        return [_entry("fake", "create_fake")]

    monkeypatch.setattr(registry_module, "entry_points", fake_entry_points)

    connector = EntryPointConnectorRegistry().create("fake", {})

    assert asked == ["rag_engine.connectors"]
    assert isinstance(connector, FakeConnector)
