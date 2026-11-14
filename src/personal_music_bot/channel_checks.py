from __future__ import annotations

import discord
from discord import app_commands

from personal_music_bot.messages import wrong_channel_message

MUSIC_ONLY_COMMANDS = {
    "play",
    "pause",
    "resume",
    "skip",
    "stop",
    "queue",
    "nowplaying",
    "leave",
    "stats",
    "quality",
    "volume",
}


async def check_music_channel(interaction: discord.Interaction) -> bool:
    channel = interaction.channel
    if (
        interaction.guild_id is not None
        and isinstance(channel, discord.TextChannel)
        and channel.name == "musica"
    ):
        return True

    await interaction.response.send_message(
        wrong_channel_message(),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    return False


class MusicChannelCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # The tree check runs before discord.py resolves interaction.command.
        data = interaction.data or {}
        if (
            data.get("name") not in MUSIC_ONLY_COMMANDS
            and interaction.guild_id is not None
            and isinstance(interaction.channel, discord.TextChannel)
        ):
            return True
        return await check_music_channel(interaction)
