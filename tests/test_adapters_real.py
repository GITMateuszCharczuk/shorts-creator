import importlib
import importlib.util

import pytest

from shared.adapters import LLMBackend, TTSBackend
from shared.adapters.real import KokoroBackend, OllamaBackend


def test_ollama_satisfies_protocol():
    assert isinstance(OllamaBackend(base_url="http://h:11434", model="qwen2.5:14b-instruct"),
                      LLMBackend)


def test_kokoro_satisfies_protocol(tmp_path):
    assert isinstance(KokoroBackend(out_dir=tmp_path), TTSBackend)


def test_ollama_builds_generate_payload():
    be = OllamaBackend(base_url="http://h:11434", model="qwen2.5:14b-instruct")
    url, payload = be._request("hello")
    assert url == "http://h:11434/api/generate"
    assert payload == {"model": "qwen2.5:14b-instruct", "prompt": "hello", "stream": False}


def test_ollama_seeded_payload_sets_options_seed():
    be = OllamaBackend(base_url="http://h:11434", model="qwen2.5:14b-instruct")
    _, payload = be._request("hi", seed=7)
    assert payload["options"]["seed"] == 7   # best-of-N is reproducible (ADR 0009)


def test_real_module_imports_without_host_only_deps():
    # CI-safety guard (Task-0 review): real.py must import with kokoro/whisperx ABSENT — they are
    # host-only and imported lazily inside the method bodies. If either leaks to module top-level,
    # CI collection breaks. This env has neither installed, so a clean import proves the contract.
    assert importlib.util.find_spec("kokoro") is None
    importlib.import_module("shared.adapters.real")          # must not raise
    KokoroBackend(out_dir="/tmp/x")                          # construct without kokoro present


class _FakeResp:
    def __init__(self, body, text=""):
        self._body = body
        self.text = text

    def raise_for_status(self):
        pass

    def json(self):
        if self._body is _NON_JSON:
            raise ValueError("not json")
        return self._body


_NON_JSON = object()


def test_llm_clear_error_on_ollama_error_shape(monkeypatch):
    # a 200 with an error body must surface a clear ValueError, not a bare KeyError on ["response"]
    be = OllamaBackend(base_url="http://h:11434", model="m")
    monkeypatch.setattr("shared.adapters.real.httpx.post",
                        lambda *a, **k: _FakeResp({"error": "model not found"}))
    with pytest.raises(ValueError):
        be.llm("hi")


def test_llm_json_retries_then_raises_clear_error(monkeypatch):
    be = OllamaBackend(base_url="http://h:11434", model="m")
    calls = []
    monkeypatch.setattr("shared.adapters.real.httpx.post",
                        lambda *a, **k: calls.append(1) or _FakeResp({"response": "not json{"}))
    with pytest.raises(ValueError):
        be.llm_json("give me json")
    assert len(calls) == 2   # one repair retry, then raise (bounded)


def test_llm_json_succeeds_first_try(monkeypatch):
    be = OllamaBackend(base_url="http://h:11434", model="m")
    calls = []
    monkeypatch.setattr("shared.adapters.real.httpx.post",
                        lambda *a, **k: calls.append(1) or _FakeResp({"response": '{"ok": 1}'}))
    assert be.llm_json("x") == {"ok": 1}
    assert len(calls) == 1   # success returns immediately, no wasted retry


@pytest.mark.integration
def test_ollama_llm_live():
    be = OllamaBackend(base_url="http://127.0.0.1:11434", model="qwen2.5:14b-instruct")
    assert isinstance(be.llm("Reply with the single word OK."), str)
