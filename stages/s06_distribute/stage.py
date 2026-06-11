import json

from shared.adapters import PostMeta, Visibility
from shared.ctx import StageContext, StageResult
from shared.distribution.posts_ledger import idempotency_key
from shared.stage import StageManifest, stage


@stage(StageManifest(id="06", inputs=["render", "qc", "creative_qc", "script"],
                     outputs=["posts", "feature_record"], compute="cpu", capability="distribution"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    ad = ctx.backend("distribution")
    plat = ctx.job["platform_targets"][0]
    # exactly-once: confirm first; only publish if not already posted (ADR 0003 D1)
    receipt = ad.confirm_posted(ctx.job["video_id"], plat) or ad.publish(
        ctx.read_input("render"),
        PostMeta(title=script["platform_meta"][plat]["title"],
                 description=script["platform_meta"][plat]["description"],
                 hashtags=tuple(script["platform_meta"][plat]["hashtags"]),
                 visibility=Visibility.PRIVATE))
    posts = ctx.write_output("posts")
    # Minimal M0-stub patch (controller-approved, M5 Task 9): emit the NEW posts shape so the
    # Task-9 posts.schema change and the full-DAG boundary validation stay consistent. The REAL
    # ledger rewire (per-video posts.jsonl, ramp gate) still lands in Task 13.
    posts.write_text(json.dumps(
        {"schema_version": "1.0.0", "video_id": receipt.video_id,
         "platform": receipt.platform, "state": "confirmed",
         "idempotency_key": idempotency_key(receipt.video_id, receipt.platform),
         "remote_id": receipt.remote_post_id, "url": "",
         "ts": "2026-06-09T00:00:00Z"}))
    fr = ctx.write_output("feature_record")
    fr.write_text(json.dumps({"schema_version": "1.0.0", "video_id": receipt.video_id,
                              "format": script["format"], "seed": ctx.seed,
                              "hook_variant_id": "chosen", "judge_scores": {}, "metrics": {}}))
    return StageResult(outputs={"posts": posts, "feature_record": fr})
