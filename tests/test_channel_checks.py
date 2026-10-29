from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from personal_music_bot.channel_checks import MusicChannelCommandTree
from personal_music_bot.music import Music, MusicControls


@pytest.mark.asyncio
@pytest.mark.parametrize("command_name", ["play", "cuantomemide", "cuandtomemide"])
@pytest.mark.parametrize("entrypoint", [MusicChannelCommandTree, MusicControls])
@pytest.mark.parametrize(
    ("channel_type", "name", "guild_id", "allowed"),
    [
        (discord.TextChannel, "musica", 1, True),
        (discord.TextChannel, "general", 1, False),
        (discord.TextChannel, "musica-bot", 1, False),
        (discord.VoiceChannel, "musica", 1, False),
        (discord.Thread, "musica", 1, False),
        (discord.DMChannel, "musica", None, False),
        (None, None, 1, False),
    ],
)
async def test_interactions_only_run_in_music_text_channel(
    entrypoint, channel_type, name, guild_id, allowed, command_name
) -> None:
    if (
        entrypoint is MusicChannelCommandTree
        and command_name == "cuantomemide"
        and channel_type is discord.TextChannel
        and guild_id is not None
    ):
        allowed = True
    channel = MagicMock(spec=channel_type) if channel_type else None
    if channel is not None:
        channel.name = name
    interaction = SimpleNamespace(
        data={"name": command_name, "type": discord.AppCommandType.chat_input.value},
        channel=channel,
        guild_id=guild_id,
        response=SimpleNamespace(send_message=AsyncMock()),
    )

    assert await entrypoint.interaction_check(None, interaction) is allowed

    if allowed:
        interaction.response.send_message.assert_not_awaited()
    else:
        interaction.response.send_message.assert_awaited_once()
        assert "#musica" in interaction.response.send_message.call_args.args[0]


def test_measurement_command_has_correct_registered_name() -> None:
    names = {command.name for command in Music.__cog_app_commands__}
    assert "cuantomemide" in names
    assert "cuandtomemide" not in names


def test_wrong_channel_messages_have_varied_copy(monkeypatch) -> None:
    from personal_music_bot import messages

    variants = messages._WRONG_CHANNEL
    assert len(set(variants)) >= 10
    for variant in variants:
        monkeypatch.setattr(messages, "choice", lambda _options, variant=variant: variant)
        assert messages.wrong_channel_message() == variant
        assert "#musica" in variant
