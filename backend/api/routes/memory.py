"""FROZEN filename at tag contracts-v1. Body owned by Card 2A (EverMind memory).

Stub routes return HTTP 501 until Card 2A fills this module in. Response
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

router = APIRouter(prefix="/memory")

_NOT_IMPLEMENTED = JSONResponse(status_code=501, content={"detail": "not implemented"})


class ProfileOut(BaseModel):
    user_id: str
    specialty: str | None
    conditions_explored: list[str]
    query_count: int
    distilled_context: str
    seen_pmid_count: int


class SpecialtyRequest(BaseModel):
    user_id: str
    specialty: str


class ForgetRequest(BaseModel):
    user_id: str


class ThreadOut(BaseModel):
    session_id: str
    user_id: str
    queries: list[str]
    pmids_shown: list[str]


@router.get("/profile", response_model=ProfileOut)
def memory_profile(user_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.post("/specialty", status_code=204)
def memory_specialty(body: SpecialtyRequest) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.post("/forget", status_code=204)
def memory_forget(body: ForgetRequest) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/thread", response_model=ThreadOut)
def memory_thread(user_id: str, session_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED
