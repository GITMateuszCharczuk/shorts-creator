from shared.conductor.retry import RetryPolicy, run_with_retries
from shared.conductor.subproc import StageOutcome


def _attempts(seq):
    it = iter(seq)
    return lambda: next(it)


def test_retries_failed_then_succeeds():
    seq = [StageOutcome("failed", 1, 0.1), StageOutcome("done", 0, 0.1)]
    out, attempts = run_with_retries(_attempts(seq), RetryPolicy(retries=2, backoff_s=0))
    assert out.status == "done" and attempts == 2


def test_quarantine_is_never_retried():
    seq = [StageOutcome("quarantined", 77, 0.1), StageOutcome("done", 0, 0.1)]
    out, attempts = run_with_retries(_attempts(seq), RetryPolicy(retries=3, backoff_s=0))
    assert out.status == "quarantined" and attempts == 1   # a gate verdict is final


def test_exhausted_retries_stay_failed():
    seq = [StageOutcome("failed", 1, 0.1)] * 3
    out, attempts = run_with_retries(_attempts(seq), RetryPolicy(retries=2, backoff_s=0))
    assert out.status == "failed" and attempts == 3
