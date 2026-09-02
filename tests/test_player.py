import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from personal_music_bot import player as player_module
from personal_music_bot.media import Track
from personal_music_bot.player import GuildPlayer


@pytest.mark.asyncio
async def test_idle_disconnect_sends_a_farewell() -> None:
    player = GuildPlayer(
        guild_id=1,
        resolver=MagicMock(),
        ffmpeg_executable="ffmpeg",
        volume=0.7,
        idle_timeout=0.01,
    )
    voice = MagicMock()
    voice.is_connected.return_value = True
    voice.disconnect = AsyncMock()
    status_messages: list[str] = []
    farewell_sent = asyncio.Event()

    async def save_status(message: str) -> None:
        status_messages.append(message)
        farewell_sent.set()

    player.set_voice(voice)
    player.set_status_callback(save_status)

    try:
        await asyncio.wait_for(farewell_sent.wait(), timeout=1)

        voice.disconnect.assert_awaited_once_with(force=True)
        assert player.voice is None
        assert len(status_messages) == 1
    finally:
        await player.close()


@pytest.mark.asyncio
async def test_idle_disconnect_runs_cleanup_before_farewell() -> None:
    player = GuildPlayer(
        guild_id=1,
        resolver=MagicMock(),
        ffmpeg_executable="ffmpeg",
        volume=0.7,
        idle_timeout=0.01,
    )
    voice = MagicMock()
    voice.is_connected.return_value = True
    voice.disconnect = AsyncMock()
    events: list[str] = []
    completed = asyncio.Event()

    async def update_track(_track: Track | None) -> None:
        events.append("panel-updated")

    async def disconnect_cleanup() -> None:
        events.append("panel-deleted")
        events.append("farewell")
        completed.set()

    player.set_voice(voice)
    player.set_track_callback(update_track)
    player.set_disconnect_callback(disconnect_cleanup)

    try:
        await asyncio.wait_for(completed.wait(), timeout=1)

        voice.disconnect.assert_awaited_once_with(force=True)
        assert player.voice is None
        assert events == ["panel-updated", "panel-deleted", "farewell"]
    finally:
        await player.close()


@pytest.mark.asyncio
async def test_random_event_runs_during_an_eligible_track(monkeypatch) -> None:
    player = GuildPlayer(
        guild_id=1,
        resolver=MagicMock(),
        ffmpeg_executable="ffmpeg",
        volume=0.7,
        idle_timeout=300,
    )
    track = Track(
        title="Tren al sur",
        webpage_url="https://example.com/track",
        duration=245,
        requester_id=1,
        requester_name="Alberto",
    )
    voice = MagicMock()
    voice.is_connected.return_value = True
    voice.disconnect = AsyncMock()
    callback = AsyncMock()
    sleep = AsyncMock()
    monkeypatch.setattr(player_module.random, "random", lambda: 0)
    monkeypatch.setattr(player_module.random, "uniform", lambda _start, _end: 42)
    monkeypatch.setattr(player_module.asyncio, "sleep", sleep)
    player.current = track
    player.voice = voice
    player.set_random_event_callback(callback)

    try:
        await player._schedule_random_event(track)

        sleep.assert_awaited_once_with(42)
        callback.assert_awaited_once()
    finally:
        await player.close()
