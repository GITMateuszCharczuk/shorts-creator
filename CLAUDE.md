# shorts-creator — guidance for Claude

Automated short-form video pipeline (finance/business niches): research → script → visuals →
voice → captions → music → render → safety/QC gates → distribute to YouTube/TikTok. **Runner-first**
(a Python conductor on a Windows/WSL2 box with host-owned GPU services; ADR 0015), with an optional
Kubernetes/Argo profile (ADR 0015a). Python 3.12 + `uv`. The **18 ADRs in `docs/decisions/`** are the
source of truth for every design decision — read the relevant one before changing behavior; this file
points at them rather than duplicating them.

## Commands
- `uv sync` — install (commits `uv.lock`; never use bare `python`, always `uv run`).
- `uv run pytest -q -m "not integration and not soak"` — the fast suite (== `make test`, == CI). Must stay GPU-free **and** network-free.
- `uv run ruff check .` — lint (line-length 100, `select = E,F,I`; `ruff format` for layout).
- `uv run pytest -q tests/test_soak_offline.py -m soak` — the offline stability soak (`make soak`).
- Ops CLIs (host): `make {up,trigger,dry-run,review,audit,calibrate,obs-up,obs-lint}`; k8s: `make {cluster-up,argo-generate,k8s-smoke}`.

## Golden rules (do not break these invariants)
- **Determinism:** every stage is a pure function of (declared inputs + resolved config + code version). Seed all RNGs from `ctx.seed`; never read wall-clock/hidden global state into outputs. A seed change must be a cache miss.
- **Content-addressed cache:** keys are `(stage, input_hash, seed)`; `input_hash` folds in `model_id`/`graph_version` for GPU stages. Never hand-roll a cache key.
- **Schemas are contracts:** every declared artifact validates against `schemas/*.schema.json` at the stage boundary. Changing an artifact shape = update the schema + its golden fixture in the same change.
- **Manifests are the DAG source of truth:** `stages/*/manifest.json` (inputs/outputs/compute/capability). The drift-catcher (`tests/test_stage_manifests.py`) requires manifest == registered `@stage`. `runner.ORDER` must equal `executor.default_stage_order()` (guarded by test).
- **Policy is data (ADR 0010):** safety wordlists, disclaimers, thresholds, visibility, per-platform behavior come from the profile/`ctx.config` — **no hardcoded policy and no `platform ==` branches in `shared/` or `stages/`** (`tests/test_no_platform_branches.py` enforces this).
- **Purity of the conductor core:** `execute_batch` stays pure/injectable; metrics/IO are injected wrappers (`metered`), never inlined.

## Account-safety & content (highest stakes — bans are irreversible)
- **Exactly-once:** posting is owned by the `DistributionAdapter` base against a per-video `posts.jsonl` (intent→publishing→confirmed). Never double-post. On crash recovery, if `_find_existing` returns `None`, **raise `UnresolvedPendingPost` — never blind-repost.** Idempotency keys are derived internally, never trusted from caller metadata.
- **Never invent API fields — verify against live platform docs at bring-up.** AI-disclosure rides where the live API actually supports it (YouTube: description today; TikTok: `aigc_content` in `post_info`). **Two items are pending live-docs re-verification** (see soak-runbook §2g + ADR 0009): whether `status.containsSyntheticMedia` is now a real YouTube field, and the current `videos.insert` quota cost (was 1600; reportedly ~100 since Dec 2025 — operator sets `budgets.youtube_insert_units`).
- **YMYL (finance):** every script carries the profile `disclaimer` ("not financial advice / educational only"); 05b blocks prohibited claims (no guaranteed/risk-free returns, no individualized advice). The safety gate is **all-must-hold**; a single failure quarantines before stage 06.
- **Private-first ramp:** videos are held for human approval until the ramp gate lifts; TikTok is forced `SELF_ONLY` until `tiktok.audit_cleared`. Never let a video go public before warming/approval.
- **Secrets:** never commit OAuth secrets/tokens/keys. Use the host vault / env-file (`make k8s-secrets`); `secrets.template.yaml` holds placeholders only.
- **Music:** only verified-licensed tracks (e.g. YouTube Audio Library). Never assume "royalty-free" is strike-safe, and don't reuse YouTube clearance on TikTok.
- **Pre-flight fails closed:** OAuth-age/quota/disk/host gates halt the whole batch (never per-video quarantine, never hammer the API into a lockout).

## uv & dependencies
- Commit `uv.lock`. Runtime deps in `[project.dependencies]`; dev/test in `[dependency-groups]`. GPU libs (torch/clip/kokoro/whisperx) are **host-only, lazily imported** — the GPU-free CI never installs them. CI pins Python 3.12.

## Testing & subprocess discipline
- `--strict-markers` is on; the only markers are `integration` (live model/service) and `soak`. Mark anything touching GPU/network/cluster `integration` so the fast suite excludes it.
- TDD: write the failing test first. Use golden-file fixtures as drift-catchers; mutating a golden must fail the test.
- Crash safety: subprocess-per-stage with `start_new_session=True` + process-group kill on timeout; atomic writes (temp+rename); the success marker last; idempotent retries; the boot reconciler resumes `running`/`pending`/`held`.

## CI (`.github/workflows/`)
- `ci.yml` — the fast GPU-free suite, per push/PR (the per-commit gate).
- `image.yml` — builds the shared image and runs the offline DAG inside it (main only).
- `k8s-generator-diff.yml` — regenerates the Argo `WorkflowTemplate` and diffs it (drift-catcher, per push/PR).
- `k8s-smoke.yml` — the slow kind+Argo gate, nightly/manual only.

## Git / PR
- Develop on the designated feature branch; **commit only when asked**, push only when asked. Branch before committing if on a default branch.
- Commits must be signed and authored as `Claude <noreply@anthropic.com>`.
- Do NOT create a PR unless explicitly asked.

## Do-not-touch / gotchas
- `deploy/argo/generated/shorts-workflowtemplate.yaml` is **generated** — never hand-edit; run `make argo-generate` and commit (CI diffs it).
- `history/` and `models/` are **never** GC'd; the GC never deletes the active or reconciler-resumed batch.
- `NotImplementedError` bodies are **sanctioned host-bring-up seams** (real backends, ComfyUI `_await_output`, `_build_backends`, the k8s smoke) — not bugs; their pure collaborators are implemented + tested. Don't "fix" them with fakes.
- Golden render frames are a deferred on-box artifact (regenerated in the pinned image), not committed.
- The DoD itself is **wall-clock-gated** (~5–7 weeks post-deploy); "code-complete" ≠ "DoD met" (see `deploy/host/soak-runbook.md`).
