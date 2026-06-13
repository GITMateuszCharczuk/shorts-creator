import json
from datetime import datetime, timezone

from shared.ctx import StageContext, StageResult
from shared.distribution.caption import build_caption
from shared.distribution.posts_ledger import idempotency_key
from shared.distribution.visibility import resolve_visibility
from shared.ramp.policy import gate_active
from shared.ramp.state import is_warmed, load_state
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()


class HeldForReview(Exception):
    """The ramp gate is active and this video has no approval yet — a resumable HOLD, not a failure
    (maps to exit 70 / status 'held'). The review CLI releases it on the next batch."""


def distribute(*, video_id, platforms, adapters, renders, metadata, visibilities, ledger_path,
               approved):
    if not approved:
        raise HeldForReview(f"{video_id} awaiting human approval (ramp gate active)")
    return {p: (adapters[p].publish(video_id=video_id, media_path=renders[p], metadata=metadata[p],
                                    visibility=visibilities[p], ledger_path=ledger_path)
                or {"skipped": "already confirmed"}) for p in platforms}


@stage(StageManifest(id="06", inputs=["render", "script", "qc", "creative_qc"],
                     outputs=["posts", "feature_record"], compute="cpu", capability="distribution"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    state = load_state(ctx.config["ramp_state_path"])          # explicit path (no run-dir guessing)
    warmed = is_warmed(state)                          # CALENDAR predicate (now >= warming_until)
    active = gate_active(state, ctx.config.get("ramp", {}))
    approved = (not active) or (state.get("approved_videos", {}).get(ctx.job["video_id"]) is True)
    platforms, adapters = ctx.job.get("platform_targets", ["youtube"]), ctx.backend("distribution")
    vis_cfg = ctx.config.get("visibility", {})
    affiliate = script.get("affiliate") if ctx.config.get("affiliate_enabled") else None
    metadata = {p: {**build_caption(script["platform_meta"][p], platform=p,
                                    disclosure_line=ctx.config["disclosure_line"],
                                    affiliate=affiliate),
                    "idempotency_key": idempotency_key(ctx.job["video_id"], p)} for p in platforms}
    # per-platform cuts are siblings of the declared "render" input (05 writes renders/<plat>.mp4);
    # derive them from the input path, not an ad-hoc one, so the cache key stays input-bound.
    render = ctx.read_input("render")
    posted = distribute(
        video_id=ctx.job["video_id"], platforms=platforms, adapters=adapters,
        renders={p: render.with_name(f"{p}.mp4") for p in platforms}, metadata=metadata,
        visibilities={p: resolve_visibility(adapters[p], vis_cfg, warmed=warmed)
                      for p in platforms},
        ledger_path=ctx.run_dir / "posts.jsonl", approved=approved)               # PER-VIDEO ledger
    out = ctx.write_output("posts")
    # The posts ARTIFACT is the schema-valid record for the PRIMARY platform (the full
    # per-platform map lives in the per-video posts.jsonl ledger, which the M4 fan-in merges
    # into history/posts.jsonl — ADR 0003 D6).
    primary = platforms[0]
    out.write_text(json.dumps(
        {"schema_version": "1.0.0", "video_id": ctx.job["video_id"], "platform": primary,
         "state": "confirmed", "idempotency_key": idempotency_key(ctx.job["video_id"], primary),
         "remote_id": posted[primary].get("remote_id", ""),
         "url": posted[primary].get("url", ""),
         "ts": datetime.now(timezone.utc).isoformat()}))
    cqc = json.loads(ctx.read_input("creative_qc").read_text())
    fr = ctx.write_output("feature_record")
    feature_record = {"schema_version": "1.0.0", "video_id": ctx.job["video_id"],
                      "niche": ctx.job.get("niche"),
                      "format": script["format"], "seed": ctx.seed,
                      "hook_variant_id": "chosen",
                      "judge_scores": cqc.get("scores", {}),
                      "metrics": {},
                      "creative_qc_overall": cqc.get("overall")}
    _REG.validate("feature_record", feature_record)   # schema boundary — never emit an invalid one
    fr.write_text(json.dumps(feature_record))
    ctx.log.info("distributed", platforms=list(posted))
    return StageResult(outputs={"posts": out, "feature_record": fr})
