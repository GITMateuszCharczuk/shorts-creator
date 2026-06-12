import pytest

from shared.conductor.preflight import PreflightFailure
from shared.ops.budgets import data_api_budget_gate


def test_keyless_sources_never_block():
    data_api_budget_gate(used={}, planned={"fred": 10, "stooq": 10}, budgets={})


def test_capped_source_blocks_over_budget():
    with pytest.raises(PreflightFailure):
        data_api_budget_gate(used={"alpha_vantage": 24}, planned={"alpha_vantage": 5},
                             budgets={"alpha_vantage": 25})
