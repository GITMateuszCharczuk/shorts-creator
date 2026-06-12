from shared.conductor.preflight import PreflightFailure


def data_api_budget_gate(*, used: dict, planned: dict, budgets: dict) -> None:
    """Open #10. A source with no budget entry is keyless/free (FRED/stooq) — never blocks. A
    capped source (Alpha Vantage) fails the batch BEFORE fan-out if it would overrun the day's
    cap."""
    for src, cap in budgets.items():
        if used.get(src, 0) + planned.get(src, 0) > cap:
            raise PreflightFailure(
                f"{src} budget: {used.get(src, 0)}+{planned.get(src, 0)} > {cap}")
