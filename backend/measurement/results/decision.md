# Step 2 Measurement Gate Decision

| Candidate | Tokens after | Tokens before | Reduction |
|---|---|---|---|
| A - search loop calls (proxy vs direct chat) | 1442 | 1434 | -0.56% |
| B - sourced-summary call (compress_for_prompt) | 2458 | 4159 | 40.9% |

Note: Candidate A's "before/after" columns compare the proxy's auto-detected
chat completion tokens against a direct (unproxied) call. Candidate B's
columns compare compress_for_prompt's original vs compressed token counts on
the stuffed-abstracts context, since that is the only call site production
actually routes through Paritok's compression pipeline.

Threshold: 15.0% reduction to count as a winning compression surface.

**Winner: candidate_b_summary**

Multi-turn session (final cumulative prompt tokens, 6 turns):
proxied 565, direct 565.
