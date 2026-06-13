"""M6 closeout (f): resolved-profile injection into the per-video job contract.

05b reads job["profile"]["defaults"]["disclaimer"/"denylist_terms"] (the RESOLVED profile dict,
ADR 0010 D5) — but only the CI fake runner (shared/runner.py) ever injected it; no production
code authored job["profile"], so the first real run would KeyError. build_job is the tested
job.json author the bring-up seam (shorts.run_batch._build_backends) must use.
"""
from pathlib import Path

import pytest

from shared.planner.batch import build_job
from shared.profiles.loader import load_profile

ROOT = Path(__file__).resolve().parents[1]


def _video(niche="finance", seed=7):
    return {"video_id": f"{niche}-b1-0", "niche": niche, "format": "myth_buster",
            "lane": "monetization", "topic": "fees", "seed": seed, "status": "pending"}


def test_build_job_injects_the_resolved_profile_05b_reads():
    job = build_job(_video("finance"), batch_id="b1")
    want = load_profile(ROOT / "profiles" / "finance" / "profile.yaml")
    # the exact reads stages/s05b_safety/stage.py performs
    assert job["profile"]["defaults"]["disclaimer"] == want["defaults"]["disclaimer"]
    assert job["profile"]["defaults"]["denylist_terms"] == want["defaults"]["denylist_terms"]
    assert job["profile"]["defaults"]["denylist_terms"]    # non-empty in the real profile


def test_build_job_resolves_per_niche():
    fin = build_job(_video("finance"), batch_id="b1")
    biz = build_job(_video("business"), batch_id="b1")
    assert fin["profile"]["niche"] == "finance" and biz["profile"]["niche"] == "business"
    assert fin["profile"]["defaults"]["disclaimer"] != biz["profile"]["defaults"]["disclaimer"]


def test_build_job_produces_the_full_job_spine():
    job = build_job(_video("finance", seed=424242), batch_id="2026-06-12",
                    platform_targets=["youtube", "tiktok"])
    assert job["schema_version"] == "1.0.0"
    assert job["batch_id"] == "2026-06-12" and job["video_id"] == "finance-b1-0"
    assert job["niche"] == "finance" and job["seed"] == 424242
    assert job["platform_targets"] == ["youtube", "tiktok"]
    assert job["stages"] == {} and job["paths"] == {}      # stages own their sections (ADR 0012)


def test_build_job_defaults_platform_targets_to_youtube():
    assert build_job(_video(), batch_id="b1")["platform_targets"] == ["youtube"]


def test_build_job_unknown_niche_fails_loud():
    with pytest.raises(ValueError, match="cooking"):
        build_job(_video("cooking"), batch_id="b1")


def test_build_job_honors_an_explicit_profiles_root(tmp_path):
    with pytest.raises(ValueError, match="finance"):       # empty root: even finance is unknown
        build_job(_video("finance"), batch_id="b1", profiles_root=tmp_path)
