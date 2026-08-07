"""MemEx Tier 1 - the cold-vs-warm cost substrate.

One question, two ways to answer it:

  COLD  no memory layer. Premium model, every retrieved abstract stuffed into
        the prompt in full, re-read and re-billed on every single turn.
  WARM  a compact digest - what the researcher profile already knows, plus
        one line per paper - then the cheapest model that can work from it.

The delta between those two prices is what MemEx sells. Tier 2 (market.py)
turns it into a trade price; this file is where the number comes from.

Three rules hold this honest, and each one is a question a judge can ask:

  1. BOTH PATHS GET THE SAME SYSTEM PROMPT AND THE SAME QUESTION. The only
     variable is how the context is represented. Otherwise the comparison
     measures prompt engineering, not memory.
  2. TOKENS ARE COUNTED ON THE EXACT FINAL PROMPT that gets sent - taken from
     the ChatResult the port returns, not estimated client-side.
  3. THE COLD PATH IS NOT SANDBAGGED. It gets every abstract in full and the
     premium rate. It answers correctly. It just pays for the privilege every
     turn. "Same answer, a fraction of the price" is a stronger claim than one
     bought by crippling the baseline.

--- THE ONE THING TO SAY OUT LOUD ------------------------------------------

`LLMPort.chat()` (FROZEN, backend/contracts/ports.py) takes no model argument -
the model is a property of the configured service, not of the call. So MemEx
cannot force the cold path onto claude-opus-5 and the warm path onto
llama3.1-8b through that interface.

What is therefore MEASURED and what is PRICED differ, and the response says so
in every payload:

  MEASURED  the token counts. Real, from the actual call, on both paths.
  PRICED    the rate applied to them. When ChatResult.usage.model is a model
            in the published table we use that model's rate and flag
            `model_measured=True`. Otherwise (the fake profile reports
            model="fake") we price the cold prompt at the premium rate and the
            warm prompt at the cheap rate and flag `model_measured=False`,
            i.e. "this is what those measured tokens would cost on those
            models".

The token delta - the thing memory actually causes - is real either way. The
model attribution is a scenario, and it is labelled as one. That distinction is
the difference between a number that survives a follow-up question and one that
does not.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from backend.memex import pricing
from backend.memex.scarcity import get_index

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

#: Identical on both paths, deliberately. Kept short so it is a rounding error
#: against either context - a long system prompt appears on both sides and
#: dilutes the measured delta.
SYSTEM_PROMPT = (
    "You are a neurology literature analyst. Answer the clinician's question "
    "directly from the sources provided. Cite each claim with its [n] marker. "
    "Be specific rather than general."
)

#: The one line that differs between the two prompts. Exported so Tier 2
#: rebuilds the cold prompt with the identical label when it counts what memory
#: displaced - a re-typed label would make the counterfactual differ from the
#: real cold run by a few tokens for no reason.
CONTEXT_LABELS = {
    "cold": "Full source abstracts:",
    "warm": "What you already know:",
}

#: How many papers each path is given. Same on both - the variable under test
#: is representation, not recall.
TOP_K = 5

#: Warm digest budget. Not a hard truncation of meaning: one sentence per paper
#: is what a researcher who has read them would carry forward.
WARM_SENTENCE_CHARS = 220


class _Services(Protocol):
    """Structural view of backend.contracts.registry.Services."""

    retrieval: Any
    llm: Any
    memory: Any
    ledger: Any


def _get_services() -> _Services:
    from backend.contracts.registry import get_services

    return get_services()


def _message(role: str, content: str):
    from backend.contracts.models import Message

    return Message(role=role, content=content)


def _first_sentence(text: str, limit: int = WARM_SENTENCE_CHARS) -> str:
    """First sentence of an abstract, hard-capped.

    The warm path's whole claim is that a distilled fact substitutes for the
    source. Taking the opening sentence is the cheapest defensible distillation
    and it is deterministic, which matters more than elegance for a demo that
    has to produce the same number twice.
    """
    stripped = " ".join(text.split())
    match = re.search(r"(?<=[.!?])\s", stripped)
    sentence = stripped[: match.start() + 1] if match else stripped
    if len(sentence) > limit:
        sentence = sentence[: limit - 1].rstrip() + "…"
    return sentence


def build_cold_context(scored_papers: Sequence[Any]) -> str:
    """Every retrieved abstract, in full. This is the bill memory removes."""
    blocks = []
    for i, sp in enumerate(scored_papers, start=1):
        p = sp.paper
        blocks.append(f"[{i}] {p.title} (PMID {p.pmid}, {p.condition})\n{p.abstract}")
    return "\n\n".join(blocks)


def build_warm_context(scored_papers: Sequence[Any], distilled_context: str) -> str:
    """The digest: what the profile already knows, plus one line per paper.

    Deliberately NOT the abstracts. Distillation already did the compression;
    this spends it. Re-including the source text here would hand back exactly
    the tokens the warm path exists to save.
    """
    blocks = []
    if distilled_context.strip():
        blocks.append(f"Researcher profile: {distilled_context.strip()}")
    for i, sp in enumerate(scored_papers, start=1):
        p = sp.paper
        blocks.append(f"[{i}] {p.title} ({p.condition}) - {_first_sentence(p.abstract)}")
    return "\n".join(blocks)


def _build_messages(question: str, context: str, label: str) -> list:
    return [
        _message("system", SYSTEM_PROMPT),
        _message("user", f"{label}\n{context}\n\nQuestion: {question}"),
    ]


# ---------------------------------------------------------------------------
# Result shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PathResult:
    """One of the two paths, measured and priced."""

    mode: str  # "cold" | "warm"
    summary_markdown: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    #: Model the rate came from.
    priced_as: str
    #: True when the port actually reported `priced_as`; False when we applied
    #: a scenario rate to measured tokens (see module docstring).
    model_measured: bool
    credits: float
    usd: float
    #: False when `priced_as` is not in the published table.
    published: bool
    degraded: bool
    error: str | None
    context_chars: int
    breakdown: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "summary_markdown": self.summary_markdown,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "priced_as": self.priced_as,
            "model_measured": self.model_measured,
            "credits": self.credits,
            "usd": self.usd,
            "published": self.published,
            "degraded": self.degraded,
            "error": self.error,
            "context_chars": self.context_chars,
            "breakdown": self.breakdown,
        }


@dataclass(frozen=True)
class AskResult:
    """Both paths plus the priced delta between them."""

    request_id: str
    query: str
    user_id: str
    session_id: str
    cold: PathResult
    warm: PathResult
    #: Prompt tokens the warm path did not have to send. The headline number.
    tokens_displaced: int
    #: Those tokens priced at the COLD input rate - what re-derivation costs.
    displaced_credits: float
    displaced_usd: float
    savings_percent: float
    cost_ratio: float
    scarcity_multiplier: float
    scarcity_condition: str
    scarcity_paper_count: int
    papers: list = field(default_factory=list)
    memory_applied: bool = False
    distilled_context: str = ""
    seen_filtered: int = 0

    def as_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "cold": self.cold.as_dict(),
            "warm": self.warm.as_dict(),
            "delta": {
                "tokens_displaced": self.tokens_displaced,
                "credits": self.displaced_credits,
                "usd": self.displaced_usd,
                "savings_percent": self.savings_percent,
                "cost_ratio": self.cost_ratio,
                "priced_at_model": self.cold.priced_as,
            },
            "scarcity": {
                "condition": self.scarcity_condition,
                "paper_count": self.scarcity_paper_count,
                "multiplier": self.scarcity_multiplier,
            },
            "memory": {
                "applied": self.memory_applied,
                "profile_used": bool(self.distilled_context),
                "distilled_context": self.distilled_context,
                "seen_filtered": self.seen_filtered,
            },
        }


# ---------------------------------------------------------------------------
# Summary extraction
# ---------------------------------------------------------------------------

#: FakeLLM's canned "summary" payload. Recognising it lets the fake profile
#: still render a real, sourced answer on stage instead of a placeholder.
_FAKE_SUMMARY_MARKER = "Fake summary"


def _summary_from(content: str, scored_papers: Sequence[Any], mode: str) -> str:
    """Pull markdown out of an LLM response, or synthesise it from the sources.

    Live models return JSON per the frozen `summary` call-site schema. The fake
    profile returns a canned stub. A demo that shows "**Fake summary.**" on the
    fake profile is a demo that cannot be rehearsed, so when the payload is
    absent, unparseable, or the known stub, we build a deterministic sourced
    summary from the papers actually retrieved. Both paths get the same
    treatment, so the comparison stays fair.
    """
    text = ""
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            text = str(parsed.get("summary_markdown") or parsed.get("summary") or "")
    except (json.JSONDecodeError, TypeError):
        text = content or ""

    if text and _FAKE_SUMMARY_MARKER not in text:
        return text

    if not scored_papers:
        return "No sources matched this query."

    lines = [
        f"**{scored_papers[0].paper.condition}** - {len(scored_papers)} sources retrieved."
    ]
    for i, sp in enumerate(scored_papers, start=1):
        lines.append(f"- {_first_sentence(sp.paper.abstract)} [{i}]")
    if mode == "warm":
        lines.append("")
        lines.append("_Answered from the distilled digest; abstracts were not re-read._")
    return "\n".join(lines)


def _price(
    usage: Any, scenario_model: str, kind_split: bool = True
) -> tuple[str, bool, pricing.PriceBreakdown]:
    """Decide which model's rate applies, and price the measured tokens.

    Returns (priced_as, model_measured, breakdown). See the module docstring for
    why this branch exists.
    """
    reported = getattr(usage, "model", "") or ""
    if pricing.is_published(reported):
        return reported, True, pricing.price_call(
            reported, usage.prompt_tokens, usage.completion_tokens
        )
    return scenario_model, False, pricing.price_call(
        scenario_model, usage.prompt_tokens, usage.completion_tokens
    )


def _run_path(
    *,
    mode: str,
    question: str,
    context: str,
    scored_papers: Sequence[Any],
    scenario_model: str,
    services: _Services,
    request_id: str,
    session_id: str,
    user_id: str,
) -> PathResult:
    messages = _build_messages(question, context, CONTEXT_LABELS[mode])
    result = services.llm.chat(
        messages,
        call_site="summary",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        max_output_tokens=1024,
    )
    priced_as, measured, breakdown = _price(result.usage, scenario_model)
    return PathResult(
        mode=mode,
        summary_markdown=_summary_from(result.content, scored_papers, mode),
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        priced_as=priced_as,
        model_measured=measured,
        credits=breakdown.credits_total,
        usd=breakdown.usd_total,
        published=breakdown.published,
        degraded=result.degraded,
        error=result.error,
        context_chars=len(context),
        breakdown=breakdown.as_dict(),
    )


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


def ask(
    query: str,
    *,
    user_id: str = "demo-researcher",
    session_id: str = "demo-session",
    personalize: bool = True,
    top_k: int = TOP_K,
    services: _Services | None = None,
    request_id: str | None = None,
) -> AskResult:
    """Run one question down both paths and price the gap.

    Everything goes through the frozen ports, so this runs keyless on the
    `fake` profile and unchanged on `live`.
    """
    svc = services or _get_services()
    rid = request_id or uuid.uuid4().hex

    # -- memory: what do we already know about this researcher? -------------
    distilled = ""
    seen: set[str] = set()
    memory_applied = False
    if personalize:
        try:
            profile = svc.memory.get_profile(user_id)
            distilled = profile.distilled_context or ""
            seen = svc.memory.seen_pmids(user_id)
            memory_applied = True
        except Exception:  # noqa: BLE001 - memory must never take the query down
            distilled, seen, memory_applied = "", set(), False

    # -- retrieval: identical paper set for both paths ----------------------
    scored = svc.retrieval.search(query, top_k=top_k, apply_rarity=True)
    seen_filtered = sum(1 for sp in scored if sp.paper.pmid in seen)

    # -- the two paths ------------------------------------------------------
    cold_ctx = build_cold_context(scored)
    warm_ctx = build_warm_context(scored, distilled)

    cold = _run_path(
        mode="cold",
        question=query,
        context=cold_ctx,
        scored_papers=scored,
        scenario_model=pricing.cold_model(),
        services=svc,
        request_id=rid,
        session_id=session_id,
        user_id=user_id,
    )
    warm = _run_path(
        mode="warm",
        question=query,
        context=warm_ctx,
        scored_papers=scored,
        scenario_model=pricing.warm_model(),
        services=svc,
        request_id=rid,
        session_id=session_id,
        user_id=user_id,
    )

    # -- the delta ----------------------------------------------------------
    # Priced at the COLD input rate on purpose: the question being answered is
    # "what would the premium model have been billed to read this instead?",
    # so the premium model's rate answers it. Pricing displaced tokens at the
    # cheap rate would understate what memory is worth by ~23x.
    tokens_displaced = max(0, cold.prompt_tokens - warm.prompt_tokens)
    displaced_credits = pricing.cost_for(tokens_displaced, cold.priced_as, "input")

    # -- scarcity -----------------------------------------------------------
    index = get_index()
    conditions = [sp.paper.condition for sp in scored]
    multiplier = index.multiplier_for_papers(conditions)
    top_condition = conditions[0] if conditions else ""
    # Report the condition that actually set the multiplier, not merely the
    # top hit - otherwise the number and its label can disagree on screen.
    if conditions:
        top_condition = max(conditions, key=index.multiplier)

    # -- write memory back --------------------------------------------------
    if personalize and memory_applied:
        try:
            svc.memory.record_query(user_id, session_id, query, conditions)
            svc.memory.record_papers_shown(
                user_id, session_id, [sp.paper.pmid for sp in scored]
            )
        except Exception:  # noqa: BLE001
            pass

    return AskResult(
        request_id=rid,
        query=query,
        user_id=user_id,
        session_id=session_id,
        cold=cold,
        warm=warm,
        tokens_displaced=tokens_displaced,
        displaced_credits=displaced_credits,
        displaced_usd=pricing.usd_for(displaced_credits),
        savings_percent=pricing.savings_percent(cold.credits, warm.credits),
        cost_ratio=pricing.cost_ratio(cold.credits, warm.credits),
        scarcity_multiplier=multiplier,
        scarcity_condition=top_condition,
        scarcity_paper_count=index.paper_count(top_condition),
        papers=list(scored),
        memory_applied=memory_applied,
        distilled_context=distilled,
        seen_filtered=seen_filtered,
    )
