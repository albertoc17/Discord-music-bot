from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from personal_music_bot.media import Track
from personal_music_bot.music import Music, MusicControls
from personal_music_bot.player import GuildPlayer


@pytest.mark.asyncio
async def test_music_controls_have_expected_buttons() -> None:
    controls = MusicControls(cast(Music, object()))

    assert controls.timeout is None
    assert [item.custom_id for item in controls.children] == [
        "arturo:music:toggle",
        "arturo:music:stop",
        "arturo:music:next",
    ]
    controls.stop()


def test_control_panel_embed_shows_now_playing() -> None:
    track = Track(
        title="Tren al sur",
        webpage_url="https://example.com/track",
        duration=245,
        requester_id=1,
        requester_name="Alberto",
    )
    player = cast(
        GuildPlayer,
        SimpleNamespace(current=track, queue=(track, track), get_elapsed_time=lambda: 65),
    )

    embed = Music._control_panel_embed(player)

    assert embed.title == "🎧 Panel de Arturo"
    assert embed.description == "[Tren al sur](https://example.com/track)"
    assert [field.value for field in embed.fields] == [
        "`█████░░░░░░░░░░░░░░░` 1:05 / 4:05",
        "Alberto",
        "2",
    ]


@pytest.mark.asyncio
async def test_control_panel_is_republished_after_new_messages() -> None:
    player = cast(
        GuildPlayer,
        SimpleNamespace(current=None, queue=()),
    )
    old_panel = AsyncMock()
    new_panel = AsyncMock()
    text_channel = AsyncMock()
    text_channel.send.return_value = new_panel
    music = object.__new__(Music)
    music._control_panels = {1: old_panel}

    await Music._ensure_control_panel(music, 1, text_channel, player)

    assert music._control_panels[1] is new_panel
    old_panel.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_voice_channel_status_tracks_current_song_without_repeating_edits() -> None:
    track = Track(
        title="Tren al sur",
        webpage_url="https://example.com/track",
        duration=245,
        requester_id=1,
        requester_name="Alberto",
    )
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 10
    channel.edit = AsyncMock()
    player = cast(
        GuildPlayer,
        SimpleNamespace(guild_id=1, voice=SimpleNamespace(channel=channel)),
    )
    music = cast(Music, SimpleNamespace(_voice_channel_statuses={}))

    await Music._update_voice_channel_status(music, player, track)
    await Music._update_voice_channel_status(music, player, track)

    channel.edit.assert_awaited_once_with(
        status="🎵 Tren al sur",
        reason="Actualizar la canción que está reproduciendo Arturo",
    )

    await Music._update_voice_channel_status(music, player, None)
    assert channel.edit.await_count == 2
    assert channel.edit.await_args.kwargs["status"] is None
