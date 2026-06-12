from collections import Counter


def build_report(*, posts: list[dict], quarantines: list[dict], feature_records: list[dict],
                 floor: float) -> dict:
    """The DoD clause-2 spot-audit (read-only). Disagreement is computed vs the LIVE floor
    (injected by the caller from config), not a hardcoded default — so a promoted floor isn't
    audited stale."""
    reasons = Counter(c for q in quarantines for c in q.get("failed_checks", []))
    disagree = [{"video_id": fr["video_id"], "score": fr["creative_qc_overall"],
                 "human_approved": fr["ramp_label"]["approved"]}
                for fr in feature_records if "ramp_label" in fr
                and "creative_qc_overall" in fr
                and (fr["creative_qc_overall"] >= floor) != fr["ramp_label"]["approved"]]
    return {"posted_count": len(posts), "quarantined_count": len(quarantines), "posts": posts,
            "quarantine_reasons": dict(reasons), "label_score_disagreement": disagree}
