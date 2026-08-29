from personal_music_bot.media import format_duration


def test_format_duration() -> None:
    assert format_duration(None) == "duracion desconocida"
    assert format_duration(65) == "1:05"
    assert format_duration(3661) == "1:01:01"

