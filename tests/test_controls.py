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
async def test_control_panel_is_removed_from_tracking_before_deletion() -> None:
    panel = AsyncMock()
    music = object.__new__(Music)
    music._control_panels = {1: panel}

    await Music._delete_control_panel(music, 1)

    assert music._control_panels == {}
    panel.delete.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_leave_deletes_panel_before_farewell() -> None:
    events: list[str] = []
    voice = MagicMock()
    voice.is_connected.return_value = True
    voice.disconnect = AsyncMock(side_effect=lambda **_kwargs: events.append("disconnect"))
    player = SimpleNamespace(
        guild_id=1,
        voice=voice,
        stop=MagicMock(side_effect=lambda: events.append("stop")),
    )
    music = object.__new__(Music)
    music._player = MagicMock(return_value=player)
    music._update_voice_channel_status = AsyncMock(
        side_effect=lambda *_args: events.append("status-cleared")
    )
    music._delete_control_panel = AsyncMock(
        side_effect=lambda *_args: events.append("panel-deleted")
    )
    interaction = SimpleNamespace(
        response=SimpleNamespace(
            defer=AsyncMock(side_effect=lambda: events.append("deferred"))
        ),
        edit_original_response=AsyncMock(
            side_effect=lambda **_kwargs: events.append("farewell")
        ),
    )

    await Music.leave.callback(music, interaction)

    assert events == [
        "deferred",
        "stop",
        "status-cleared",
        "disconnect",
        "panel-deleted",
        "farewell",
    ]
    assert player.voice is None


@pytest.mark.asyncio
async def test_connect_voice_channel_replaces_a_stale_connection() -> None:
    stale_voice = MagicMock()
    stale_voice.is_connected.return_value = False
    stale_voice.disconnect = AsyncMock()
    new_voice = MagicMock()
    voice_channel = MagicMock(spec=discord.VoiceChannel)
    voice_channel.connect = AsyncMock(return_value=new_voice)
    guild = MagicMock(spec=discord.Guild)
    guild.voice_client = stale_voice

    result = await Music._connect_voice_channel(guild, voice_channel)

    stale_voice.disconnect.assert_awaited_once_with(force=True)
    voice_channel.connect.assert_awaited_once_with()
    assert result is new_voice


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
    music = cast(
        Music,
        SimpleNamespace(
            _voice_channel_statuses={},
            _voice_channel_status_failures={},
        ),
    )

    await Music._update_voice_channel_status(music, player, track)
    await Music._update_voice_channel_status(music, player, track)

    channel.edit.assert_awaited_once_with(
        status="🎵 Tren al sur",
        reason="Actualizar la canción que está reproduciendo Arturo",
    )

    await Music._update_voice_channel_status(music, player, None)
    assert channel.edit.await_count == 2
    assert channel.edit.await_args.kwargs["status"] is None


@pytest.mark.asyncio
async def test_voice_channel_status_retries_after_a_transient_error() -> None:
    track = Track(
        title="Tren al sur",
        webpage_url="https://example.com/track",
        duration=245,
        requester_id=1,
        requester_name="Alberto",
    )
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 10
    channel.guild.me = MagicMock()
    channel.permissions_for.return_value.set_voice_channel_status = True
    response = MagicMock(status=500, reason="Server Error")
    channel.edit = AsyncMock(
        side_effect=discord.HTTPException(response, "temporary failure")
    )
    player = cast(
        GuildPlayer,
        SimpleNamespace(guild_id=1, voice=SimpleNamespace(channel=channel)),
    )
    music = cast(
        Music,
        SimpleNamespace(
            _voice_channel_statuses={},
            _voice_channel_status_failures={},
        ),
    )

    await Music._update_voice_channel_status(music, player, track)

    assert music._voice_channel_statuses == {}
    assert music._voice_channel_status_failures[1][0] == (10, "🎵 Tren al sur")

    music._voice_channel_status_failures[1] = ((10, "🎵 Tren al sur"), 0)
    channel.edit.side_effect = None
    await Music._update_voice_channel_status(music, player, track)

    assert music._voice_channel_statuses[1] == (10, "🎵 Tren al sur")
    assert music._voice_channel_status_failures == {}
