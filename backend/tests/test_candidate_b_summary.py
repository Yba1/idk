from backend.measurement.candidate_b_summary import run_candidate_b


def test_run_candidate_b_computes_reduction():
    # run_candidate_b measures compress_for_prompt directly against the real
    # corpus (Step 4.3's actual usage pattern) - it doesn't call client.chat,
    # so no client mock can drive its numbers. Assert the invariants that must
    # hold regardless of whether the Paritok GPU compression endpoint is
    # reachable in this environment (it degrades to passthrough when it isn't).
    result = run_candidate_b()

    assert result["direct_prompt_tokens"] > 0
    assert 0 <= result["proxied_prompt_tokens"] <= result["direct_prompt_tokens"]

    expected_reduction = round(
        (result["direct_prompt_tokens"] - result["proxied_prompt_tokens"])
        / result["direct_prompt_tokens"] * 100,
        2,
    )
    assert result["reduction_pct"] == expected_reduction
    assert 0.0 <= result["reduction_pct"] <= 100.0
