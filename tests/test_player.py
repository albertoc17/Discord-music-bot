import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from personal_music_bot import player as player_module
from personal_music_bot.media import Track
from personal_music_bot.player import GuildPlayer


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TimeoutError, OSError, RuntimeError])
@pytest.mark.parametrize("failed_callback", ["panel", "status"])
async def test_notification_failure_preserves_playback(
    monkeypatch, error_type, failed_callback
) -> None:
    resolver = MagicMock()
    resolver.stream_for = AsyncMock(return_value=MagicMock(url="https://example.com/audio"))
    player = GuildPlayer(1, resolver, "ffmpeg", 0.7, 300)
    voice = MagicMock()
    voice.is_connected.return_value = True
    voice.disconnect = AsyncMock()
    monkeypatch.setattr(player_module.discord, "FFmpegPCMAudio", MagicMock())
    monkeypatch.setattr(player_module.discord, "PCMVolumeTransformer", MagicMock())
    track = Track("Song", "https://example.com/track", 245, 1, "Listener")
    notification_failed = asyncio.Event()
    panel_recovered = asyncio.Event()
    playback_finished = asyncio.Event()
    messages: list[str] = []

    async def update_panel(current: Track | None) -> None:
        if current is None:
            playback_finished.set()
        elif failed_callback == "panel" and not notification_failed.is_set():
            notification_failed.set()
            raise error_type("Panel unavailable")
        else:
            panel_recovered.set()

    async def send_status(message: str) -> None:
        messages.append(message)
        if failed_callback == "status" and not notification_failed.is_set():
            notification_failed.set()
            raise error_type("Status unavailable")

    player.set_voice(voice)
    player.set_track_callback(update_panel)
    player.set_status_callback(send_status)
    player.enqueue([track])
    try:
        await asyncio.wait_for(notification_failed.wait(), timeout=2)
        await asyncio.wait_for(panel_recovered.wait(), timeout=2)
        assert player.current is track
        assert not player._task.done()
        assert not playback_finished.is_set()
        voice.play.assert_called_once()
        voice.stop.assert_not_called()
        assert len(messages) == 1

        voice.play.call_args.kwargs["after"](None)
        await asyncio.wait_for(playback_finished.wait(), timeout=2)
        assert player.current is None
        assert not player._task.done()
    finally:
        await player.close()


@pytest.mark.asyncio
async def test_panel_notification_does_not_swallow_cancellation() -> None:
    player = GuildPlayer(1, MagicMock(), "ffmpeg", 0.7, 300)
    player.set_track_callback(AsyncMock(side_effect=asyncio.CancelledError))
    try:
        with pytest.raises(asyncio.CancelledError):
            await player._notify_track_changed(None)
    finally:
        await player.close()


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
