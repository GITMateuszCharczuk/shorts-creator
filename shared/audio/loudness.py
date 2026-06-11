_TARGETS = {"youtube": -14.0, "tiktok": -14.0}


def target_lufs(platform: str) -> float:
    return _TARGETS.get(platform, -14.0)


def loudnorm_args(platform: str, true_peak: float = -1.0) -> str:
    return f"loudnorm=I={target_lufs(platform):g}:TP={true_peak:g}:LRA=11"
