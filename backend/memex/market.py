"""MemEx Tier 2 - the memory marketplace. IN MEMORY, PROCESS LOCAL.

Tier 1 proved a fact costs less to remember than to re-derive. This file turns
that gap into a *price*, so a fact stops being a cache entry and starts being
an asset one agent can sell to another.

--- THE HONEST PART, READ THIS FIRST ---------------------------------------

THE PEER AGENTS ARE SCRIPTED. `attending` and `sage` do not run. They are
ledger rows with names. There is no agent-to-agent protocol, no negotiation, no
autonomous loop underneath this. What actually happens: the buyer's warm path
retrieves context, this module looks up who is recorded as owning it, and books
a transfer. That is a deliberate scope choice, and it is the line to say out
loud if a judge asks.

What is NOT scripted, and is the whole point: the price. Every number below is
a measured token count multiplied by a published Snowflake credit rate.

--- THE PRICE --------------------------------------------------------------

    tokens displaced = cold prompt tokens - warm prompt tokens
    re-derivation cost = tokens displaced x published COLD input rate
    PRICE = re-derivation cost x MARGIN x scarcity(condition)

The seller charges a quarter of what the buyer would have burned doing it the
hard way, scaled by how irreplaceable the condition is. Both agents are better
off, which is what makes it a market rather than a toll. Selling above 1.0x
re-derivation cost would be irrational for the buyer, so MARGIN < 1 is a
modelling constraint, not taste. Scarcity can push the effective take to
0.25 x 2.093 = 0.523 - still under 1.0, so the constraint holds across the
whole corpus.

--- NOT MODELLED -----------------------------------------------------------

Counterparty risk, price discovery, bid/ask, memory quality disputes,
double-selling, revocation after purchase, and any settlement outside this
process. A restart empties the book.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from backend.memex import pricing

#: Micro-credits. 1 credit = 1,000,000 ucr. A single trade prices at roughly
#: 0.0004 credits; six leading zeros read as "nothing is happening" from the
#: back of a room. The ledger computes in credits - the honest, citable unit -
#: and only the display scales.
MICRO_CREDITS_PER_CREDIT = 1_000_000

#: The seller's cut of what the buyer would have spent re-deriving.
MARGIN = 0.25

#: Opening balance per agent, in credits. ~$0.30 - deliberately small, so a few
#: hundred trades would actually exhaust a wallet. A float large enough to never
#: run out would make the balance decorative.
OPENING_BALANCE_CREDITS = 0.1

#: Who owns what. Traceable to the seed rather than assigned at random:
#: `attending` is the assistant on every turn of the seeded sessions, so the
#: episodes are its work product. The profile is a synthesis across sessions -
#: different artifact, different producer - so `sage` holds it.
AGENT_ROLES = {
    "rookie": "new resident - has never seen this patient population. Buys.",
    "attending": "ran the seeded sessions. Owns the episodes. Sells.",
    "sage": "distilled the researcher profile. Owns it. Sells.",
}


def owner_of(kind: str) -> str:
    """Seller for a memory of `kind` ("profile" or "episode")."""
    return "sage" if kind == "profile" else "attending"


@dataclass
class Agent:
    id: str
    role: str
    balance_credits: float = OPENING_BALANCE_CREDITS
    earned_credits: float = 0.0
    spent_credits: float = 0.0

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "balance_credits": self.balance_credits,
            "balance_ucr": self.balance_credits * MICRO_CREDITS_PER_CREDIT,
            "earned_credits": self.earned_credits,
            "spent_credits": self.spent_credits,
        }


@dataclass(frozen=True)
class Trade:
    id: str
    buyer: str
    seller: str
    memory_kind: str
    memory_subject: str
    question: str
    tokens_displaced: int
    scarcity_multiplier: float
    price_credits: float
    price_usd: float
    #: Buyer surplus: re-derivation cost minus price. Why the buyer agrees.
    saved_credits: float
    saved_usd: float
    model: str
    ts: float

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["price_ucr"] = self.price_credits * MICRO_CREDITS_PER_CREDIT
        return d


@dataclass(frozen=True)
class ShockEvent:
    id: str
    condition: str
    question: str
    destroyed: int
    #: What the buyer paid for this question while the memory existed.
    pre_shock_credits: float
    #: What re-deriving it from scratch costs now that it does not.
    post_shock_credits: float
    #: post / pre. The number said out loud.
    spike: float
    tokens_re_derived: int
    scarcity_multiplier: float
    ts: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class Market:
    """Wallets and a trade book. One instance per process."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {
            aid: Agent(id=aid, role=role) for aid, role in AGENT_ROLES.items()
        }
        self.trades: list[Trade] = []
        self.shocks: list[ShockEvent] = []

    # -- state --------------------------------------------------------------

    def reset(self) -> None:
        """Back to opening balances. The rehearsal button."""
        self.__init__()

    def agents(self) -> list[dict]:
        return [a.as_dict() for a in self._agents.values()]

    def totals(self) -> dict:
        return {
            "trades": len(self.trades),
            "tokens_displaced": sum(t.tokens_displaced for t in self.trades),
            "volume_credits": sum(t.price_credits for t in self.trades),
            "volume_usd": sum(t.price_usd for t in self.trades),
            "buyer_surplus_credits": sum(t.saved_credits for t in self.trades),
            "shocks": len(self.shocks),
        }

    def book(self) -> dict:
        return {
            "agents": self.agents(),
            "trades": [t.as_dict() for t in self.trades],
            "shocks": [s.as_dict() for s in self.shocks],
            "totals": self.totals(),
            "margin": MARGIN,
            "micro_credits_per_credit": MICRO_CREDITS_PER_CREDIT,
        }

    # -- settlement ---------------------------------------------------------

    def price_of(self, displaced_credits: float, scarcity_multiplier: float) -> float:
        """PRICE = re-derivation cost x MARGIN x scarcity."""
        return displaced_credits * MARGIN * scarcity_multiplier

    def settle_question(self, result, *, buyer: str = "rookie", memory_kind: str = "episode") -> Trade:
        """Book one trade against a completed two-path ask.

        `result` is a `backend.memex.engine.AskResult`. Taking the whole result
        rather than loose numbers is what keeps the price provably tied to the
        run that produced it.
        """
        seller = owner_of(memory_kind)
        price = self.price_of(result.displaced_credits, result.scarcity_multiplier)
        saved = max(0.0, result.displaced_credits - price)

        buyer_agent = self._agents[buyer]
        seller_agent = self._agents[seller]
        buyer_agent.balance_credits -= price
        buyer_agent.spent_credits += price
        seller_agent.balance_credits += price
        seller_agent.earned_credits += price

        trade = Trade(
            id=uuid.uuid4().hex[:12],
            buyer=buyer,
            seller=seller,
            memory_kind=memory_kind,
            memory_subject=result.scarcity_condition or "(unknown condition)",
            question=result.query,
            tokens_displaced=result.tokens_displaced,
            scarcity_multiplier=result.scarcity_multiplier,
            price_credits=price,
            price_usd=pricing.usd_for(price),
            saved_credits=saved,
            saved_usd=pricing.usd_for(saved),
            model=result.cold.priced_as,
            ts=time.time(),
        )
        self.trades.append(trade)
        return trade

    def run_shock(self, result, *, destroyed: int = 1) -> ShockEvent:
        """Destroy the memory, then price the same question without it.

        Pre-shock is what the buyer paid while the memory existed. Post-shock is
        the full re-derivation cost - the buyer must now read every abstract at
        the premium rate, because nobody can sell them the digest. The spike is
        the ratio, and it is large precisely where the corpus is thin.
        """
        pre = self.price_of(result.displaced_credits, result.scarcity_multiplier)
        post = result.cold.credits
        event = ShockEvent(
            id=uuid.uuid4().hex[:12],
            condition=result.scarcity_condition or "(unknown condition)",
            question=result.query,
            destroyed=destroyed,
            pre_shock_credits=pre,
            post_shock_credits=post,
            spike=(post / pre) if pre > 0 else 0.0,
            tokens_re_derived=result.cold.prompt_tokens,
            scarcity_multiplier=result.scarcity_multiplier,
            ts=time.time(),
        )
        self.shocks.append(event)
        return event


_MARKET: Market | None = None


def get_market() -> Market:
    """Process-wide singleton."""
    global _MARKET
    if _MARKET is None:
        _MARKET = Market()
    return _MARKET
