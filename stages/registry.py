import importlib

_STAGE_MODULES = [
    "stages.s00a_research.stage", "stages.s00b_script.stage", "stages.s01a_stock.stage",
    "stages.s01b_imagegen.stage", "stages.s01c_img2vid.stage", "stages.s01d_upscale.stage",
    "stages.s01e_dataviz.stage", "stages.s02_voice.stage", "stages.s03_subs.stage",
    "stages.s04_music.stage", "stages.s05_render.stage", "stages.s05x_vision.stage",
    "stages.s05b_safety.stage", "stages.s05c_qc.stage", "stages.s06_distribute.stage",
]


def load_all():
    for m in _STAGE_MODULES:
        importlib.import_module(m)
