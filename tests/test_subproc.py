import sys

from shared.conductor.subproc import run_stage_subprocess, stage_cmd


def test_stage_cmd_builds_module_invocation_with_flags():
    # H5: stage_cmd is the argv builder for every stage launch — assert module + flags + values
    cmd = stage_cmd("05x", run_dir="/runs/r1", seed=42, config_json='{"input_paths": {}}')
    assert cmd[0] == sys.executable
    assert cmd[1:4] == ["-m", "shorts.stage", "05x"]   # python -m shorts.stage <stage_id>
    # flag/value pairs are passed through verbatim
    assert cmd[cmd.index("--run-dir") + 1] == "/runs/r1"
    assert cmd[cmd.index("--seed") + 1] == "42"        # seed stringified
    assert cmd[cmd.index("--config") + 1] == '{"input_paths": {}}'


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
