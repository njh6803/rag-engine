"""HTTP 표면. REST 와 MCP 를 한 FastAPI 앱이 연다(ADR 0005)."""

from rag_engine.server.app import create_app

__all__ = ["create_app"]
