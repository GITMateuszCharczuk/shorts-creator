import re

from shared.safety.types import CheckResult

_DEFAULT_PROFANITY = {"damn", "hell", "crap"}            # global default; profile may override
_ARTIFACT_LEXICON = ("morph", "garbled", "extra finger", "warp", "melted",
                     "caption overlap", "occlud", "distorted text")


def _text(script: dict) -> str:
    spoken = " ".join(b.get("text", "") for b in script.get("narration_beats", []))
    captions = " ".join(c.get("text", "") for c in script.get("captions", []))
    return f"{spoken} {captions}".lower()


def disclaimer_present(script: dict, profile: dict) -> CheckResult:
    want = profile["defaults"]["disclaimer"].strip()
    got = (script.get("disclaimer") or "").strip()
    return CheckResult(got == want and bool(want), "disclaimer",
                       "" if got == want else f"disclaimer != profile ({got!r})")


def no_prohibited_claims(script: dict, profile: dict) -> CheckResult:
    """The denylist is the PROFILE's denylist_terms (data, not code, ADR 0010 D5). Conservative by
    design: a match quarantines (safe); the list is the niche's responsibility to keep complete."""
    def _norm(s: str) -> str:
        return s.lower().replace("-", " ")   # "risk-free" and "risk free" must match either way
    terms = [_norm(t) for t in profile["defaults"].get("denylist_terms", [])]
    text = _norm(_text(script))
    hit = next((t for t in terms if t in text), None)
    return CheckResult(hit is None, "prohibited_claims",
                       "" if hit is None else f"prohibited phrase {hit!r}")


def sources_cited(script: dict) -> CheckResult:
    cited = [c for c in script.get("claims", []) if c.get("source_ref")]
    return CheckResult(len(cited) >= 1, "sources_cited",
                       "" if cited else "no claim carries a source_ref")


def disclosure_set(script: dict) -> CheckResult:
    ok = bool(script.get("platform_meta", {}).get("ai_disclosure"))
    return CheckResult(ok, "ai_disclosure", "" if ok else "ai_disclosure flag not set")


def profanity_clear(script: dict, wordlist: set[str] | None = None) -> CheckResult:
    words = wordlist if wordlist is not None else _DEFAULT_PROFANITY
    tokens = set(re.findall(r"\w+", _text(script)))   # punctuation-attached profanity must NOT slip
    hit = next((w for w in words if w in tokens), None)
    return CheckResult(hit is None, "profanity", "" if hit is None else f"profanity {hit!r}")


def artifact_clear(vision: dict) -> CheckResult:
    """The 05x dual-consumer contract (ADR 0008/0016 D5): fail on any artifact observation
    (morphing/garbled text/caption occlusion).
    05c judged its visual *quality*; 05b judges *safety*."""
    obs = [o.lower() for o in vision.get("judgment", {}).get("observations", [])]
    hit = next((o for o in obs if any(k in o for k in _ARTIFACT_LEXICON)), None)
    return CheckResult(hit is None, "artifact", "" if hit is None else f"artifact: {hit}")
