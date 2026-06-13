from shared.safety.probe import ProbeResult


def test_probe_result_carries_every_numeric_input_05b_needs():
    p = ProbeResult(integrated_lufs=-14.0, true_peak_dbtp=-1.4, silences=[(0.0, 0.1)],
                    black_spans=[], actual_s=30.0, projected_s=31.0,
                    cta_rect={"x": 120, "y": 900, "w": 600, "h": 200})
    assert p.integrated_lufs == -14.0 and p.cta_rect["w"] == 600
    assert isinstance(p.silences, list) and isinstance(p.black_spans, list)
