"""Single entry point for every Groq/Paritok call in the app.

Never call `openai.OpenAI(...)` directly anywhere else - routing everything
through here is what makes the Paritok dashboard's token savings number
reflect the whole app, not just some calls (plan.md Architecture section).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from openai import APIError, APITimeoutError, OpenAI

from paritok.config import ParitokConfig
from paritok.pipelines.compress import CompressionPipeline
from paritok.token_counter import count_tokens

logger = logging.getLogger(__name__)

GROQ_DIRECT_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-flash-latest"

# gpu_server.timeout in paritok.yaml is 180s, sized for RunPod cold starts
# (plan/paritok-feedback.md #2: a real cold start measured at 45.5s, and the
# strategy has no retry/backoff of its own). That's fine for a background job
# but far too long to block an interactive query. Cap our own wait well below
# it; a still-running call degrades exactly like the pipeline's own
# gpu_unavailable passthrough path (original content, ratio 0).
COMPRESSION_DEADLINE_S = 8.0

# The proxy's message-shape auto-detection only compresses role="tool" content
# and long conversation history - it never sees a plain single-shot system+user
# RAG prompt (our HyDE/relevance/summary calls). Calling the pipeline directly
# on a large context block (e.g. stuffed retrieved abstracts) is what actually
# reaches the Paritok GPU server for this app's call shape.
_PARITOK_YAML = Path(__file__).resolve().parent.parent.parent / "paritok.yaml"
_compression_pipeline: CompressionPipeline | None = None


def _get_compression_pipeline() -> CompressionPipeline:
    global _compression_pipeline
    if _compression_pipeline is None:
        config = ParitokConfig.load(str(_PARITOK_YAML))
        _compression_pipeline = CompressionPipeline(config)
    return _compression_pipeline


def compress_for_prompt(content: str, query: str) -> tuple[str, int, int]:
    """Compress a large context block before it's stuffed into a prompt.

    Safe to call unconditionally: content below `compression.min_tokens` or a
    failed/unavailable GPU server both return the original content unchanged
    (CompressionPipeline's own gating and degrade-to-passthrough behavior).
    Returns (text_to_send, original_tokens, compressed_tokens).
    """
    # upstream_model lets the hosted GPU server attribute $ saved at the real
    # per-model rate (Groq's llama-3.3-70b-versatile pricing) instead of an
    # unlabeled default - accuracy, since the dashboard can only price what it
    # knows which model the compressed content was headed for.
    outcome: dict = {}

    def _run() -> None:
        outcome["result"] = _get_compression_pipeline().compress(content, query=query, upstream_model=MODEL)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=COMPRESSION_DEADLINE_S)

    if "result" not in outcome:
        # Still cold-starting past our deadline - degrade to passthrough now
        # rather than let the request hang for up to gpu_server.timeout (180s).
        tokens = count_tokens(content)
        return content, tokens, tokens

    result = outcome["result"]
    return result.compressed, result.original_tokens, result.compressed_tokens


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    degraded: bool = False
    error: str | None = None


class ParitokLLMClient:
    def __init__(self) -> None:
        base_url = os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not base_url or not api_key:
            raise RuntimeError(
                "OPENAI_BASE_URL and OPENAI_API_KEY must be set (load .env before "
                "constructing ParitokLLMClient)."
            )
        self.proxy_base_url = base_url
        self.api_key = api_key
        # The OpenAI SDK appends "/chat/completions" directly to base_url (it expects
        # base_url to already end in "/v1"); OPENAI_BASE_URL is the bare proxy host,
        # so the "/v1" suffix has to be added here rather than stored on proxy_base_url.
        proxy_client_base_url = base_url.rstrip("/")
        if not proxy_client_base_url.endswith("/v1"):
            proxy_client_base_url += "/v1"
        # Explicit per-request timeout: the SDK's own default (600s) would let a
        # hung Paritok proxy connection stall every retry attempt in turn, defeating
        # the exponential-backoff retry loop below.
        self._proxy_client = OpenAI(base_url=proxy_client_base_url, api_key=api_key, timeout=15.0)
        self._direct_client = OpenAI(base_url=GROQ_DIRECT_BASE_URL, api_key=api_key, timeout=15.0)
        gemini_key = os.environ.get("GEMINI_API_KEY")
        self._gemini_client = (
            OpenAI(base_url=GEMINI_BASE_URL, api_key=gemini_key, timeout=15.0)
            if gemini_key else None
        )

    def chat(
        self,
        messages: list[dict],
        *,
        response_format: dict | None = None,
        direct: bool = False,
        max_retries: int = 3,
    ) -> ChatResult:
        client = self._direct_client if direct else self._proxy_client
        kwargs: dict = {"model": MODEL, "messages": messages}
        if response_format is not None:
            kwargs["response_format"] = response_format

        last_error = ""
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(**kwargs)
                usage = response.usage
                return ChatResult(
                    content=response.choices[0].message.content or "",
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                )
            except (APIError, APITimeoutError) as exc:
                last_error = str(exc)
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                continue

        if self._gemini_client is not None:
            try:
                response = self._gemini_client.chat.completions.create(
                    **{**kwargs, "model": GEMINI_MODEL}
                )
                usage = response.usage
                return ChatResult(
                    content=response.choices[0].message.content or "",
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                )
            except (APIError, APITimeoutError) as exc:
                last_error = str(exc)

        logger.warning("LLM call degraded after all retries/fallbacks exhausted: %s", last_error)
        return ChatResult(
            content="",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            degraded=True,
            error=last_error,
        )
