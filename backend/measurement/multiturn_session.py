"""Measurement gate, session-level view (plan.md Step 2.4): simulate 5-8
follow-up queries on the same case, each triggering a loop call, and record
cumulative tokens with vs without the proxy across turns. This produces the
session cost ledger's underlying data (with-Paritok flat, without climbing).
"""
from __future__ import annotations

from backend.app.llm_client import ParitokLLMClient
from backend.app.loop.hyde import build_hyde_prompt

FOLLOW_UP_QUERIES = [
    "PET findings in rare frontoparietal scalp lesions",
    "differential diagnosis for focal FDG uptake at a scalp lesion",
    "how does scalp angiosarcoma FDG uptake compare to metastatic lesions",
    "typical age and presentation for scalp angiosarcoma case reports",
    "imaging follow-up protocol after scalp angiosarcoma resection",
    "recurrence patterns visible on follow-up PET for scalp angiosarcoma",
]


def run_multiturn_session(client: ParitokLLMClient, turns: int = 6) -> dict:
    queries = FOLLOW_UP_QUERIES[:turns]
    proxied_cumulative: list[int] = []
    direct_cumulative: list[int] = []
    proxied_total = 0
    direct_total = 0

    for query in queries:
        proxied_total += client.chat(build_hyde_prompt(query), direct=False).prompt_tokens
        direct_total += client.chat(build_hyde_prompt(query), direct=True).prompt_tokens
        proxied_cumulative.append(proxied_total)
        direct_cumulative.append(direct_total)

    return {"proxied_cumulative": proxied_cumulative, "direct_cumulative": direct_cumulative}
