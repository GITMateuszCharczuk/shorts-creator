from stages.s01e_dataviz.stage import chart_spec


def test_chart_spec_from_data_series():
    data = {"market": {"cpi_yoy": {"value": 3.2}, "fed_funds": {"value": 4.5}}}
    spec = chart_spec(data, keys=["cpi_yoy", "fed_funds"], kind="bar",
                      brand={"accent": "#00E5FF"})
    assert spec["kind"] == "bar"
    assert spec["series"] == [{"label": "cpi_yoy", "value": 3.2},
                              {"label": "fed_funds", "value": 4.5}]
    assert spec["accent"] == "#00E5FF"
