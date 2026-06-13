from shared.conductor.executor import default_stage_order
from shared.runner import ORDER


def test_05b_06_placement():
    o = default_stage_order()
    assert o.index("05x") < o.index("05b") < o.index("06")   # vision -> safety -> distribute
    assert o.index("05c") < o.index("06") and o[-1] == "06"


def test_runner_order_matches_conductor_default_stage_order():
    """Guard against ORDER in runner.py drifting from default_stage_order() in executor.py.
    Both define the canonical 15-stage execution order; this test is the only enforcement."""
    assert list(ORDER) == default_stage_order()
