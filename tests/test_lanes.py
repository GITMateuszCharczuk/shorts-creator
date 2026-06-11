from shared.planner.lanes import next_lane


def test_under_target_monetization_share_picks_monetization():
    history = ["reach"] * 19 + ["monetization"]          # 5% < the 20% target
    assert next_lane(history, monetization_share=0.20) == "monetization"


def test_at_or_over_target_picks_reach():
    history = ["reach"] * 16 + ["monetization"] * 4      # exactly 20%
    assert next_lane(history, monetization_share=0.20) == "reach"


def test_empty_history_starts_with_reach():
    assert next_lane([], monetization_share=0.20) == "reach"   # PoC posture: reach-first
