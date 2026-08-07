"""RESTORED module - adapter from the pre-freeze LLM client onto LLMPort.

WHY THIS FILE EXISTS
--------------------
The v2 freeze deleted backend/app/llm_client.py, but six modules still import
it, so `backend.api.main` does not import and the API will not boot:

    backend/api/dependencies.py:12      backend/api/routes/query.py:24
    backend/app/loop/hyde.py:8          backend/app/loop/refine.py:11
    backend/app/loop/relevance_check.py:9
    backend/app/summary/generate.py:12  backend/app/verify/citation_check.py:10

Restoring the module as a thin adapter over the FROZEN LLMPort fixes all six
call sites at once with zero edits to any existing file. The alternative -
editing dependencies.py and query.py - touches two files that Bryan owns
during an active merge. This does not.

Everything here delegates to `get_services().llm`, so the profile in
config/services.yaml still decides what actually runs, and the fake profile
still needs no credentials.

SURFACE: only what the existing callers actually use, verified by grep -
`client.chat(...)` returning something with `.content` and `.degraded`, plus
`compress_for_prompt`. Nothing speculative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

#: Call site recorded for chat() calls that do not name one. The frozen
#: CallSite literal has no "generic" member, and "summary" is the honest
#: majority case, so ledger attribution is coarse-but-valid rather than
#: invented. Pass call_site= explicitly where precision matters.
DEFAULT_CALL_SITE = "summary"


@dataclass(frozen=True)
class ChatResult:
    """What the pre-freeze client returned. Callers read .content/.degraded."""

    content: str
    degraded: bool = False
    error: str | None = None
    usage: Any | None = None


def _to_messages(messages: Sequence[Any]) -> list:
    """Accept the dict messages this codebase uses; emit frozen Message objects."""
    from backend.contracts.models import Message

    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append(Message(role=m.get("role", "user"), content=m.get("content", "")))
        else:
            out.append(m)
    return out


class ParitokLLMClient:
    """Pre-freeze call shape (`chat(messages, response_format=, direct=)`) on
    top of the frozen LLMPort."""

    def __init__(self, *, user_id: str = "api", session_id: str = "api") -> None:
        self._user_id = user_id
        self._session_id = session_id

    def chat(
        self,
        messages: Sequence[Any],
        *,
        response_format: dict | None = None,
        direct: bool = False,
        call_site: str = DEFAULT_CALL_SITE,
        request_id: str = "api",
        max_output_tokens: int = 1024,
        **_ignored: Any,
    ) -> ChatResult:
        """Delegate to the configured LLMPort.

        `response_format` and `direct` are accepted because existing callers
        pass them; `response_format={"type": "json_object"}` maps onto the
        port's `json_schema` slot, and `direct` (which used to bypass a retry
        wrapper) is a no-op here because the port owns its own retry policy.
        """
        from backend.contracts.registry import get_services

        try:
            result = get_services().llm.chat(
                _to_messages(messages),
                call_site=call_site,
                request_id=request_id,
                session_id=self._session_id,
                user_id=self._user_id,
                json_schema=response_format,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            # Degrade rather than raise: the shared definition of done requires
            # /query to still return 200 with a truthful degraded flag when the
            # backing service is unreachable.
            return ChatResult(content="", degraded=True, error=str(exc))

        return ChatResult(
            content=result.content,
            degraded=result.degraded,
            error=result.error,
            usage=result.usage,
        )

    def health(self) -> dict:
        from backend.contracts.registry import get_services

        return get_services().llm.health()


def _count_tokens(text: str) -> int:
    """Whitespace token count - the same basis FakeLLM reports on."""
    return len(text.split())


def compress_for_prompt(text: str, query: str) -> tuple[str, int, int]:
    """(compressed_text, original_tokens, compressed_tokens).

    The pre-freeze implementation ran a learned compressor. That model is not
    in requirements.txt post-freeze and pulling it in mid-merge would be a
    dependency fight for no demo value, so this returns the text unchanged and
    reports equal counts.

    Deliberately a truthful no-op rather than a fake ratio: `backend/app/summary
    /generate.py` logs these two numbers, and inventing a compression ratio
    would put a made-up figure next to MemEx's measured ones on the same
    screen. If real compression is wanted later, replace the body here - every
    caller already handles the tuple.
    """
    tokens = _count_tokens(text)
    return text, tokens, tokens


def _get_compression_pipeline() -> None:
    """Present for backend/measurement/run_gate.py:24, which imports it.

    Returns None because there is no compression pipeline post-freeze; the
    measurement harness treats a None pipeline as "compression disabled".
    """
    return None
