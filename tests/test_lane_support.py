from shared.formats.registry import FormatRegistry, compatible


def test_compatible_only_for_supported_lane():
    reg = FormatRegistry()
    assert compatible(reg.get("explainer"), lane="monetization") is True
    assert compatible(reg.get("explainer"), lane="reach") is False


def test_all_eight_formats_load():
    reg = FormatRegistry()
    assert len(reg.all()) == 8
