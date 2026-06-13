import httpx  # noqa: F401

_COMMERCIAL_SAFE = {"Pexels", "Pixabay", "Mixkit", "Coverr", "Videvo-Free"}


def license_ok(license_name: str) -> bool:
    return license_name in _COMMERCIAL_SAFE


def provenance_record(*, asset_id: str, source: str, url: str, license: str,
                      fetch_date: str) -> dict:
    return {"asset_id": asset_id, "source": source, "url": url,
            "license": license, "fetch_date": fetch_date}


class StockClient:
    """Pulls N vertical candidates per query from commercial-safe libraries (host/integration)."""

    def __init__(self, providers: dict[str, str]):  # {provider: api_key}
        self._providers = providers

    def search(self, query: str, n: int) -> list[dict]:
        raise NotImplementedError("live provider HTTP wired at integration bring-up; "
                                  "01a CI uses fixture candidates")
