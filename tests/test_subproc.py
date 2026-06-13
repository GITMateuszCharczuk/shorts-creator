import sys

from shared.conductor.subproc import run_stage_subprocess


def test_outcome_maps_exit_codes(tmp_path):
    # use a trivial python -c as the command builder's stand-in via cmd_override
    ok = run_stage_subprocess(cmd=[sys.executable, "-c", "raise SystemExit(0)"], timeout_s=10)
    qr = run_stage_subprocess(cmd=[sys.executable, "-c", "raise SystemExit(77)"], timeout_s=10)
    assert (ok.status, qr.status) == ("done", "quarantined")


def test_timeout_kills_and_fails():
    out = run_stage_subprocess(cmd=[sys.executable, "-c", "import time; time.sleep(30)"],
                               timeout_s=1)
    assert out.status == "failed" and out.timed_out is True


def test_elapsed_recorded():
    out = run_stage_subprocess(cmd=[sys.executable, "-c", "raise SystemExit(0)"], timeout_s=10)
    assert out.elapsed_s >= 0.0
