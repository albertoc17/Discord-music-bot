from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import discord
import psutil
from discord import app_commands
from discord.ext import commands

from personal_music_bot import __version__


@dataclass(frozen=True, slots=True)
class ProcessMetrics:
    cpu_percent: float
    memory_bytes: int
    memory_percent: float


def deployment_version(version_file: Path | None = None) -> str:
    environment_version = os.getenv("DEPLOY_VERSION", "").strip()
    if environment_version:
        return environment_version

    if version_file is None:
        version_file = Path(__file__).resolve().parents[2] / ".deploy-version"

    try:
        deployed_version = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        deployed_version = ""

    return deployed_version or f"v{__version__}"


def format_memory(byte_count: int) -> str:
    return f"{byte_count / (1024**2):.1f} MiB"


def status_embed(version: str, metrics: ProcessMetrics) -> discord.Embed:
    embed = discord.Embed(
        title="Estado de Arturo",
        description="El bot esta funcionando correctamente.",
        color=discord.Color.green(),
    )
    embed.add_field(name="Version", value=f"`{version}`", inline=False)
    embed.add_field(name="CPU", value=f"{metrics.cpu_percent:.1f}%")
    embed.add_field(
        name="Memoria",
        value=f"{format_memory(metrics.memory_bytes)} ({metrics.memory_percent:.1f}%)",
    )
    embed.set_footer(text="Consumo del proceso del bot")
    return embed


class SystemStatus(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.process = psutil.Process()

    def _read_metrics(self) -> ProcessMetrics:
        return ProcessMetrics(
            cpu_percent=self.process.cpu_percent(interval=0.1),
            memory_bytes=self.process.memory_info().rss,
            memory_percent=self.process.memory_percent(),
        )

    @app_commands.command(
        name="status",
        description="Muestra la version y el consumo de recursos del bot",
    )
    async def status(self, interaction: discord.Interaction) -> None:
        metrics = await asyncio.to_thread(self._read_metrics)
        await interaction.response.send_message(
            embed=status_embed(deployment_version(), metrics)
        )
