---
title: Inference Architecture
---

# One model client, six call sites

All inference goes through one Cortex COMPLETE client. The `call_site` label separates purpose and cost without creating six provider integrations.

| Call site | Purpose |
|---|---|
| `hyde` | Expand the researcher query |
| `relevance_check` | Judge retrieved papers |
| `refine` | Rewrite a weak query |
| `summary` | Produce the sourced answer |
| `citation_check` | Verify claims against abstracts |
| `memory_distill` | Condense the researcher profile |

Every invocation records one ledger event, including degraded calls with zero usage. The dashboard therefore presents accounting, not an estimate.
