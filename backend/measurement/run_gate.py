"""Runs the Step 2 measurement gate for real (live Groq/Paritok calls) and
writes the decision artifacts. Run manually once corpus.json exists:
    python -m backend.measurement.run_gate
Loads .env the same way backend/smoke_test.py does, internally, so the key
never passes through a Claude-visible tool call.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
with open(root / ".env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip()

import time

from backend.app.llm_client import ParitokLLMClient, _get_compression_pipeline  # noqa: E402
from backend.measurement.candidate_a_loop import run_candidate_a  # noqa: E402
from backend.measurement.candidate_b_summary import run_candidate_b  # noqa: E402
from backend.measurement.multiturn_session import run_multiturn_session  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
THRESHOLD_PCT = 15.0

# GPU_SERVER_WARMUP_TIMEOUT_S generously covers the ~45.5s cold start already
# measured (plan/paritok-feedback.md #2); production's own 8s interactive
# deadline in compress_for_prompt is untouched, this only warms the GPU up
# before candidate B's batch measurement so it isn't unlucky enough to poll
# entirely inside the cold-start window like the first live run was.
GPU_SERVER_WARMUP_TIMEOUT_S = 90.0
GPU_SERVER_WARMUP_POLL_S = 5.0


def _wait_for_gpu_server() -> None:
    """Poll Paritok's GET /test health check until the GPU backend reports ready.

    A no-op when running against the local Ollama backend (use_gpu_server: false),
    since LocalModelStrategy has no .check().
    """
    strategy = _get_compression_pipeline()._model
    if not hasattr(strategy, "check"):
        return

    deadline = time.time() + GPU_SERVER_WARMUP_TIMEOUT_S
    while time.time() < deadline:
        available, message = strategy.check()
        if available:
            print("GPU server ready.")
            return
        print(f"Waiting for GPU server ({message or 'not ready'})...")
        time.sleep(GPU_SERVER_WARMUP_POLL_S)
    print("GPU server did not report ready within the warm-up window; proceeding anyway.")


def decide(candidate_a: dict, candidate_b: dict) -> str:
    a_wins = candidate_a["reduction_pct"] > THRESHOLD_PCT
    b_wins = candidate_b["reduction_pct"] > THRESHOLD_PCT
    if a_wins and (not b_wins or candidate_a["reduction_pct"] >= candidate_b["reduction_pct"]):
        return "candidate_a_loop"
    if b_wins:
        return "candidate_b_summary"
    return "fallback_summary"  # neither cleared 15% - plan.md Step 2.3 fallback


def main() -> None:
    client = ParitokLLMClient()
    candidate_a = run_candidate_a(client)
    _wait_for_gpu_server()
    candidate_b = run_candidate_b()
    session = run_multiturn_session(client)
    winner = decide(candidate_a, candidate_b)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "candidate_a_loop": candidate_a,
        "candidate_b_summary": candidate_b,
        "multiturn_session": session,
        "winner": winner,
        "threshold_pct": THRESHOLD_PCT,
    }
    (RESULTS_DIR / "candidate_results.json").write_text(json.dumps(results, indent=2))

    decision_md = f"""# Step 2 Measurement Gate Decision

| Candidate | Tokens after | Tokens before | Reduction |
|---|---|---|---|
| A - search loop calls (proxy vs direct chat) | {candidate_a['proxied_prompt_tokens']} | {candidate_a['direct_prompt_tokens']} | {candidate_a['reduction_pct']}% |
| B - sourced-summary call (compress_for_prompt) | {candidate_b['proxied_prompt_tokens']} | {candidate_b['direct_prompt_tokens']} | {candidate_b['reduction_pct']}% |

Note: Candidate A's "before/after" columns compare the proxy's auto-detected
chat completion tokens against a direct (unproxied) call. Candidate B's
columns compare compress_for_prompt's original vs compressed token counts on
the stuffed-abstracts context, since that is the only call site production
actually routes through Paritok's compression pipeline.

Threshold: {THRESHOLD_PCT}% reduction to count as a winning compression surface.

**Winner: {winner}**

Multi-turn session (final cumulative prompt tokens, {len(session['proxied_cumulative'])} turns):
proxied {session['proxied_cumulative'][-1]}, direct {session['direct_cumulative'][-1]}.
"""
    (RESULTS_DIR / "decision.md").write_text(decision_md)
    print(f"Winner: {winner}")
    print(f"Candidate A reduction: {candidate_a['reduction_pct']}%")
    print(f"Candidate B reduction: {candidate_b['reduction_pct']}%")


if __name__ == "__main__":
    main()
