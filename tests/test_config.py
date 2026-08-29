from __future__ import annotations

import pytest

from personal_music_bot.config import Settings


def test_settings_reads_required_and_optional_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "secret")
    monkeypatch.setenv("DISCORD_GUILD_ID", "123")
    monkeypatch.setenv("DEFAULT_VOLUME", "0.75")

    settings = Settings.from_env()

    assert settings.discord_token == "secret"
    assert settings.guild_id == 123
    assert settings.default_volume == 0.75


def test_settings_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.setattr("personal_music_bot.config.load_dotenv", lambda: None)

    with pytest.raises(RuntimeError, match="DISCORD_TOKEN"):
        Settings.from_env()


@pytest.mark.parametrize("value", ["-1", "1.1", "abc"])
def test_settings_rejects_invalid_volume(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "secret")
    monkeypatch.setenv("DEFAULT_VOLUME", value)

    with pytest.raises(ValueError, match="DEFAULT_VOLUME"):
        Settings.from_env()

