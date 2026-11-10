"""토큰 관리 API(명세 "관리 API"). 발급·목록·회수이고 모두 `admin` 토큰의 몫이다(인증 미들웨어가
`reader`의 REST를 막는다). 시각은 UTC `Z`로 낸다(ADR 0015)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import AwareDatetime, BaseModel, Field

from rag_engine.app.tokens import TokenView, issue_token, list_tokens, revoke_token
from rag_engine.domain.entities import TokenRole
from rag_engine.domain.ports import TokenStore, UnitOfWork


class IssueTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="토큰의 이름")
    role: TokenRole = Field(description="`admin`은 REST와 MCP 전부, `reader`는 MCP만")
    knowledge_bases: list[str] = Field(
        default_factory=list,
        description="`reader`가 볼 지식베이스 이름. 비면 전부. `admin`에는 줄 수 없다",
    )
    expires_at: AwareDatetime | None = Field(
        default=None, description="만료 시각(오프셋이 붙은 ISO 8601). 지난 시각이면 422"
    )


class TokenSummary(BaseModel):
    id: UUID
    name: str
    role: TokenRole
    knowledge_bases: list[str]
    expires_at: datetime | None
    created_at: datetime


class IssuedTokenResponse(TokenSummary):
    token: str = Field(description="토큰 원문. 이 응답에만 나오고 다시 볼 수 없다")


class TokenListResponse(BaseModel):
    tokens: list[TokenSummary]


def _utc(moment: datetime | None) -> datetime | None:
    return None if moment is None else moment.astimezone(UTC)


def _summary(view: TokenView) -> dict[str, object]:
    token = view.token
    created_at = _utc(token.created_at)
    return {
        "id": token.id,
        "name": token.name,
        "role": token.role,
        "knowledge_bases": list(view.knowledge_base_names),
        "expires_at": _utc(token.expires_at),
        "created_at": created_at,
    }


def build_token_router(token_store: TokenStore, unit_of_work: UnitOfWork) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin")

    @router.post("/tokens", status_code=201)
    async def issue(body: IssueTokenRequest) -> IssuedTokenResponse:
        issued = await issue_token(
            token_store,
            unit_of_work,
            name=body.name,
            role=body.role,
            knowledge_base_names=body.knowledge_bases,
            expires_at=body.expires_at,
            now=datetime.now(UTC),
        )
        view = TokenView(issued.token, tuple(dict.fromkeys(body.knowledge_bases)))
        return IssuedTokenResponse.model_validate({**_summary(view), "token": issued.raw})

    @router.get("/tokens")
    async def list_all() -> TokenListResponse:
        views = await list_tokens(token_store, unit_of_work)
        return TokenListResponse.model_validate({"tokens": [_summary(view) for view in views]})

    @router.delete("/tokens/{token_id}", status_code=204)
    async def revoke(token_id: UUID) -> None:
        await revoke_token(token_store, token_id, datetime.now(UTC))

    return router
