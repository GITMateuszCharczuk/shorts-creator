import json
import subprocess
from pathlib import Path

REMOTION_DIR = Path(__file__).resolve().parents[2] / "remotion"


def render_manifest_to_frames(manifest: dict, out_dir: Path) -> list[Path]:
    """Pure-function render: same manifest -> same frames (in the pinned toolchain image)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    raw = out_dir / "raw"
    subprocess.run(
        ["npx", "remotion", "render", "src/index.ts", "Manifest",
         "--props", str(manifest_path), "--sequence", "--image-format", "png",
         "--output", str(raw)],
        cwd=REMOTION_DIR, check=True)
    # Remotion --sequence emits element-<n>.png (NOT zero-padded). Renumber to a zero-padded
    # sequence so ffmpeg's `%05d.png` pattern (encode.py) matches and ordering is numeric
    # (lexical == numeric once padded) — fixes both the glob mismatch and the sort-order bug.
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    raws = sorted(raw.glob("*.png"),
                  key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))
    if not raws:
        # a render that produced 0 frames is broken — never hand ffmpeg an empty sequence
        raise RuntimeError(f"Remotion produced 0 frames in {raw}")
    out = []
    for i, src in enumerate(raws):
        dst = frames_dir / f"{i:05d}.png"
        src.rename(dst)   # MOVE, not copy — frames are ~10 GB/cut; copying doubled the peak
        out.append(dst)
    return out


def render_component(component: str, props: dict, out_dir: Path) -> Path:
    """Renders ONE registered Remotion composition standalone — 01e uses it for the
    `DataVizSlot` component, the SAME component `Manifest` mounts for the `stat_bars`
    region — so 01e and 05 share the engine AND the chart component, not merely the
    project (ADR 0007a §1/§4)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    props_path = out_dir / f"{component}.props.json"
    props_path.write_text(json.dumps(props, sort_keys=True))
    subprocess.run(["npx", "remotion", "render", "src/index.ts", component,
                    "--props", str(props_path), "--output", str(out_dir / f"{component}.mp4")],
                   cwd=REMOTION_DIR, check=True)
    return out_dir / f"{component}.mp4"
