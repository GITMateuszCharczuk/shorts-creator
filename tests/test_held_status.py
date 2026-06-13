from shared.exitcodes import EXIT_HELD, status_for_exit


def test_held_exit_code_maps_to_held():
    assert EXIT_HELD == 70
    assert status_for_exit(70) == "held"
    assert status_for_exit(0) == "done" and status_for_exit(77) == "quarantined"   # M4 unchanged
