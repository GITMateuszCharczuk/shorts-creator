from shared.exitcodes import EXIT_DEGRADED, EXIT_OK, EXIT_QUARANTINED, status_for_exit


def test_protocol_values_are_stable():
    assert (EXIT_OK, EXIT_DEGRADED, EXIT_QUARANTINED) == (0, 75, 77)


def test_status_mapping():
    assert status_for_exit(0) == "done"
    assert status_for_exit(75) == "done"          # degraded still completes (WARN, ADR 0009 #8)
    assert status_for_exit(77) == "quarantined"
    assert status_for_exit(1) == "failed"
