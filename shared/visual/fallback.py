from dataclasses import dataclass


@dataclass(frozen=True)
class AssetChoice:
    kind: str          # "stock" | "ai" | "card" | "hook_card"
    ref: str | None    # stock path when kind == "stock", else None


def choose_asset(*, beat: str, stock_ranked: list[tuple[str, float]], stock_threshold: float,
                 ai_available: bool, is_hook: bool) -> AssetChoice:
    if stock_ranked and stock_ranked[0][1] >= stock_threshold:
        return AssetChoice(kind="stock", ref=stock_ranked[0][0])
    if ai_available:
        return AssetChoice(kind="ai", ref=None)
    return AssetChoice(kind="hook_card" if is_hook else "card", ref=None)


# Note (ADR 0017 D4): the hook beat is invoked with a HIGH stock_threshold so the typographic
# card wins by default — stock/AI must demonstrably beat it. The denylist + abstract bias
# (ADR 0017 D2) are applied in the 01a search query, before ranking reaches choose_asset.
