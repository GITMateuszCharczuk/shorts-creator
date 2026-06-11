# ADR 0007a §1/§9: CPU rasterization on the 7800X3D. Published M2 budget (revisit on the box):
TARGET_MS_PER_FRAME = 40.0    # design target for the resolve+raster path @1080x1920
FAIL_MS_PER_FRAME = 80.0      # tripwire: above this, the overnight-batch budget (ADR 0011) is at risk


def ms_per_frame(*, elapsed_s: float, frames: int) -> float:
    return round(elapsed_s * 1000.0 / frames, 3)


def within_budget(mspf: float) -> bool:
    return mspf <= FAIL_MS_PER_FRAME
