from pathlib import Path
from typing import Callable


def rank_candidates(
    paths: list[str],
    scorer: Callable[[str], float],
    threshold: float = 0.0,
) -> list[str]:
    """Rank image paths by scorer descending, filtering below threshold.

    Python's sorted() is stable — equal-score candidates preserve input order (ADR 0009).
    A candidate whose scorer RAISES (corrupt/unreadable image) is skipped, not fatal: one bad
    download must never sink the whole beat's candidate list.
    NB: CLIP cosines live in [-1, 1]; the default threshold=0.0 intentionally filters
    anti-correlated candidates.
    """
    scored = []
    for p in paths:
        try:
            scored.append((p, scorer(p)))
        except Exception:   # any per-candidate failure means "skip this one", never "skip all"
            continue
    kept = [(p, s) for p, s in scored if s >= threshold]
    return [p for p, _ in sorted(kept, key=lambda x: x[1], reverse=True)]


class ClipRanker:
    """open-clip beat<->image cosine similarity. model_id is config-swappable (ADR 0005)."""

    def __init__(self, model: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        self.model_id = f"open-clip:{model}:{pretrained}"
        self._model = model
        self._pretrained = pretrained
        self._loaded = None

    def _ensure(self):
        if self._loaded is None:
            import open_clip  # host-only
            import torch  # host-only
            m, _, prep = open_clip.create_model_and_transforms(
                self._model, pretrained=self._pretrained
            )
            self._loaded = (m, prep, open_clip.get_tokenizer(self._model), torch)
        return self._loaded

    def score(self, beat_text: str, image: Path) -> float:
        from PIL import Image

        m, prep, tok, torch = self._ensure()
        with torch.no_grad():
            img = prep(Image.open(image)).unsqueeze(0)
            txt = tok([beat_text])
            i = m.encode_image(img)
            t = m.encode_text(txt)
            i = i / i.norm(dim=-1, keepdim=True)
            t = t / t.norm(dim=-1, keepdim=True)
            return float((i @ t.T).item())
