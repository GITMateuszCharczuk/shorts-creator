import json

from shared.ctx import StageContext, StageResult
from shared.safety import audio_defect as ad
from shared.safety import checks as ck
from shared.safety import geometry as geo
from shared.safety import render_integrity as ri
from shared.safety.gate import aggregate
from shared.safety.probe import ProbeResult, probe
from shared.safety.repetition import not_repetitious
from shared.safety.types import CheckResult, SafetyThresholds
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()
_QUALITY_KEYS = {"score", "quality", "interesting", "rating", "overall"}

# support-only: the 00b model checks factual grounding, NOT quality (ADR 0016 D1 stays intact).
_FACT_PROMPT = ('Return STRICT JSON {"hallucination": bool, "note": "..."} — true if any stated '
                "number/claim is NOT supported by the DATA. Judge support only, never quality."
                "\n\nSCRIPT: ")


class QualityLeakError(Exception):
    """The 05b fact LLM returned a quality-adjacent key — that signal belongs to 05c, not the
    safety gate. Fail loud so 05b never drifts into self-judging quality (ADR 0016 D1)."""


def collect_checks(*, script, profile, vision, probes: ProbeResult, platform, ledger, llm,
                   thresholds: SafetyThresholds, safe_zones) -> list[CheckResult]:
    fact = llm.llm_json(_FACT_PROMPT + json.dumps(script))
    if _QUALITY_KEYS & set(fact):
        raise QualityLeakError(f"05b fact-LLM returned quality keys: {_QUALITY_KEYS & set(fact)}")
    return [
        ck.disclaimer_present(script, profile),
        ck.no_prohibited_claims(script, profile),
        ck.sources_cited(script),
        ck.disclosure_set(script),
        ck.profanity_clear(script,
                           set(profile["defaults"].get("profanity_wordlist", [])) or None),
        ck.artifact_clear(vision),
        geo.in_safe_zone(probes.cta_rect, platform=platform, zones=safe_zones),
        ad.loudness_ok(integrated_lufs=probes.integrated_lufs,
                       true_peak_dbtp=probes.true_peak_dbtp, t=thresholds),
        ad.hook_dead_air_ok(silences=probes.silences, t=thresholds),
        ad.synth_duration_ok(actual_s=probes.actual_s, projected_s=probes.projected_s,
                             t=thresholds),
        ri.black_run_ok(black_spans=probes.black_spans, t=thresholds),
        ri.no_clipping_ok(true_peak_dbtp=probes.true_peak_dbtp, t=thresholds),
        not_repetitious({"topic": script.get("topic"),
                         "hook": script.get("hook", {}).get("spoken", "")}, ledger),
        CheckResult(not fact.get("hallucination", True), "hallucination", fact.get("note", "")),
    ]


@stage(StageManifest(id="05b", inputs=["render", "script", "vision", "narration", "music"],
                     outputs=["qc"], compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    vision = json.loads(ctx.read_input("vision").read_text())
    profile = ctx.job["profile"]                # the resolved profile dict on the job (ADR 0010 D5)
    # narration + music are declared inputs because the probe MEASURES them (silencedetect on
    # narration, loudnorm on the music mix) — so the DAG/cache key reflect 05b's real dependencies.
    probes = probe(ctx.run_dir, narration=ctx.read_input("narration"),
                   music=ctx.read_input("music"), render=ctx.read_input("render"),
                   render_manifest=ctx.run_dir / "render_manifest.json")
    results = collect_checks(
        script=script, profile=profile, vision=vision, probes=probes,
        platform=ctx.job.get("platform_targets", ["youtube"])[0], ledger=_recent_ledger(ctx),
        llm=ctx.backend("llm"),
        thresholds=SafetyThresholds.from_config(ctx.config.get("safety", {})),
        safe_zones=ctx.config.get("safe_zones"))
    payload = aggregate(results)
    _REG.validate("qc", payload)
    out = ctx.write_output("qc")
    out.write_text(json.dumps(payload))                   # write BEFORE any quarantine raise
    if not payload["passed"]:
        failed = [c["name"] for c in payload["checks"] if not c["ok"]]
        ctx.quarantine(f"safety gate failed: {failed}")
    ctx.log.info("safety gate pass", checks=len(results))
    return StageResult(outputs={"qc": out})


def _recent_ledger(ctx):
    raise NotImplementedError("Integration seam: read the trailing novelty/posted window from "
                              "history/; CI injects a list. The pure checks are unit-tested.")
