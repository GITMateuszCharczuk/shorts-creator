PROVISIONAL = 0.70  # the ADR 0016 D2 provisional floor, held until data earns a change


def _metrics_at(labels, thr):
    keep = [lb for lb in labels if lb["overall"] >= thr]
    tp = sum(1 for lb in keep if lb["approved"])
    fn = sum(1 for lb in labels if lb["overall"] < thr and lb["approved"])
    kp = tp / len(keep) if keep else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * kp * recall / (kp + recall)) if (kp + recall) else 0.0
    return kp, recall, f1


def recommend_floor(labels: list[dict], *, min_labels: int = 30, min_keep_precision: float = 0.85,
                    floor_min: float = 0.50, floor_max: float = 0.90,
                    low_conf_below: int = 50) -> dict:
    """ADR 0016 D2, PER NICHE (the caller groups by niche). Maximize F1 s.t. keep-precision >=
    constraint. Below min_labels -> hold PROVISIONAL. n < low_conf_below -> data_anchored but
    flagged low_confidence (a 1-2 week ramp yields few labels: directional, operator-promoted,
    never auto-applied)."""
    if len(labels) < min_labels:
        return {"floor": PROVISIONAL, "reason": "insufficient_labels", "n_labels": len(labels)}
    best, thr = None, floor_min
    while thr <= floor_max + 1e-9:
        kp, recall, f1 = _metrics_at(labels, round(thr, 3))
        if kp >= min_keep_precision and (best is None or f1 > best["f1"]):
            best = {"floor": round(thr, 3), "f1": round(f1, 3),
                    "keep_precision": round(kp, 3), "recall": round(recall, 3)}
        thr += 0.01
    if best is None:
        return {"floor": floor_max, "reason": "precision_constraint_unmet", "n_labels": len(labels)}
    return {**best, "reason": "data_anchored", "n_labels": len(labels),
            "low_confidence": len(labels) < low_conf_below}
