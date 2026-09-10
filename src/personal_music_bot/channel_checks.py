from __future__ import annotations

import discord
from discord import app_commands

from personal_music_bot.messages import wrong_channel_message


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
        return await check_music_channel(interaction)
