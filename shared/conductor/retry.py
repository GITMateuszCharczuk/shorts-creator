import time
from dataclasses import dataclass
from typing import Callable

from shared.conductor.subproc import StageOutcome


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = 2          # additional attempts after the first
    backoff_s: float = 30.0   # multiplied by the attempt number (linear backoff)


def run_with_retries(attempt: Callable[[], StageOutcome],
                     policy: RetryPolicy,
                     *, sleep: Callable[[float], None] = time.sleep) -> tuple[StageOutcome, int]:
    """Retries only `failed` outcomes (transient). `quarantined` is a deliberate gate verdict —
    retrying it would re-spend GPU on a parked video. `sleep` is injectable (consistent with the
    codebase's IO-injection pattern) so tests need not pass backoff_s=0 to avoid real waits."""
    attempts = 0
    while True:
        attempts += 1
        out = attempt()
        if out.status != "failed" or attempts > policy.retries:
            return out, attempts
        sleep(policy.backoff_s * attempts)
