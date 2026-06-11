import json
from pathlib import Path

from shared.adapters.types import Judgment, PostMeta, PostReceipt, Visibility
from shared.hashing import input_hash, sha256_bytes


class MissingFixtureError(FileNotFoundError):
    """No fixture for this (capability, input_hash) — add one under fixtures_dir/<capability>/."""


class FixtureBackend:
    """Replays canned outputs from fixtures_dir/<capability>/<input_hash>.<ext>."""

    def __init__(self, fixtures_dir: Path):
        self._dir = Path(fixtures_dir)

    def _hash(self, **named_bytes: bytes) -> str:
        return input_hash(
            declared_input_digests={k: sha256_bytes(v) for k, v in named_bytes.items()},
            resolved_config={}, stage_version="fake",
        )

    def _path(self, capability: str, h: str, ext: str) -> Path:
        return self._dir / capability / f"{h}.{ext}"

    def llm(self, prompt: str, seed: int | None = None) -> str:
        p = self._path("llm", self._hash(prompt=prompt.encode()), "txt")
        if not p.exists():
            raise MissingFixtureError(f"no llm fixture at {p} — add the canned response")
        return p.read_text()

    def llm_json(self, prompt: str, seed: int | None = None) -> dict:
        return json.loads(self.llm(prompt, seed))   # fixtures are valid JSON by construction

    def generate_image(self, prompt: str, seed: int) -> Path:
        p = self._path("generate_image", self._hash(prompt=prompt.encode()), "png")
        if not p.exists():
            # raise HERE so the error names this stage — otherwise the missing file surfaces one
            # stage later in img2vid with a misattributed message
            raise MissingFixtureError(f"no generate_image fixture at {p} — add the canned png")
        return p

    def img2vid(self, image: Path, seed: int) -> Path:
        img = Path(image)
        if not img.exists():
            raise MissingFixtureError(f"img2vid input {img} missing — upstream fixture absent")
        return self._path("img2vid", self._hash(image=img.read_bytes()), "mp4")

    def tts(self, text: str) -> Path:
        return self._path("tts", self._hash(text=text.encode()), "wav")

    def tts_segments(self, segments: list[dict]) -> Path:
        h = self._hash(segments=json.dumps(segments, sort_keys=True).encode())
        p = self._path("tts", h, "wav")
        if not p.exists():
            raise MissingFixtureError(f"no tts fixture at {p} — add the canned wav")
        return p

    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment:
        return Judgment(overall=0.82, scores={"hook": 0.8, "coherence": 0.85}, passed=True)

    def restore(self, frames: list[Path]) -> list[Path]:
        return list(frames)  # fake: passthrough


class FixtureStockClient:
    """Deterministic stock candidates for the offline DAG (no HTTP)."""

    def search(self, query: str, n: int) -> list[dict]:
        h = sha256_bytes(query.encode())[:16]   # deterministic per-query stem
        return [{"path": f"stock/{h[:8]}_{i}.jpg",
                 "phash": sha256_bytes(f"{query}/{i}".encode())[:16],   # distinct per candidate
                 "score": 0.9 - 0.1 * i,
                 "source": "pexels", "url": f"https://fixture/{h[:8]}/{i}",
                 "license": "Pexels", "fetch_date": "2026-06-09"} for i in range(min(n, 2))]


class FixtureDistributionAdapter:
    """In-memory exactly-once fake: publish records intent->confirm; confirm replays it."""

    def __init__(self):
        self._posted: dict[tuple[str, str], PostReceipt] = {}
        self._counter = 0

    def publish(self, render: Path, meta: PostMeta) -> PostReceipt:
        self._counter += 1
        # unique per call so a multi-video offline batch doesn't collide on one ledger key
        rec = PostReceipt(video_id=f"fin-{self._counter:04d}", platform="youtube",
                          remote_post_id=f"fake_{self._counter}", visibility=meta.visibility)
        self._posted[(rec.video_id, rec.platform)] = rec
        return rec

    def confirm_posted(self, video_id: str, platform: str) -> PostReceipt | None:
        return self._posted.get((video_id, platform))

    def allowed_visibility(self, audit_state: str) -> set[Visibility]:
        if audit_state == "audited":
            return {Visibility.PRIVATE, Visibility.SELF_ONLY, Visibility.PUBLIC}
        return {Visibility.PRIVATE, Visibility.SELF_ONLY}
