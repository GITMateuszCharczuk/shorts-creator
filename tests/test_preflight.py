import pytest

from shared.conductor.preflight import PreflightFailure, free_space_gate, run_preflight


def test_free_space_gate_fails_below_minimum(tmp_path):
    with pytest.raises(PreflightFailure):
        free_space_gate(tmp_path, min_free_gb=10**9)   # absurd requirement -> fail


def test_pluggable_checks_run_in_order(tmp_path):
    calls = []
    run_preflight([lambda: calls.append("a"), lambda: calls.append("b")])
    assert calls == ["a", "b"]                    # OAuth token-age slots in here at M5


def test_host_health_gate_fails_on_unhealthy_service():
    from shared.conductor.preflight import host_health_gate
    healthy = {"http://h:8188/system_stats": 200, "http://h:11434/api/version": 200}
    host_health_gate(comfy_url="http://h:8188", ollama_url="http://h:11434",
                     get=lambda u: healthy[u])    # no raise
    with pytest.raises(PreflightFailure):
        host_health_gate(comfy_url="http://h:8188", ollama_url="http://h:11434",
                         get=lambda u: 503)       # fail fast — no retry-storm (ADR 0003 D2)
