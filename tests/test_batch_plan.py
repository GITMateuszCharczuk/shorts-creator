import pytest

from shared.planner.batch import plan_batch
from shared.planner.topics import TopicStarvation
from shared.schema import SchemaError, SchemaRegistry


def test_plan_batch_is_valid_seeded_and_lane_mixed():
    fmts = [{"id": "surprising_stat", "lane_support": {"reach": True, "monetization": False}},
            {"id": "explainer", "lane_support": {"reach": False, "monetization": True}}]
    b = plan_batch(batch_id="2026-06-11", niches=["finance", "business"], per_niche=1,
                   formats=fmts, lane_history=[], topic_candidates=["cpi", "fed", "gold", "oil"],
                   ledger_topics=set(), monetization_share=0.20, master_seed=42)
    SchemaRegistry().validate("batch", b)
    assert len(b["videos"]) == 2
    assert {v["niche"] for v in b["videos"]} == {"finance", "business"}
    assert all(v["status"] == "pending" and isinstance(v["seed"], int) for v in b["videos"])
    # deterministic re-plan (same master seed -> same batch)
    assert b == plan_batch(
        batch_id="2026-06-11", niches=["finance", "business"], per_niche=1,
        formats=fmts, lane_history=[], topic_candidates=["cpi", "fed", "gold", "oil"],
        ledger_topics=set(), monetization_share=0.20, master_seed=42,
    )


def test_invalid_status_fails_schema_validation():
    """A batch dict with a video status 'exploded' (not in enum) fails SchemaRegistry.validate."""
    b = {
        "schema_version": "1.0.0",
        "batch_id": "2026-06-11",
        "monetization_share": 0.20,
        "videos": [
            {
                "video_id": "finance-2026-06-11-0",
                "niche": "finance",
                "format": "surprising_stat",
                "lane": "reach",
                "topic": "cpi",
                "seed": 12345,
                "status": "exploded",
            }
        ],
    }
    with pytest.raises(SchemaError):
        SchemaRegistry().validate("batch", b)


def test_too_few_topic_candidates_raises_topic_starvation():
    """plan_batch with too-few topic_candidates raises TopicStarvation (from claim_topics)."""
    fmts = [{"id": "surprising_stat", "lane_support": {"reach": True, "monetization": False}}]
    with pytest.raises(TopicStarvation):
        plan_batch(
            batch_id="2026-06-11",
            niches=["finance", "business"],
            per_niche=1,
            formats=fmts,
            lane_history=[],
            topic_candidates=["cpi"],   # only 1 candidate but need 2
            ledger_topics=set(),
            monetization_share=0.20,
            master_seed=42,
        )
