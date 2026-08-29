from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from personal_music_bot.config import Settings
from personal_music_bot.media import MediaError, MediaResolver, Track, format_duration
from personal_music_bot.messages import (
    leaving_message,
    not_found_message,
    playlist_queued_message,
    searching_message,
    track_queued_message,
)
from personal_music_bot.player import GuildPlayer, PlayerManager

logger = logging.getLogger(__name__)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self._control_panels: dict[int, discord.Message] = {}
        self.resolver = MediaResolver(settings.max_playlist_items)
        self.players = PlayerManager(
            resolver=self.resolver,
            ffmpeg_executable=settings.ffmpeg_executable,
            volume=settings.default_volume,
            idle_timeout=settings.idle_timeout_seconds,
        )
        self._persistent_controls = MusicControls(self)
        self.bot.add_view(self._persistent_controls)

    async def cog_unload(self) -> None:
        self._persistent_controls.stop()
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

        async def update_panel(_track: Track | None) -> None:
            await self._update_control_panel(interaction.guild_id)

        player.set_track_callback(update_panel)
        await self._ensure_control_panel(interaction.guild_id, voice_channel, player)
        return player

    @staticmethod
    def _control_panel_embed(player: GuildPlayer) -> discord.Embed:
        track = player.current
        if track:
            description = f"[{track.title}]({track.webpage_url})"
            color = discord.Color.green()
        else:
            description = "No hay ninguna weá sonando ahora mismo."
            color = discord.Color.blurple()

        embed = discord.Embed(
            title="🎛️ Panel de Arturo",
            description=description,
            color=color,
        )
        if track:
            embed.add_field(name="Duración", value=format_duration(track.duration))
            embed.add_field(name="Pedido por", value=track.requester_name)
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
        embed.add_field(name="En cola", value=str(len(player.queue)))
        embed.set_footer(text="Usa los botones para controlar la música")
        return embed

    async def _ensure_control_panel(
        self,
        guild_id: int,
        voice_channel: discord.VoiceChannel | discord.StageChannel,
        player: GuildPlayer,
    ) -> None:
        embed = self._control_panel_embed(player)
        existing = self._control_panels.get(guild_id)
        if existing and existing.channel.id == voice_channel.id:
            try:
                await existing.edit(embed=embed, view=MusicControls(self))
                return
            except discord.NotFound:
                self._control_panels.pop(guild_id, None)
            except discord.HTTPException as exc:
                logger.warning("No se pudo refrescar el panel en guild %s: %s", guild_id, exc)
                return

        try:
            panel = await voice_channel.send(embed=embed, view=MusicControls(self))
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("No se pudo publicar el panel en guild %s: %s", guild_id, exc)
            return
        self._control_panels[guild_id] = panel

    async def _update_control_panel(self, guild_id: int) -> None:
        panel = self._control_panels.get(guild_id)
        player = self.players.find(guild_id)
        if not panel or not player:
            return
        try:
            await panel.edit(embed=self._control_panel_embed(player), view=MusicControls(self))
        except discord.NotFound:
            self._control_panels.pop(guild_id, None)
        except discord.HTTPException as exc:
            logger.warning("No se pudo actualizar el panel en guild %s: %s", guild_id, exc)

    async def _search_and_enqueue(
        self,
        query: str,
        requester: discord.Member | discord.User,
        player: GuildPlayer,
    ) -> list[Track]:
        tracks = await self.resolver.search(
            query,
            requester_id=requester.id,
            requester_name=requester.display_name,
        )
        player.enqueue(tracks)
        await self._update_control_panel(player.guild_id)
        return tracks

    @staticmethod
    def _queued_message(tracks: list[Track], playlist_limit: int) -> str:
        if len(tracks) == 1:
            track = tracks[0]
            return track_queued_message(track.title, format_duration(track.duration))
        return playlist_queued_message(
            count=len(tracks),
            limit=playlist_limit,
        )

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
        await interaction.response.send_message(searching_message())
        try:
            player = await self._connect(interaction)
            tracks = await self._search_and_enqueue(busqueda, interaction.user, player)
        except MusicCommandError as exc:
            await interaction.edit_original_response(content=str(exc))
            return
        except MediaError:
            await interaction.edit_original_response(content=not_found_message())
            return

        await interaction.edit_original_response(
            content=self._queued_message(tracks, self.resolver.max_playlist_items)
        )

    @app_commands.command(name="pause", description="Pausa la musica")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if not player.voice or not player.voice.is_playing():
            raise MusicCommandError("No está sonando ni una weá ahora mismo.")
        player.voice.pause()
        await interaction.response.send_message("Ya, dejé la música en pausa. ⏸️")

    @app_commands.command(name="resume", description="Continua la musica pausada")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if not player.voice or not player.voice.is_paused():
            raise MusicCommandError("La música no está pausada, po.")
        player.voice.resume()
        await interaction.response.send_message("Ya po, seguimos con la música. ▶️")

    @app_commands.command(name="skip", description="Salta la pista actual")
    async def skip(self, interaction: discord.Interaction) -> None:
        if not self._player(interaction).skip():
            raise MusicCommandError("No hay ningún tema pa saltar.")
        await interaction.response.send_message("Chao nomás con ese tema. Vamos al siguiente.")

    @app_commands.command(name="stop", description="Detiene la musica y vacia la cola")
    async def stop(self, interaction: discord.Interaction) -> None:
        removed = self._player(interaction).stop()
        await interaction.response.send_message(
            f"Corté la música y saqué {removed} temas de la cola. Quedó todo impeque."
        )

    @app_commands.command(name="queue", description="Muestra las proximas pistas")
    async def show_queue(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        upcoming = player.queue
        if not player.current and not upcoming:
            raise MusicCommandError("La cola está más pelada que rodilla de cabro chico.")

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
            raise MusicCommandError("No está sonando ni una weá ahora mismo.")
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
        await self._update_control_panel(player.guild_id)
        await interaction.response.send_message(leaving_message())

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


class MusicControls(discord.ui.View):
    def __init__(self, music: Music) -> None:
        super().__init__(timeout=None)
        self.music = music

    async def _player_for(self, interaction: discord.Interaction) -> GuildPlayer | None:
        if not interaction.guild_id or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este panel funciona dentro del servidor, po.",
                ephemeral=True,
            )
            return None

        player = self.music.players.find(interaction.guild_id)
        if not player or not player.voice or not player.voice.is_connected():
            await interaction.response.send_message(
                "Arturo no está conectado a ningún canal de voz.",
                ephemeral=True,
            )
            return None

        member_channel = interaction.user.voice.channel if interaction.user.voice else None
        if member_channel != player.voice.channel:
            await interaction.response.send_message(
                "Métete al mismo canal de voz que Arturo para usar los botones, po.",
                ephemeral=True,
            )
            return None
        return player

    @discord.ui.button(
        label="Play / Pausa",
        emoji="⏯️",
        style=discord.ButtonStyle.primary,
        custom_id="arturo:music:toggle",
    )
    async def toggle_playback(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[MusicControls],
    ) -> None:
        player = await self._player_for(interaction)
        if not player or not player.voice:
            return

        if player.voice.is_paused():
            player.voice.resume()
            message = "Ya po, seguimos con la música. ▶️"
        elif player.voice.is_playing():
            player.voice.pause()
            message = "Ya, dejé la música en pausa. ⏸️"
        else:
            message = "No está sonando ni una weá ahora mismo."
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(
        label="Stop",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="arturo:music:stop",
    )
    async def stop_music(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[MusicControls],
    ) -> None:
        player = await self._player_for(interaction)
        if not player:
            return

        removed = player.stop()
        await self.music._update_control_panel(player.guild_id)
        await interaction.response.send_message(
            f"Corté la música y saqué {removed} temas de la cola.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Siguiente",
        emoji="⏭️",
        style=discord.ButtonStyle.secondary,
        custom_id="arturo:music:next",
    )
    async def next_track(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[MusicControls],
    ) -> None:
        player = await self._player_for(interaction)
        if not player:
            return

        if not player.skip():
            await interaction.response.send_message(
                "No hay ningún tema pa saltar.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Chao nomás con ese tema. Vamos al siguiente.",
            ephemeral=True,
        )
