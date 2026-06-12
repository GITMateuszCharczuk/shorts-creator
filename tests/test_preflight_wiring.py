import os
import time

import pytest

from shared.conductor.preflight import PreflightFailure, oauth_token_age_gate
from shared.conductor.subproc import StageOutcome
from shorts.run_batch import build_preflight, metered, post_batch_sweep, production_preflight


def test_preflight_runs_all_gates_in_order():
    calls = []
    for g in build_preflight(hooks={k: (lambda k=k: calls.append(k)) for k in
                                    ["free_space", "host_health", "oauth", "youtube_quota",
                                     "data_budget"]}):
        g()
    assert calls == ["free_space", "host_health", "oauth", "youtube_quota", "data_budget"]


def test_wiring_invokes_the_REAL_oauth_gate_not_a_stub():
    # the seam must call the actual M5 gate with the resolved mode/age, not a no-op
    gates = build_preflight(hooks={"oauth": lambda: oauth_token_age_gate(token_age_days=8.0,
                                                                         mode="testing")})
    with pytest.raises(PreflightFailure):
        for g in gates:
            g()


def test_production_preflight_composes_the_real_gates_config_driven(tmp_path):
    """main()'s composition: the five real gates from cfg+usage, run in order by ONE closure
    (batch_flow calls preflight() once). An 8-day testing token must fail via the REAL M5 gate
    after free_space/host_health pass."""
    cfg = {"gc": {"min_free_gb": 0.0},
           "hosts": {"comfy_url": "http://h:8188", "ollama_url": "http://h:11434"},
           "oauth_mode": "testing",
           "budgets": {"youtube_units": 10000, "data_api": {"alpha_vantage": 25}}}
    usage = {"token_age_days": 8.0, "last_used_days": 0.0,
             "youtube_used_units": 0, "planned_inserts": 1,
             "data_api_used": {}, "data_api_planned": {}}
    preflight = production_preflight(cfg=cfg, data_root=tmp_path, usage=usage,
                                     http_get=lambda url: 200)
    with pytest.raises(PreflightFailure, match="OAuth token 8.0d"):
        preflight()


# --- metered: per-stage .prom emission around the M4 run_stage (Task 1 Step 3 + StageSlow) ---

def test_metered_writes_stage_metrics_and_slow_gauge(tmp_path):
    out = StageOutcome(status="done", exit_code=0, elapsed_s=9.0)
    wrapped = metered(lambda v, s: out, batch_id="b1", textfile_dir=tmp_path,
                      baselines={"05": 4.0})
    assert wrapped("v1", "05") is out                  # outcome passes through untouched
    text = (tmp_path / "v1-05.prom").read_text()
    assert 'shorts_stage_duration_seconds{batch="b1",stage="05",video="v1"} 9.0' in text
    assert 'shorts_stage_status{batch="b1",stage="05",video="v1",status="done"} 1' in text
    assert 'shorts_stage_slow{batch="b1",stage="05",video="v1"} 1' in text   # 9.0 > 4.0*1.5


def test_metered_without_baseline_emits_slow_zero(tmp_path):
    out = StageOutcome(status="done", exit_code=0, elapsed_s=9.0)
    metered(lambda v, s: out, batch_id="b1", textfile_dir=tmp_path)("v1", "02")
    assert 'shorts_stage_slow{batch="b1",stage="02",video="v1"} 0' in (
        tmp_path / "v1-02.prom").read_text()


# --- post_batch_sweep: GC after backup() + the batch-level series the alerts read ---

def _mk_dir(root, rel, age_days):
    p = root / rel
    p.mkdir(parents=True)
    (p / "f").write_text("x")
    old = time.time() - age_days * 86400
    os.utime(p, (old, old))
    return p


def test_sweep_deletes_old_runs_but_protects_active_resumed_history_models(tmp_path):
    cfg = {"gc": {"keep_days": 7, "keep_count": 1, "quarantine_keep_days": 30, "cap_gb": 50.0}}
    active = _mk_dir(tmp_path, "runs/b9", 0)
    resumed = _mk_dir(tmp_path, "runs/b8", 10)         # reconciler just re-ran it
    old = _mk_dir(tmp_path, "runs/b1", 10)
    history = _mk_dir(tmp_path, "history", 99)
    models = _mk_dir(tmp_path, "models", 99)
    post_batch_sweep(tmp_path, batch_id="b9", resumed_ids={"b8"}, cfg=cfg,
                     outcomes={"v1": "done"}, niche="finance",
                     textfile_dir=tmp_path / ".metrics" / "textfile")
    assert active.exists() and resumed.exists() and history.exists() and models.exists()
    assert not old.exists()


def test_sweep_gcs_quarantine_and_cache_by_cfg_knobs(tmp_path):
    cfg = {"gc": {"keep_days": 7, "keep_count": 14, "quarantine_keep_days": 30, "cap_gb": 0.0}}
    old_q = _mk_dir(tmp_path, "quarantine/v-old", 40)
    young_q = _mk_dir(tmp_path, "quarantine/v-new", 5)
    cached = _mk_dir(tmp_path, ".cache/05/abc-42", 1)
    post_batch_sweep(tmp_path, batch_id="b1", resumed_ids=set(), cfg=cfg,
                     outcomes={}, niche="finance", textfile_dir=tmp_path / ".metrics")
    assert not old_q.exists() and young_q.exists()     # 40d > 30d cap; 5d kept
    assert not cached.exists()                         # cap_gb=0 -> LRU evicts everything


def test_sweep_emits_the_batch_series_from_the_outcome_tally(tmp_path):
    cfg = {"gc": {"keep_days": 7, "keep_count": 14, "quarantine_keep_days": 30, "cap_gb": 50.0}}
    outcomes = {"v1": "done", "v2": "quarantined", "v3": "done", "v4": "failed"}
    post_batch_sweep(tmp_path, batch_id="b9", resumed_ids=set(), cfg=cfg, outcomes=outcomes,
                     niche="finance", textfile_dir=tmp_path / ".metrics")
    text = (tmp_path / ".metrics" / "batch-b9.prom").read_text()
    assert 'shorts_batch_videos_total{batch="b9",niche="finance"} 4' in text
    assert 'shorts_batch_quarantined_total{batch="b9",niche="finance"} 1' in text
    assert 'shorts_batch_failed_total{batch="b9",niche="finance"} 1' in text
    assert 'shorts_quarantine_rate{batch="b9",niche="finance"} 0.25' in text
    assert "shorts_quarantine_baseline" in text
