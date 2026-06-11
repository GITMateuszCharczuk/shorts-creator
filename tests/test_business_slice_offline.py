import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_business_niche_is_pure_config():
    from shared.config import resolve_config
    from shared.profiles.loader import load_profile
    fin = load_profile(ROOT / "profiles/finance/profile.yaml")
    biz = load_profile(ROOT / "profiles/business/profile.yaml")
    assert (fin["niche"], biz["niche"]) == ("finance", "business")
    # identical resolver call, different niche DATA -> different resolved config (no code branch)
    fin_cfg = resolve_config(global_defaults={"fps": 30}, niche=fin["defaults"], batch={},
                             per_platform={})
    biz_cfg = resolve_config(global_defaults={"fps": 30}, niche=biz["defaults"], batch={},
                             per_platform={})
    assert fin_cfg["music_index"] != biz_cfg["music_index"]
    assert fin_cfg["emphasis_hex"] != biz_cfg["emphasis_hex"]
    for p in (fin, biz):  # both personas + brand kits load + validate (ADR 0005 D9)
        assert {"palette", "font", "logo"} <= set(p["brand_kit"]) and p["persona"]["voice"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_dag_runs_niche_agnostic(run_dir, tmp_path):
    # the DAG carries no niche branch (enforced by test_no_platform_branches), so a run under any
    # niche produces a render — exercised here with the M1 fixture chain.
    from tests.helpers.m1 import run_m1_slice
    result = run_m1_slice(run_dir=run_dir, seed=11, fixtures=ROOT / "tests/fixtures/m1",
                          timing_log=tmp_path / "t.jsonl")
    assert (run_dir / result["render"]).exists()
