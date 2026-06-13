import pytest

from shared.conductor.preflight import PreflightFailure, youtube_quota_gate


def test_quota_gate_blocks_when_a_batch_wont_fit():
    # insert ~1600 units; a 4-video batch needs ~6400 + headroom
    youtube_quota_gate(used_units=0, planned_inserts=4, daily_quota=10000)     # ok
    with pytest.raises(PreflightFailure):
        # 6400 units needed > 4000 left
        youtube_quota_gate(used_units=6000, planned_inserts=4, daily_quota=10000)
