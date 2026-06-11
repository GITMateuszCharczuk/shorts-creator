import json

from shared.adapters import PostMeta, Visibility
from shared.ctx import StageContext, StageResult
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
    posts.write_text(json.dumps({"schema_version": "1.0.0", "video_id": receipt.video_id,
                                 "platform": receipt.platform, "state": "confirmed",
                                 "visibility": receipt.visibility.value,
                                 "remote_post_id": receipt.remote_post_id,
                                 "timestamp": "2026-06-09T00:00:00Z"}))
    fr = ctx.write_output("feature_record")
    fr.write_text(json.dumps({"schema_version": "1.0.0", "video_id": receipt.video_id,
                              "format": script["format"], "seed": ctx.seed,
                              "hook_variant_id": "chosen", "judge_scores": {}, "metrics": {}}))
    return StageResult(outputs={"posts": posts, "feature_record": fr})
