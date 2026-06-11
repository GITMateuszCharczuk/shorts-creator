import json

from shared.ctx import StageContext, StageResult
from shared.qc.sampling import sample_frames
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()


@stage(StageManifest(id="05x", inputs=["render", "script"], outputs=["vision"],
                     compute="gpu", capability="vlm_judge"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    manifest = json.loads((ctx.run_dir / "render_manifest.json").read_text())
    total = _frame_count(ctx.read_input("render"))            # ffprobe, integration
    indices = sample_frames(manifest, total)
    frame_paths = _extract_frames(ctx.read_input("render"), indices)   # integration
    judgment = ctx.backend("vlm_judge").vlm_judge(frame_paths, script)

    def _kind(i: int) -> str:                # 05b (M5) needs the hook/end-card distinction
        return "hook" if i == 0 else "end_card" if i == total - 1 else "beat"

    vision = {"schema_version": "1.0.0",
              "keyframes": [{"frame_id": str(idx), "kind": _kind(idx), "observations": []}
                            for idx in indices],
              "judgment": {"visual_scores": judgment.scores,                  # coherence, pacing
                           "observations": list(judgment.observations)}}      # ADR 0016 D5
    _REG.validate("vision", vision)   # boundary validation (Ch.5); judgment keys pinned in schema
    out = ctx.write_output("vision")
    out.write_text(json.dumps(vision))
    ctx.log.info("vision pass complete", frames=len(frame_paths))
    return StageResult(outputs={"vision": out})


def _frame_count(render):
    raise NotImplementedError("ffprobe frame count wired at integration; sampling is unit-tested")


def _extract_frames(render, indices):
    raise NotImplementedError("ffmpeg frame extraction wired at integration")
