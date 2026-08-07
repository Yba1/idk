"""MemEx - the memory economy layer.

Additive package. Nothing in here edits a FROZEN file; everything reaches the
rest of the system through backend.contracts.ports, so the whole package runs
keyless on the `fake` profile.

  pricing.py       Snowflake Cortex Table 6(a) rates - the pricing oracle
  scarcity.py      IDF multiplier over corpus.json conditions
  engine.py        Tier 1: cold vs warm, measured and priced
  market.py        Tier 2: wallets, settlement, the scarcity shock
  everos_client.py MemoryPort implementation over EverOS (mock + real)
  seed_research.py deterministic seed sessions for the demo
  wire.py          attach(app) - the two-line hook into the FastAPI app
  standalone.py    zero-touch fallback: our own app on its own port
"""
