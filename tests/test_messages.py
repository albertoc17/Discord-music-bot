from personal_music_bot import messages


def test_searching_message_uses_chilean_copy(monkeypatch) -> None:
    monkeypatch.setattr(messages, "choice", lambda options: options[1])

    assert messages.searching_message() == "Ya po, estoy viendo qué weá pillo... 🔎"


def test_not_found_message_uses_chilean_copy(monkeypatch) -> None:
    monkeypatch.setattr(messages, "choice", lambda options: options[0])

    assert messages.not_found_message().startswith("No encontré tu tema, qlo")


def test_track_message_includes_metadata(monkeypatch) -> None:
    monkeypatch.setattr(messages, "choice", lambda options: options[0])

    result = messages.track_queued_message("El baile", "3:42")

    assert "**El baile**" in result
    assert "3:42" in result


def test_playlist_message_includes_count_and_limit(monkeypatch) -> None:
    monkeypatch.setattr(messages, "choice", lambda options: options[1])

    result = messages.playlist_queued_message(12, 50)

    assert "**12 canciones**" in result
    assert "50" in result


def test_now_playing_message_includes_requester(monkeypatch) -> None:
    monkeypatch.setattr(messages, "choice", lambda options: options[2])

    result = messages.now_playing_message("Tren al sur", "Alberto")

    assert "**Tren al sur**" in result
    assert "Alberto" in result


def test_leaving_message_uses_chilean_copy(monkeypatch) -> None:
    monkeypatch.setattr(messages, "choice", lambda options: options[0])

    assert messages.leaving_message() == "Chao, giles culiaos. 👋"
