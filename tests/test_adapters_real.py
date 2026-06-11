import importlib
import importlib.util

import pytest

from shared.adapters import ModelBackend
from shared.adapters.real import KokoroBackend, OllamaBackend


def test_ollama_satisfies_protocol():
    assert isinstance(OllamaBackend(base_url="http://h:11434", model="qwen2.5:14b-instruct"),
                      ModelBackend)


def test_kokoro_satisfies_protocol(tmp_path):
    assert isinstance(KokoroBackend(out_dir=tmp_path), ModelBackend)


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


@pytest.mark.integration
def test_ollama_llm_live():
    be = OllamaBackend(base_url="http://127.0.0.1:11434", model="qwen2.5:14b-instruct")
    assert isinstance(be.llm("Reply with the single word OK."), str)
