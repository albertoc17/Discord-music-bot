from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from personal_music_bot.config import Settings
from personal_music_bot.media import MediaError, MediaResolver, format_duration
from personal_music_bot.player import GuildPlayer, PlayerManager

logger = logging.getLogger(__name__)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.resolver = MediaResolver(settings.max_playlist_items)
        self.players = PlayerManager(
            resolver=self.resolver,
            ffmpeg_executable=settings.ffmpeg_executable,
            volume=settings.default_volume,
            idle_timeout=settings.idle_timeout_seconds,
        )

    async def cog_unload(self) -> None:
        await self.players.close_all()

    async def _connect(self, interaction: discord.Interaction) -> GuildPlayer:
        if not interaction.guild or not interaction.guild_id:
            raise MusicCommandError("Este comando solo funciona dentro de un servidor.")

        member = interaction.user
        if not isinstance(member, discord.Member):
            raise MusicCommandError("Primero entra a un canal de voz.")

        voice_state = member.voice
        if not voice_state or not voice_state.channel:
            try:
                voice_state = await member.fetch_voice()
            except discord.NotFound as exc:
                raise MusicCommandError("Primero entra a un canal de voz.") from exc
            except discord.Forbidden as exc:
                logger.warning(
                    "Discord nego consultar el estado de voz del usuario %s en el servidor %s",
                    member.id,
                    interaction.guild_id,
                )
                raise MusicCommandError(
                    "No pude consultar tu canal de voz. Revisa los permisos Ver canal, "
                    "Conectar y Hablar de King Arturo."
                ) from exc
            except discord.HTTPException as exc:
                logger.warning(
                    "Fallo al consultar el estado de voz del usuario %s: %s",
                    member.id,
                    exc,
                )
                raise MusicCommandError(
                    "Discord no permitio consultar tu canal de voz. Intenta de nuevo."
                ) from exc

        voice_channel = voice_state.channel
        if not isinstance(voice_channel, (discord.VoiceChannel, discord.StageChannel)):
            raise MusicCommandError("Primero entra a un canal de voz.")

        voice = interaction.guild.voice_client
        if voice and voice.channel != voice_channel:
            await voice.move_to(voice_channel)
        elif not voice:
            voice = await voice_channel.connect()

        player = self.players.get(interaction.guild_id)
        player.set_voice(voice)

        async def send_status(message: str) -> None:
            channel = interaction.channel
            if channel and hasattr(channel, "send"):
                await channel.send(message)

        player.set_status_callback(send_status)
        return player

    def _player(self, interaction: discord.Interaction) -> GuildPlayer:
        if not interaction.guild_id:
            raise MusicCommandError("Este comando solo funciona dentro de un servidor.")
        player = self.players.find(interaction.guild_id)
        if not player:
            raise MusicCommandError("No hay un reproductor activo en este servidor.")
        return player

    @app_commands.command(name="play", description="Busca o agrega una URL a la cola")
    @app_commands.describe(busqueda="Nombre, URL de una pista o URL de una playlist")
    async def play(self, interaction: discord.Interaction, busqueda: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            player = await self._connect(interaction)
            tracks = await self.resolver.search(
                busqueda,
                requester_id=interaction.user.id,
                requester_name=interaction.user.display_name,
            )
            player.enqueue(tracks)
        except (MusicCommandError, MediaError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if len(tracks) == 1:
            track = tracks[0]
            await interaction.followup.send(
                f"Agregada a la cola: **{track.title}** ({format_duration(track.duration)})"
            )
        else:
            await interaction.followup.send(
                f"Agregue **{len(tracks)} pistas** a la cola "
                f"(limite: {self.resolver.max_playlist_items})."
            )

    @app_commands.command(name="pause", description="Pausa la musica")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if not player.voice or not player.voice.is_playing():
            raise MusicCommandError("No hay musica sonando.")
        player.voice.pause()
        await interaction.response.send_message("Musica pausada.")

    @app_commands.command(name="resume", description="Continua la musica pausada")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if not player.voice or not player.voice.is_paused():
            raise MusicCommandError("La musica no esta pausada.")
        player.voice.resume()
        await interaction.response.send_message("Continuamos.")

    @app_commands.command(name="skip", description="Salta la pista actual")
    async def skip(self, interaction: discord.Interaction) -> None:
        if not self._player(interaction).skip():
            raise MusicCommandError("No hay ninguna pista para saltar.")
        await interaction.response.send_message("Pista saltada.")

    @app_commands.command(name="stop", description="Detiene la musica y vacia la cola")
    async def stop(self, interaction: discord.Interaction) -> None:
        removed = self._player(interaction).stop()
        await interaction.response.send_message(
            f"Reproduccion detenida. Quite {removed} pistas de la cola."
        )

    @app_commands.command(name="queue", description="Muestra las proximas pistas")
    async def show_queue(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        upcoming = player.queue
        if not player.current and not upcoming:
            raise MusicCommandError("La cola esta vacia.")

        lines: list[str] = []
        if player.current:
            lines.append(f"**Sonando:** {player.current.title}")
        if upcoming:
            lines.append("\n**A continuacion:**")
            lines.extend(
                f"{index}. {track.title} - {format_duration(track.duration)}"
                for index, track in enumerate(upcoming[:10], start=1)
            )
            if len(upcoming) > 10:
                lines.append(f"...y {len(upcoming) - 10} mas.")
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="nowplaying", description="Muestra la pista actual")
    async def now_playing(self, interaction: discord.Interaction) -> None:
        track = self._player(interaction).current
        if not track:
            raise MusicCommandError("No hay musica sonando.")
        embed = discord.Embed(
            title="Ahora suena",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Duracion", value=format_duration(track.duration))
        embed.add_field(name="Pedido por", value=track.requester_name)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leave", description="Desconecta el bot del canal de voz")
    async def leave(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        player.stop()
        if player.voice and player.voice.is_connected():
            await player.voice.disconnect(force=True)
            player.voice = None
        await interaction.response.send_message("Me desconecte del canal de voz.")

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = getattr(error, "original", error)
        if isinstance(original, MusicCommandError):
            message = str(original)
        else:
            message = "Ocurrio un error inesperado al ejecutar el comando."
            logger.error(
                "Fallo al ejecutar un comando de musica",
                exc_info=(type(original), original, original.__traceback__),
            )
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class MusicCommandError(app_commands.AppCommandError):
    pass
