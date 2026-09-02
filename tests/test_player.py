import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

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
