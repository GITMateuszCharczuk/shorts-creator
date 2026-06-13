import json
from pathlib import Path

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01c", inputs=["scenes_gen"], outputs=["scenes_motion"],
                     compute="gpu", capability="img2vid"))
def run(ctx: StageContext) -> StageResult:
    scenes_gen = json.loads(ctx.read_input("scenes_gen").read_text())
    be = ctx.backend("img2vid")
    clips = []
    for frame in scenes_gen.get("frames", []):
        p = be.img2vid(Path(frame["path"]), ctx.seed)
        clips.append({"beat": frame["beat"], "path": str(p)})
    out = ctx.write_output("scenes_motion")
    out.write_text(json.dumps({"clips": clips}))
    return StageResult(outputs={"scenes_motion": out})
