"""In-process TTL prompt cache for LLMPort.chat(), scoped to `hyde` and
`relevance_check` call sites only (see CACHEABLE_CALL_SITES below).

Hand-rolled dict + time.monotonic() TTL -- no new pip dependency. Key is a
hash of (call_site, model, normalized messages, json_schema); normalization
strips whitespace and anything that looks like a session-specific id (uuid4
hex, request_id-shaped tokens) out of message content so two logically
identical prompts differing only in embedded session/request ids still hit.

Deliberately does NOT touch backend/contracts/models.py's frozen
LedgerEvent -- there is no `cache_hit` field on it and there never will be
on this branch. Hit/miss bookkeeping lives entirely in the separate
CacheStats object in this module; callers who want per-call-site savings
read `cache_stats()`.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from threading import Lock

from backend.contracts.models import CallSite, ChatResult, Message

# Only these two call sites are eligible for caching (phase card Phase B.3).
# hyde and relevance_check are query-expansion / gate calls that are cheap
# to recompute wrong but expensive to recompute *identically* across many
# near-duplicate queries in a demo session; summary/citation_check/refine/
# memory_distill must always hit the model fresh (correctness-sensitive,
# session-specific, or both).
CACHEABLE_CALL_SITES: frozenset[str] = frozenset({"hyde", "relevance_check"})

_DEFAULT_TTL_SECONDS = 300.0

# Strips things that look like a uuid4 (session_id / request_id shape) or a
# bare "req_..." / "sess_..." token out of message content before hashing,
# so two prompts identical except for an embedded id still normalize equal.
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ID_TOKEN_RE = re.compile(r"\b(?:req|sess|session|request|user)[_-][0-9a-zA-Z]+\b", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _normalize_content(text: str) -> str:
    text = _UUID_RE.sub("<id>", text)
    text = _ID_TOKEN_RE.sub("<id>", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def normalize_messages(messages: list[Message]) -> tuple[tuple[str, str], ...]:
    # Accepts either Message instances or plain {"role", "content"} dicts -
    # most pipeline call sites build prompts as dicts (see
    # backend/snowflake/llm.py's chat(), which has the same tolerance).
    def _role(m):
        return m.role if hasattr(m, "role") else m["role"]

    def _content(m):
        return m.content if hasattr(m, "content") else m["content"]

    return tuple((_role(m), _normalize_content(_content(m))) for m in messages)


def cache_key(
    call_site: str,
    model: str,
    messages: list[Message],
    json_schema: dict | None,
) -> str:
    normalized = normalize_messages(messages)
    schema_repr = repr(sorted(json_schema.items())) if json_schema else "None"
    raw = repr((call_site, model, normalized, schema_repr))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class _CacheEntry:
    result: ChatResult
    expires_at: float  # time.monotonic() timestamp


@dataclass
class CacheStats:
    """Separate in-process stats object -- deliberately NOT part of the
    frozen LedgerEvent. hits/misses are per call_site so cache_stats() can
    report a real, observed avg-cost-per-call-derived savings estimate
    instead of a hardcoded number.
    """

    hits: int = 0
    misses: int = 0
    # running totals used to compute an *observed* avg cost/call, not a
    # hardcoded constant -- summed over real (uncached) chat() calls only.
    _observed_cost_sum: float = field(default=0.0, repr=False)
    _observed_cost_calls: int = field(default=0, repr=False)

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self, cost_usd: float | None = None) -> None:
        self.misses += 1
        if cost_usd is not None and cost_usd > 0:
            self._observed_cost_sum += cost_usd
            self._observed_cost_calls += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    @property
    def avg_observed_cost_usd(self) -> float:
        if self._observed_cost_calls == 0:
            return 0.0
        return self._observed_cost_sum / self._observed_cost_calls

    @property
    def estimated_cost_saved_usd(self) -> float:
        # Every cache hit avoided one real COMPLETE call; estimate what
        # that call would have cost using the *observed* avg cost/call from
        # this run's actual cache misses, not a hardcoded constant.
        return round(self.hits * self.avg_observed_cost_usd, 8)

    def as_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "estimated_cost_saved_usd": self.estimated_cost_saved_usd,
        }


class TTLPromptCache:
    """Thread-safe hand-rolled TTL cache. get()/set() only; entries past
    their expiry are treated as absent (and evicted lazily on access) --
    this guarantees a stale entry is never returned.
    """

    def __init__(self, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}
        self._lock = Lock()
        self.stats = CacheStats()

    def get(self, key: str) -> ChatResult | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() >= entry.expires_at:
                del self._store[key]
                return None
            return entry.result

    def set(self, key: str, result: ChatResult) -> None:
        with self._lock:
            self._store[key] = _CacheEntry(
                result=result, expires_at=time.monotonic() + self._ttl_seconds
            )

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# Module-level default instance, so CortexLLMClient (constructed with no
# args in production, per registry._load) and tests can share one cache
# without threading an extra constructor argument through every call site.
_default_cache = TTLPromptCache()


def get_default_cache() -> TTLPromptCache:
    return _default_cache


def cache_stats() -> dict:
    """{hits, misses, hit_rate, estimated_cost_saved_usd} for the
    module-level default cache, computed from actual observed
    avg-cost-per-call in this run -- see CacheStats.estimated_cost_saved_usd.
    """
    return _default_cache.stats.as_dict()


def is_cacheable_call_site(call_site: str) -> bool:
    return call_site in CACHEABLE_CALL_SITES
