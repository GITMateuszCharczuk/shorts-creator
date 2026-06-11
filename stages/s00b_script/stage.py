import json
import random
import re

from shared.ctx import StageContext, StageResult
from shared.finance.grounding import check_claims
from shared.stage import StageManifest, stage

_SCORE = re.compile(r"-?\d*\.?\d+")


def parse_score(text: str) -> float | None:
    """Extract the judge's numeric score from a free-form reply ('0.82', 'Score: 0.82', ...).

    A live model often prefixes words; take the FIRST number. None when no number exists —
    the caller quarantines (a judge that can't produce a score is a quality failure, not a crash).
    """
    m = _SCORE.search(text)
    return float(m.group()) if m else None


def pick_best(scored: list[tuple[dict, float]]) -> dict:
    # max by score; ties resolve to the earliest index (deterministic)
    best_i = max(range(len(scored)), key=lambda i: (scored[i][1], -i))
    return scored[best_i][0]


def build_judge_prompt(script: dict) -> str:
    return ("Score this short-video script 0-1 on: hook strength; "
            "does it say something NON-OBVIOUS with an ORIGINAL point of view "
            "(not a generic template fill); visual-script coherence; payoff. "
            "Return only a number.\n\n" + json.dumps(script))


def clears_floor(scored: list[tuple[dict, float]], floor: float) -> bool:
    """ADR 0016 D3: the provisional script-time floor — quarantine before any GPU work."""
    return max(sc for _, sc in scored) >= floor


@stage(
    StageManifest(
        id="00b", inputs=["data"], outputs=["script"], compute="cpu", capability="llm"
    )
)
def run(ctx: StageContext) -> StageResult:
    data = json.loads(ctx.read_input("data").read_text())
    llm = ctx.backend("llm")
    rng = random.Random(ctx.seed)  # seed -> reproducible best-of-N (ADR 0009)
    n = int(ctx.config.get("best_of_n", 3))
    if n < 1:
        raise ValueError(f"00b: best_of_n must be >= 1, got {n}")  # empty batch would crash below

    scored: list[tuple[dict, float]] = []
    for i in range(n):
        script = _generate_script(llm, data, ctx.config, rng.randint(0, 2**31))
        score = parse_score(llm.llm(build_judge_prompt(script)))
        if score is None:
            ctx.quarantine("judge returned an unparseable score")
        scored.append((script, score))

    chosen = dict(pick_best(scored))  # shallow copy: never mutate the dict held inside `scored`
    chosen["hook_variants"] = [
        {"spoken": s["hook"]["spoken"], "score": sc} for s, sc in scored
    ]
    if not clears_floor(scored, float(ctx.config.get("script_floor", 0.55))):
        ctx.quarantine(
            f"all {n} scripts below the script-time floor (ADR 0016 D3)"
        )
    from shared.finance.grounding import GroundingError
    try:
        check_claims(chosen.get("claims", []), data)
    except GroundingError as e:
        ctx.quarantine(f"numeric grounding failed: {e}")
    if not chosen.get("disclaimer", "").strip():
        ctx.quarantine("missing YMYL disclaimer")   # ADR 0004 YMYL (enforced, not just prompted)

    out = ctx.write_output("script")
    out.write_text(json.dumps(chosen))
    ctx.log.info("script chosen", n=n, best_score=max(sc for _, sc in scored))
    return StageResult(outputs={"script": out})


def _generate_script(llm, data: dict, config: dict, seed: int) -> dict:
    # Builds the finance-persona prompt (treatment + format + hook + beats + claims with
    # {value, source_ref}) and parses the model's JSON into a script.schema instance.
    # Prompt construction is deterministic given (data, config, seed); the model call is live.
    prompt = _build_prompt(data, config, seed)
    return llm.llm_json(prompt, seed=seed)  # constrained JSON + retry; seed -> sampler (ADR 0009)


def _build_prompt(data: dict, config: dict, seed: int) -> str:
    persona = config.get("persona", "a rigorous, data-first finance explainer")
    return (f"You are {persona}. Using ONLY these figures (cite each as "
            f'{{"value","source_ref"}} into the given keys): {json.dumps(data["market"])}. '
            f"Recent news: {json.dumps(data['news'])}. Seed={seed}. "
            "Write a vertical short-video script as JSON matching the script schema "
            "(format, treatment, hook, narration_beats, captions, music, platform_meta, "
            "claims, disclaimer, layout_data). Pick the ranked_list format. "
            "Include a YMYL disclaimer. Make the take NON-OBVIOUS.")
