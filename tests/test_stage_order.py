from shared.conductor.executor import default_stage_order


def test_05b_06_placement():
    o = default_stage_order()
    assert o.index("05x") < o.index("05b") < o.index("06")   # vision -> safety -> distribute
    assert o.index("05c") < o.index("06") and o[-1] == "06"
