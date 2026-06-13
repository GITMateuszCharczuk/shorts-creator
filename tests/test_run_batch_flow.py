from shorts.run_batch import batch_flow


def test_flow_order_and_lock_released_on_failure(tmp_path):
    calls = []

    def boom():
        calls.append("execute")
        raise RuntimeError("stage blew up")
    try:
        batch_flow(lock_path=tmp_path / "l", data_root=tmp_path,
                   preflight=lambda: calls.append("preflight"),
                   plan=lambda: calls.append("plan") or {"videos": []},
                   execute=lambda b: boom(),
                   commit=lambda b: calls.append("commit"),
                   backup=lambda: calls.append("backup"))
    except RuntimeError:
        pass
    assert calls == ["preflight", "plan", "execute"]   # commit/backup only after success
    assert not (tmp_path / "l").exists()               # lock ALWAYS released
