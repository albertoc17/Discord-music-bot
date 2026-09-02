from personal_music_bot import messages


def test_each_message_category_has_ten_new_variants() -> None:
    assert len(messages._SEARCHING) == 14
    assert len(messages._NOT_FOUND) == 13
    assert len(messages._TRACK_QUEUED) == 13
    assert len(messages._PLAYLIST_QUEUED) == 13
    assert len(messages._NOW_PLAYING) == 13
    assert len(messages._PLAYBACK_FAILED) == 13
    assert len(messages._LEAVING) == 14
    assert len(messages._RANDOM_INSULTS) == 15


def test_all_message_variants_accept_their_expected_metadata() -> None:
    for template in messages._TRACK_QUEUED:
        assert "Canción" in template.format(title="Canción", duration="3:42")
    for template in messages._PLAYLIST_QUEUED:
        assert "12" in template.format(count=12, limit=50)
    for template in messages._NOW_PLAYING:
        formatted = template.format(title="Canción", requester="Alberto")
        assert "Canción" in formatted
        assert "Alberto" in formatted
    for template in messages._PLAYBACK_FAILED:
        assert "Canción" in template.format(title="Canción")


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


def test_random_insult_includes_member_without_a_mention(monkeypatch) -> None:
    monkeypatch.setattr(messages, "choice", lambda options: options[0])

    result = messages.random_insult_message("Freire")

    assert result == "Freire, chupa el pico. Con cariño, Arturo. ❤️"
    assert "@" not in result
