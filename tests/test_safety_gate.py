from shared.safety.gate import aggregate
from shared.safety.types import CheckResult
from shared.schema import SchemaRegistry


def test_all_must_hold_and_payload_validates():
    payload = aggregate([CheckResult(True, "disclaimer"), CheckResult(True, "loudness", "ok")])
    SchemaRegistry().validate("qc", payload)             # incl. the detail field
    assert payload["passed"] is True


def test_one_failure_fails_the_gate_and_names_it():
    payload = aggregate([CheckResult(True, "disclaimer"),
                         CheckResult(False, "prohibited_claims", "phrase 'guaranteed'")])
    assert payload["passed"] is False
    assert any(c["name"] == "prohibited_claims" and not c["ok"] for c in payload["checks"])
