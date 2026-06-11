# Golden frames (ADR 0007a §1/§9)

Generated ONCE inside the pinned toolchain image at host bring-up:

    SHORTS_TOOLCHAIN=pinned uv run python -c "
    import json, pathlib, shutil
    from shared.layout.remotion import render_manifest_to_frames
    m = json.loads(pathlib.Path('tests/fixtures/m2/render_manifest_golden.json').read_text())
    frames = render_manifest_to_frames(m, pathlib.Path('/tmp/golden'))
    for f in frames: shutil.copy(f, 'tests/fixtures/m2/frames_golden/')"

then committed. Until they exist, test_render_determinism SKIPS with an explanatory message.
