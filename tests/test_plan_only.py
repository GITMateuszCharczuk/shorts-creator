"""M7 Variant B (ADR 0015a D1): `shorts.run_batch --plan-only` — the Argo CronWorkflow's `plan`
step. It must PLAN (batch.json + per-video job.json + the video_ids the withParam fan-out iterates)
WITHOUT running any stage or touching the `_build_backends` GPU/LLM bring-up seam. Planner inputs
are config-sourced (a resolved-config dict / --config file) so this is runnable with no cluster.
"""
import json

import pytest

from shared.planner.batch import plan_batch
from shorts.run_batch import main, plan_only

# A minimal but real resolved-config: a couple niches, a lane-mixed formats list with enough
# reach-lane formats that the anti-repeat exclusion (pick_format excludes recent[-3:]) never
# starves across the mostly-reach 4-video batch (monetization_share=0.20), plus a few fresh topics.
FORMATS = [
    {"id": "myth_buster", "lane_support": {"reach": False, "monetization": True}},
    {"id": "explainer", "lane_support": {"reach": False, "monetization": True}},
    {"id": "surprising_stat", "lane_support": {"reach": True, "monetization": False}},
    {"id": "news_reaction", "lane_support": {"reach": True, "monetization": False}},
    {"id": "quick_take", "lane_support": {"reach": True, "monetization": False}},
    {"id": "deep_dive", "lane_support": {"reach": True, "monetization": False}},
]


def _cfg(batch_id="2026-06-13"):
    return {
        "batch_id": batch_id,
        "niches": ["finance", "business"],
        "per_niche": 2,
        "formats": FORMATS,
        "lane_history": [],
        "topic_candidates": ["cpi", "fed", "gold", "oil", "rates", "etfs"],
        "ledger_topics": [],
        "monetization_share": 0.20,
        "master_seed": 42,
    }


def test_plan_only_writes_batch_json_matching_plan_batch(tmp_path):
    cfg = _cfg()
    plan_only(data_root=tmp_path, cfg=cfg)

    batch_path = tmp_path / "runs" / cfg["batch_id"] / "batch.json"
    assert batch_path.exists()
    written = json.loads(batch_path.read_text())

    expected = plan_batch(
        batch_id=cfg["batch_id"], niches=cfg["niches"], per_niche=cfg["per_niche"],
        formats=cfg["formats"], lane_history=cfg["lane_history"],
        topic_candidates=cfg["topic_candidates"], ledger_topics=set(),
        monetization_share=cfg["monetization_share"], master_seed=cfg["master_seed"])
    assert written == expected
    assert len(written["videos"]) == 4


def test_plan_only_emits_video_ids_array_for_withparam(tmp_path):
    cfg = _cfg()
    batch = plan_only(data_root=tmp_path, cfg=cfg)
    planned_ids = [v["video_id"] for v in batch["videos"]]

    # per-batch + stable well-known copy Argo's outputs.parameters.valueFrom.path reads.
    for ids_file in (tmp_path / "runs" / cfg["batch_id"] / "video_ids.json",
                     tmp_path / "runs" / "latest" / "video_ids.json"):
        ids = json.loads(ids_file.read_text())
        assert isinstance(ids, list) and ids == planned_ids
        # JSON array string is what Argo's withParam iterates.

    # stable batch_id source for the fanout's arguments.parameters.
    assert (tmp_path / "runs" / "latest" / "batch_id.txt").read_text().strip() == cfg["batch_id"]


def test_plan_only_writes_job_json_with_resolved_profile(tmp_path):
    cfg = _cfg()
    batch = plan_only(data_root=tmp_path, cfg=cfg)
    for video in batch["videos"]:
        job_path = tmp_path / "runs" / cfg["batch_id"] / video["video_id"] / "job.json"
        assert job_path.exists()
        job = json.loads(job_path.read_text())
        # the exact read 05b performs (ADR 0010 D5) — the resolved profile must be injected.
        assert job["profile"]["defaults"]["disclaimer"]
        assert job["profile"]["niche"] == video["niche"]
        assert job["video_id"] == video["video_id"]


def test_plan_only_runs_no_stages_no_backends(tmp_path):
    # No run dir / stage outputs beyond the plan artifacts; specifically the lock is never taken.
    plan_only(data_root=tmp_path, cfg=_cfg())
    assert not (tmp_path / ".batch.lock").exists()


def test_main_plan_only_via_config_file(tmp_path, monkeypatch):
    cfg = _cfg("2026-06-14")
    cfg_path = tmp_path / "plan_config.json"
    cfg_path.write_text(json.dumps(cfg))
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))

    assert main(["--plan-only", "--config", str(cfg_path)]) == 0
    batch = json.loads((tmp_path / "data" / "runs" / cfg["batch_id"] / "batch.json").read_text())
    assert len(batch["videos"]) == 4


def test_main_plan_only_requires_config(monkeypatch):
    monkeypatch.delenv("PLAN_CONFIG", raising=False)
    with pytest.raises(SystemExit):
        main(["--plan-only"])
