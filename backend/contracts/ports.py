"""FROZEN at tag contracts-v1. Do not edit on a feature branch."""
from __future__ import annotations
from typing import Protocol, Sequence
from backend.contracts.models import *  # noqa


class RetrievalPort(Protocol):
    def search(
        self,
        query: str,
        *,
        secondary_query: str | None = None,
        top_k: int = 10,
        apply_rarity: bool = True,
        exclude_pmids: Sequence[str] = (),
    ) -> list[ScoredPaper]: ...

    def closest_conditions(self, query: str, top_n: int = 3) -> list[ConditionMatch]: ...

    def get_by_pmids(self, pmids: Sequence[str]) -> list[Paper]: ...

    def health(self) -> dict: ...


class LLMPort(Protocol):
    def chat(
        self,
        messages: list[Message],
        *,
        call_site: CallSite,
        request_id: str,
        session_id: str,
        user_id: str,
        json_schema: dict | None = None,
        max_output_tokens: int = 1024,
    ) -> ChatResult: ...

    def health(self) -> dict: ...


class MemoryPort(Protocol):
    def get_profile(self, user_id: str) -> ResearcherProfile: ...
    def get_thread(self, user_id: str, session_id: str) -> SessionThread: ...
    def record_query(self, user_id: str, session_id: str, query: str,
                     matched_conditions: Sequence[str]) -> None: ...
    def record_papers_shown(self, user_id: str, session_id: str,
                            pmids: Sequence[str]) -> None: ...
    def seen_pmids(self, user_id: str) -> set[str]: ...
    def set_specialty(self, user_id: str, specialty: str) -> None: ...
    def forget(self, user_id: str) -> None: ...
    def health(self) -> dict: ...


class LedgerPort(Protocol):
    def record(self, event: LedgerEvent) -> None: ...
    def health(self) -> dict: ...
