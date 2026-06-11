import json
from pathlib import Path

from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter, FixtureStockClient
from shared.cache import StageCache
from shared.config import resolve_config
from shared.ctx import Quarantined, StageContext, StageResult
from shared.hashing import cache_key, input_hash, sha256_bytes
from shared.schema import SchemaRegistry
from shared.stage import REGISTRY
from stages.registry import load_all

# linear M0 order (lane-fork parallelism is an orchestration concern, ADR 0011; semantics identical)
ORDER = ["00a", "00b", "01a", "01b", "01c", "01d", "01e",
         "02", "03", "04", "05", "05x", "05b", "05c", "06"]

# which declared outputs carry a schema (validated at the boundary)
OUTPUT_SCHEMA = {"data": None, "script": "script", "assets": "assets", "provenance": "provenance",
                 "vision": "vision", "qc": "qc", "creative_qc": "creative_qc", "posts": "posts",
                 "feature_record": "feature_record"}

REG = SchemaRegistry()


def run_dag(*, run_dir: Path, seed: int, cache: StageCache, fixtures_dir: Path,
            config: dict | None = None) -> dict:
    load_all()
    backend = FixtureBackend(fixtures_dir=fixtures_dir)
    dist = FixtureDistributionAdapter()
    produced: dict[str, str] = {}  # declared name -> path relative to run_dir
    cache_hits = 0

    # seed job.json
    job = {"schema_version": "1.0.0", "batch_id": "b", "video_id": "fin-0001",
           "niche": "finance", "profile": "finance", "platform_targets": ["youtube"],
           "seed": seed, "stages": {}, "paths": {}}
    (run_dir / "job.json").write_text(json.dumps(job))

    for sid in ORDER:
        reg = REGISTRY[sid]
        m = reg.manifest
        input_paths = {name: produced[name] for name in m.inputs if name in produced}
        output_paths = {name: _default_path(name) for name in m.outputs}

        digests = {name: sha256_bytes((run_dir / p).read_bytes())
                   for name, p in input_paths.items()}
        # ADR 0012 §1: resolved_config is part of the hash; generative stages also fold
        # in model_id + graph_version so a model/graph bump is a miss (ADR 0010 D4).
        resolved = resolve_config(global_defaults=config or {}, niche={}, batch={}, per_platform={})
        gen = {"model_id": "m0-fake", "graph_version": "m0"} if m.compute == "gpu" else {}
        # bumped per milestone: a stale cache entry from an older artifact contract (e.g. a
        # pre-M3 vision.json without "judgment") must MISS, never poison a downstream stage.
        # M4's conductor owns true per-stage versioning.
        ih = input_hash(declared_input_digests=digests, resolved_config=resolved,
                        stage_version="m3", **gen)
        key = cache_key(sid, ih, seed)

        hit = cache.get(key)
        # honor the cache's stale-hit contract: trust a hit only if its outputs are still on
        # disk (M6 GC or a cross-run_dir entry can leave the recorded paths absent) -> else re-run
        if hit is not None and all((run_dir / rel).exists() for rel in hit.values()):
            produced.update(hit)
            cache_hits += 1
            continue

        ctx = StageContext(stage=sid, run_dir=run_dir, seed=seed, job=job, config=resolved,
                           input_paths=input_paths, output_paths=output_paths,
                           backends={"llm": backend, "generate_image": backend,
                                     "img2vid": backend, "tts": backend, "vlm_judge": backend,
                                     "restore": backend, "distribution": dist,
                                     "stock": FixtureStockClient()})
        ctx.set_status("running")                       # ADR 0012 §4 status transitions
        try:
            reg.fn(ctx) or StageResult()
        except Quarantined:
            ctx.set_status("quarantined")
            raise
        for name in m.outputs:
            p = run_dir / output_paths[name]
            schema = OUTPUT_SCHEMA.get(name)
            if schema:
                REG.validate(schema, json.loads(p.read_text()))
            produced[name] = output_paths[name]
        cache.put(key, {name: output_paths[name] for name in m.outputs})
        ctx.set_status("done")

    return {"posts": produced["posts"], "cache_hits": cache_hits}


def _default_path(name: str) -> str:
    binary = {"narration": "narration.wav", "music": "music.wav", "render": "renders/youtube.mp4",
              "captions": "captions.ass"}
    return binary.get(name, f"{name}.json")
