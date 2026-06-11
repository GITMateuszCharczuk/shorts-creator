from shared.visual.stock import license_ok, provenance_record


def test_provenance_record_shape():
    r = provenance_record(asset_id="px_1", source="pexels", url="https://p/1",
                          license="Pexels", fetch_date="2026-06-09")
    assert r == {"asset_id": "px_1", "source": "pexels", "url": "https://p/1",
                 "license": "Pexels", "fetch_date": "2026-06-09"}


def test_license_gate_rejects_unknown():
    assert license_ok("Pexels") is True
    assert license_ok("Unknown-NC") is False
