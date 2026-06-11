import base64
import json
from pathlib import Path

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage

# Minimal valid 1×1 RGB PNG (no runtime deps; ffmpeg can scale/loop it).
# Generated once: python3 -c "import base64,zlib,struct; ..."
_PLACEHOLDER_PNG: bytes = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


@stage(StageManifest(id="01d", inputs=["scenes_motion"], outputs=["assets"],
                     compute="gpu", capability="restore"))
def run(ctx: StageContext) -> StageResult:
    # M2-interim assembly; full per-beat assembly at host bring-up.
    scenes_motion = json.loads(ctx.read_input("scenes_motion").read_text())
    clips = scenes_motion.get("clips", [])

    # Call restore only when there are actual motion clips to process.
    if clips:
        restored = ctx.backend("restore").restore([Path(c["path"]) for c in clips])
    else:
        restored = []

    # Write a real PNG so stage 05's ffmpeg can actually read it (M0 thin stub).
    scene_png = ctx.run_dir / "scenes" / "00.png"
    scene_png.parent.mkdir(parents=True, exist_ok=True)
    scene_png.write_bytes(_PLACEHOLDER_PNG)

    # Baseline scene list (placeholder hook card, always present).
    scenes = [{"beat_id": "hook", "clip_path": "scenes/00.png", "duration": 1.8}]

    # Append any restored motion clips after the placeholder scene.
    for i, (clip, path) in enumerate(zip(clips, restored)):
        scenes.append({
            "beat_id": f"beat_{clip['beat']}",
            "clip_path": str(path),
            "duration": 1.8,
        })

    out = ctx.write_output("assets")
    out.write_text(json.dumps({
        "schema_version": "1.0.0",
        "scenes": scenes,
    }))
    return StageResult(outputs={"assets": out})
