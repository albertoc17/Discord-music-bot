from __future__ import annotations

import logging

import discord
from discord.ext import commands

from personal_music_bot.config import Settings
from personal_music_bot.music import Music
from personal_music_bot.system_status import SystemStatus

logger = logging.getLogger(__name__)


class PersonalAssistantBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(command_prefix=settings.command_prefix, intents=intents)
        self.settings = settings

    async def setup_hook(self) -> None:
        await self.add_cog(Music(self, self.settings))
        await self.add_cog(SystemStatus(self))
        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Sincronizados %s comandos en el servidor de desarrollo", len(synced))
        else:
            synced = await self.tree.sync()
            logger.info("Sincronizados %s comandos globales", len(synced))

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Conectado como %s (ID: %s)", self.user, self.user.id)
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="/play",
                )
            )


def create_bot(settings: Settings) -> PersonalAssistantBot:
    return PersonalAssistantBot(settings)

