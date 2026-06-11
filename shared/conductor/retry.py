import time
from dataclasses import dataclass
from typing import Callable

from shared.conductor.subproc import StageOutcome


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = 2          # additional attempts after the first
    backoff_s: float = 30.0   # multiplied by the attempt number (linear backoff)


def run_with_retries(attempt: Callable[[], StageOutcome],
                     policy: RetryPolicy) -> tuple[StageOutcome, int]:
    """Retries only `failed` outcomes (transient). `quarantined` is a deliberate gate verdict —
    retrying it would re-spend GPU on a parked video."""
    attempts = 0
    while True:
        attempts += 1
        out = attempt()
        if out.status != "failed" or attempts > policy.retries:
            return out, attempts
        time.sleep(policy.backoff_s * attempts)
