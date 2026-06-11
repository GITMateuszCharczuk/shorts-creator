import json
import os
from dataclasses import dataclass, field

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


class BudgetExceeded(Exception):
    """A free-tier API budget was exhausted for the batch."""


@dataclass
class Budget:
    limit: int
    spent: dict[str, int] = field(default_factory=dict)

    def spend(self, api: str) -> None:
        n = self.spent.get(api, 0) + 1
        if n > self.limit:
            raise BudgetExceeded(api)
        self.spent[api] = n


def corroborated(topic: str, news: list[dict], min_sources: int = 2) -> bool:
    # ADR 0009: a story needs >=min_sources DISTINCT sources whose item is ABOUT `topic`
    # (title/summary match) — not merely global source diversity across unrelated items.
    t = topic.lower()
    sources = {n["source"] for n in news
               if t in (n.get("title", "") + " " + n.get("summary", "")).lower()}
    return len(sources) >= min_sources


@stage(StageManifest(id="00a", inputs=[], outputs=["data"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    # M1: live fetch behind env keys; falls back to the committed fixture when keys absent
    # (keeps the slice runnable + the stage CI-testable). Real HTTP client lives here.
    fixture = ctx.config.get("data_fixture")
    if fixture:
        data = json.loads((ctx.run_dir / fixture).read_text())
    else:
        data = _fetch_live(ctx)  # uses httpx + Budget; raises -> ctx.degrade on partial
    out = ctx.write_output("data")
    out.write_text(json.dumps(data))
    ctx.log.info("data written", market_series=len(data["market"]), news=len(data["news"]))
    return StageResult(outputs={"data": out})


def _fetch_live(ctx: StageContext) -> dict:
    import httpx  # noqa
    _budget = Budget(limit=int(os.environ.get("AV_DAILY_LIMIT", "25")))
    # ... per-series Alpha Vantage / FRED pulls, each guarded by _budget.spend(...),
    # news via feedparser over the niche RSS list, filtered to <=3 days, corroboration-checked.
    # On any series failure: ctx.degrade("market pull failed: <series>") (first-class DAG state).
    raise NotImplementedError(
        "live fetch wired during integration bring-up; M1 CI uses data_fixture"
    )
