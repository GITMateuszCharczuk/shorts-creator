"""M6 Task 12: the offline soak — N consecutive nightly batches through the REAL batch_flow
with injected faults (kill-mid-batch, stale lock, disk-low). Marked `soak`: runs under
`make soak` (SOAK_BATCHES=N, default 14), excluded from the default sweep alongside
`integration` (Makefile test: -m "not integration and not soak")."""
import os

import pytest

from tests.helpers.soak import run_offline_soak


@pytest.mark.soak
def test_soak_survives_n_batches_without_wedging(tmp_path):
    batches = int(os.environ.get("SOAK_BATCHES", "14"))
    assert batches >= 8, "SOAK_BATCHES must be >= 8 (faults inject on batches 3/5/8)"
    result = run_offline_soak(data_root=tmp_path, batches=batches, seed=1,
                              inject={"kill_mid_batch_on": 3, "stale_lock_on": 5,
                                      "disk_low_on": 8})
    assert result["wedges"] == 0 and result["silent_failures"] == 0
    assert result["batch_3_resumed"] and result["batch_5_took_over_stale_lock"]
    assert result["batch_8_halted_with_alert"]   # disk-low pre-flight HALTED, not quarantined
    assert result["ledger_monotonic"] and result["runs_within_retention"]
