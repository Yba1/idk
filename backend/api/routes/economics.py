"""FROZEN filename at tag contracts-v1. Body owned by Card 1 (Snowflake platform).

Stub routes return HTTP 501 until Card 1 fills this module in. Response
models are declared here (not implemented) so Card 2B's `npm run types:gen`
produces the real shape from /openapi.json against the fake profile, per
plan-v2/00-SHARED-CONTRACTS.md section 4. Returning a JSONResponse directly
skips response_model validation, so the 501 body ships as-is while the
documented schema stays intact.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/economics")

_NOT_IMPLEMENTED = JSONResponse(status_code=501, content={"detail": "not implemented"})


class CallSiteBreakdown(BaseModel):
    call_site: str
    requests: int
    tokens: int
    cost_usd: float


class HourlyBreakdown(BaseModel):
    hour_iso: str
    tokens: int
    cost_usd: float


class EconomicsSummaryOut(BaseModel):
    total_requests: int
    total_tokens: int
    total_cost_usd: float
    by_call_site: list[CallSiteBreakdown]
    by_hour: list[HourlyBreakdown]


class RequestCallOut(BaseModel):
    call_site: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    degraded: bool


class EconomicsRequestOut(BaseModel):
    request_id: str
    calls: list[RequestCallOut]
    total_cost_usd: float


class EconomicsAskRequest(BaseModel):
    question: str


class EconomicsAskOut(BaseModel):
    answer: str
    sql: str
    rows: list[dict]


@router.get("/summary", response_model=EconomicsSummaryOut)
def economics_summary(window: str = "24h") -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/request/{request_id}", response_model=EconomicsRequestOut)
def economics_request(request_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.post("/ask", response_model=EconomicsAskOut)
def economics_ask(body: EconomicsAskRequest) -> JSONResponse:
    return _NOT_IMPLEMENTED
