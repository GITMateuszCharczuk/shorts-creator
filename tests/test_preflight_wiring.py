import json
import os
import time

import pytest

from shared.conductor.preflight import PreflightFailure, oauth_token_age_gate
from shared.conductor.subproc import StageOutcome
from shorts.run_batch import (
    _rmtree_guarded,
    build_preflight,
    historical_baseline,
    load_outcome_history,
    metered,
    post_batch_sweep,
    production_preflight,
)


def test_preflight_runs_all_gates_in_order():
    calls = []
    for g in build_preflight(hooks={k: (lambda k=k: calls.append(k)) for k in
                                    ["free_space", "host_health", "oauth", "youtube_quota",
                                     "data_budget"]}):
        g()
    assert calls == ["free_space", "host_health", "oauth", "youtube_quota", "data_budget"]


def test_build_preflight_rejects_unknown_hook_keys():
    with pytest.raises(ValueError, match="oauht"):           # typo guard: never silently no-op
        build_preflight(hooks={"oauht": lambda: None})


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


def _cfg_usage_for_quota(tmp_path, *, insert_units=None, planned_inserts, used_units):
    """A config/usage pair where ONLY the youtube_quota gate can fail — the other four gates pass —
    so a quota assertion is unambiguous. insert_units=None omits the config key (default path)."""
    budgets = {"youtube_units": 10000, "data_api": {}}
    if insert_units is not None:
        budgets["youtube_insert_units"] = insert_units
    cfg = {"gc": {"min_free_gb": 0.0},
           "hosts": {"comfy_url": "http://h:8188", "ollama_url": "http://h:11434"},
           "oauth_mode": "testing", "budgets": budgets}
    usage = {"token_age_days": 0.0, "last_used_days": 0.0,
             "youtube_used_units": used_units, "planned_inserts": planned_inserts,
             "data_api_used": {}, "data_api_planned": {}}
    return cfg, usage


def test_production_preflight_honors_config_youtube_insert_units(tmp_path):
    """B/A review follow-up: the per-insert quota cost is verify-at-bring-up and config-sourced.
    A batch of 6 inserts costs 9600 at the default 1600 (BLOCKS under a 10000/day quota), but only
    600 at a bring-up-verified 100 (PASSES). Drive it through the REAL production_preflight wiring,
    not a mock, so the cfg value actually reaches youtube_quota_gate."""
    # default cost (key absent) -> 6 * 1600 = 9600 > 10000? no, but +used pushes it over.
    cfg, usage = _cfg_usage_for_quota(tmp_path, planned_inserts=6, used_units=1000)
    with pytest.raises(PreflightFailure, match="YouTube quota"):     # 6*1600=9600, +1000 > 10000
        production_preflight(cfg=cfg, data_root=tmp_path, usage=usage,
                             http_get=lambda url: 200)()

    # SAME batch, but a config-supplied verified cost of 100 -> 6*100=600, +1000 fits -> passes.
    cfg, usage = _cfg_usage_for_quota(tmp_path, insert_units=100,
                                      planned_inserts=6, used_units=1000)
    production_preflight(cfg=cfg, data_root=tmp_path, usage=usage,
                         http_get=lambda url: 200)()    # no raise


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
                     outcomes_by_niche={"finance": {"v1": "done"}},
                     textfile_dir=tmp_path / ".metrics" / "textfile")
    assert active.exists() and resumed.exists() and history.exists() and models.exists()
    assert not old.exists()


def test_sweep_gcs_quarantine_and_cache_by_cfg_knobs(tmp_path):
    cfg = {"gc": {"keep_days": 7, "keep_count": 14, "quarantine_keep_days": 30, "cap_gb": 0.0}}
    old_q = _mk_dir(tmp_path, "quarantine/v-old", 40)
    young_q = _mk_dir(tmp_path, "quarantine/v-new", 5)
    cached = _mk_dir(tmp_path, ".cache/05/abc-42", 1)
    post_batch_sweep(tmp_path, batch_id="b1", resumed_ids=set(), cfg=cfg,
                     outcomes_by_niche={}, textfile_dir=tmp_path / ".metrics")
    assert not old_q.exists() and young_q.exists()     # 40d > 30d cap; 5d kept
    assert not cached.exists()                         # cap_gb=0 -> LRU evicts everything


def test_sweep_emits_the_batch_series_from_the_outcome_tally(tmp_path):
    cfg = {"gc": {"keep_days": 7, "keep_count": 14, "quarantine_keep_days": 30, "cap_gb": 50.0}}
    outcomes = {"v1": "done", "v2": "quarantined", "v3": "done", "v4": "failed"}
    post_batch_sweep(tmp_path, batch_id="b9", resumed_ids=set(), cfg=cfg,
                     outcomes_by_niche={"finance": outcomes}, textfile_dir=tmp_path / ".metrics")
    text = (tmp_path / ".metrics" / "batch-b9.prom").read_text()
    assert 'shorts_batch_videos_total{batch="b9",niche="finance"} 4' in text
    assert 'shorts_batch_quarantined_total{batch="b9",niche="finance"} 1' in text
    assert 'shorts_batch_failed_total{batch="b9",niche="finance"} 1' in text
    assert 'shorts_quarantine_rate{batch="b9",niche="finance"} 0.25' in text
    assert "shorts_quarantine_baseline" in text


def test_sweep_emits_one_labelled_block_per_niche_in_one_prom(tmp_path):
    """Batches span multiple niches (plan_batch's videos carry niche) — the QuarantineSpike alert
    is PER NICHE via labels, so each niche gets its own series in the single atomic batch file."""
    cfg = {"gc": {"keep_days": 7, "keep_count": 14, "quarantine_keep_days": 30, "cap_gb": 50.0}}
    post_batch_sweep(tmp_path, batch_id="b9", resumed_ids=set(), cfg=cfg,
                     outcomes_by_niche={
                         "finance": {"f1": "done", "f2": "quarantined"},
                         "travel": {"t1": "done", "t2": "done", "t3": "failed"}},
                     textfile_dir=tmp_path / ".metrics")
    text = (tmp_path / ".metrics" / "batch-b9.prom").read_text()
    assert 'shorts_batch_videos_total{batch="b9",niche="finance"} 2' in text
    assert 'shorts_quarantine_rate{batch="b9",niche="finance"} 0.5' in text
    assert 'shorts_batch_videos_total{batch="b9",niche="travel"} 3' in text
    assert 'shorts_batch_quarantined_total{batch="b9",niche="travel"} 0' in text
    assert 'shorts_batch_failed_total{batch="b9",niche="travel"} 1' in text


def test_quarantine_baseline_comes_from_cross_batch_history_not_this_batch(tmp_path):
    """A real batch is smaller than the trailing window, so a same-batch pre-window slice is
    always empty -> baseline 0.0 -> the rate > 2*baseline alert arm fires on ANY quarantine.
    The baseline must come from history/batches.jsonl (prior batches), per niche."""
    cfg = {"gc": {"keep_days": 7, "keep_count": 14, "quarantine_keep_days": 30, "cap_gb": 50.0}}
    hist = tmp_path / "history"
    hist.mkdir(parents=True)
    prior = ([{"video_id": f"finance-b1-{i}", "niche": "finance", "status": "quarantined"}
              for i in range(2)]
             + [{"video_id": f"finance-b1-{i+2}", "niche": "finance", "status": "done"}
                for i in range(18)]
             + [{"video_id": "travel-b1-0", "niche": "travel", "status": "quarantined"}])
    (hist / "batches.jsonl").write_text(
        "\n".join(json.dumps(e) for e in prior) + "\nnot-json\n")   # malformed line tolerated
    post_batch_sweep(tmp_path, batch_id="b2", resumed_ids=set(), cfg=cfg,
                     outcomes_by_niche={"finance": {"finance-b2-0": "quarantined"}},
                     textfile_dir=tmp_path / ".metrics")
    text = (tmp_path / ".metrics" / "batch-b2.prom").read_text()
    # 2 quarantined / 20-outcome window of PRIOR finance history — not this batch's 1/1
    assert 'shorts_quarantine_baseline{batch="b2",niche="finance"} 0.1' in text
    assert 'shorts_quarantine_rate{batch="b2",niche="finance"} 1.0' in text
    # and the sweep appended this batch's outcomes so the NEXT batch has a baseline
    assert load_outcome_history(tmp_path, niche="finance")[-1] == "quarantined"
    assert load_outcome_history(tmp_path, niche="travel") == ["quarantined"]


def test_outcome_history_loader_and_baseline_cold_start(tmp_path):
    assert load_outcome_history(tmp_path) == []                     # missing file -> []
    assert historical_baseline([], window=20) == 0.0                # cold start -> 0.0
    assert abs(historical_baseline(["done"] * 16 + ["quarantined"] * 4, window=20) - 0.2) < 1e-9


def test_sweep_removes_stale_stage_proms_but_never_the_fresh_or_batch_file(tmp_path):
    cfg = {"gc": {"keep_days": 7, "keep_count": 14, "quarantine_keep_days": 30, "cap_gb": 50.0}}
    tf = tmp_path / ".metrics"
    tf.mkdir(parents=True)
    stale = tf / "v-old-05.prom"
    stale.write_text("x")
    old_ts = time.time() - 10 * 86400
    os.utime(stale, (old_ts, old_ts))
    fresh = tf / "v-new-05.prom"
    fresh.write_text("x")
    post_batch_sweep(tmp_path, batch_id="b9", resumed_ids=set(), cfg=cfg,
                     outcomes_by_niche={}, textfile_dir=tf)
    assert not stale.exists()                          # 10d > keep_days=7
    assert fresh.exists()
    assert (tf / "batch-b9.prom").exists()             # the file the sweep itself writes


# --- _rmtree_guarded: defense-in-depth edges ---

def test_rmtree_guarded_refuses_to_delete_data_root_itself(tmp_path):
    with pytest.raises(ValueError):
        _rmtree_guarded(tmp_path, tmp_path)
    assert tmp_path.exists()


def test_rmtree_guarded_refuses_symlinks_and_keeps_the_target(tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "f").write_text("precious")
    (tmp_path / "runs").mkdir()
    evil = tmp_path / "runs" / "evil"
    evil.symlink_to(victim)                            # a symlink in runs/ is never legitimate
    with pytest.raises(ValueError):
        _rmtree_guarded(tmp_path, evil)
    assert victim.exists() and (victim / "f").read_text() == "precious"
