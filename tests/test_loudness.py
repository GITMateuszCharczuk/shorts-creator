from shared.audio.loudness import loudnorm_args, target_lufs


def test_platform_targets():
    assert target_lufs("youtube") == -14.0 and target_lufs("tiktok") == -14.0


def test_loudnorm_args_string():
    a = loudnorm_args("youtube")
    assert "loudnorm" in a and "I=-14" in a and "TP=-1" in a
