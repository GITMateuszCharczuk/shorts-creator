import pytest

from shared.finance.grounding import (
    GroundingError,
    check_claims,
    resolve_ref,
    within_tolerance,
)


def test_resolve_ref_dotted_path():
    data = {"market": {"cpi_yoy": {"value": 3.2}}}
    assert resolve_ref(data, "market.cpi_yoy") == 3.2


def test_within_tolerance_percent_band():
    assert within_tolerance(3.21, 3.2) is True       # within 0.5%
    assert within_tolerance(3.5, 3.2) is False


def test_parse_money_and_percent():
    # "3.2%" and "$184.21" parse to 3.2 and 184.21
    data = {"market": {"cpi_yoy": {"value": 3.2}, "ACME_price": {"value": 184.21}}}
    claims = [{"value": "3.2%", "source_ref": "market.cpi_yoy"},
              {"value": "$184.21", "source_ref": "market.ACME_price"}]
    check_claims(claims, data)  # no raise


def test_ungrounded_ref_raises():
    with pytest.raises(GroundingError):
        check_claims([{"value": "9.9%", "source_ref": "market.nope"}], {"market": {}})


def test_out_of_tolerance_raises():
    with pytest.raises(GroundingError):
        check_claims([{"value": "5.0%", "source_ref": "market.cpi_yoy"}],
                     {"market": {"cpi_yoy": {"value": 3.2}}})


def test_bool_anchor_is_not_numeric():
    # a stray bool in data must never silently ground a claim to 1.0 (isinstance(True,int) is True)
    with pytest.raises(GroundingError):
        resolve_ref({"market": {"flag": {"value": True}}}, "market.flag")


@pytest.mark.parametrize("bad_claim", [
    {"value": "3.2%"},                       # no source_ref
    {"source_ref": "market.cpi_yoy"},        # no value
])
def test_malformed_claim_quarantines_not_crashes(bad_claim):
    with pytest.raises(GroundingError):
        check_claims([bad_claim], {"market": {"cpi_yoy": {"value": 3.2}}})
