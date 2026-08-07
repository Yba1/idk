import pytest

pytest.skip(
    "backend/measurement/multiturn_session.py (Card 1's file, backend/measurement/** is not "
    "Card 2A's to edit) still imports the deleted backend.app.llm_client.ParitokLLMClient and "
    "measures a Paritok-era proxied-vs-direct token comparison with no v2 equivalent - Paritok "
    "was removed entirely per plan-v2/00-SHARED-CONTRACTS.md section 0. Card 2A owns this test "
    "file per scripts/ownership.txt but not the module under test. See Blockers.md.",
    allow_module_level=True,
)
