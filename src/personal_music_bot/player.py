from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable

import discord

from personal_music_bot.media import MediaError, MediaResolver, Track
from personal_music_bot.messages import now_playing_message, playback_failed_message

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], Awaitable[None]]
TrackCallback = Callable[[Track | None], Awaitable[None]]


class GuildPlayer:
    def __init__(
        self,
        guild_id: int,
        resolver: MediaResolver,
        ffmpeg_executable: str,
        volume: float,
        idle_timeout: int,
    ) -> None:
        self.guild_id = guild_id
        self.resolver = resolver
        self.ffmpeg_executable = ffmpeg_executable
        self.volume = volume
        self.idle_timeout = idle_timeout
        self.voice: discord.VoiceClient | None = None
        self.current: Track | None = None
        self._queue: deque[Track] = deque()
        self._queue_ready = asyncio.Event()
        self._next = asyncio.Event()
        self._status_callback: StatusCallback | None = None
        self._track_callback: TrackCallback | None = None
        self._cancel_current = False
        self._closed = False
        self._task = asyncio.create_task(self._player_loop(), name=f"player-{guild_id}")

    @property
    def queue(self) -> tuple[Track, ...]:
        return tuple(self._queue)

    def set_voice(self, voice: discord.VoiceClient) -> None:
        self.voice = voice
        if self._queue:
            self._queue_ready.set()

    def set_status_callback(self, callback: StatusCallback) -> None:
        self._status_callback = callback

    def set_track_callback(self, callback: TrackCallback) -> None:
        self._track_callback = callback

    def enqueue(self, tracks: list[Track]) -> None:
        self._queue.extend(tracks)
        self._queue_ready.set()

    def skip(self) -> bool:
        if not self.current:
            return False
        self._cancel_current = True
        if self.voice and (self.voice.is_playing() or self.voice.is_paused()):
            self.voice.stop()
        return True

    def clear(self) -> int:
        count = len(self._queue)
        self._queue.clear()
        self._queue_ready.clear()
        return count

    def stop(self) -> int:
        removed = self.clear()
        self.skip()
        return removed

    async def close(self) -> None:
        self._closed = True
        self._queue_ready.set()
        self.skip()
        if self.voice and self.voice.is_connected():
            await self.voice.disconnect(force=True)
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)

    async def _player_loop(self) -> None:
        while not self._closed:
            try:
                await asyncio.wait_for(self._queue_ready.wait(), timeout=self.idle_timeout)
            except TimeoutError:
                if self.voice and self.voice.is_connected() and not self.current:
                    await self.voice.disconnect(force=True)
                    self.voice = None
                continue

            if self._closed:
                return
            if not self._queue:
                self._queue_ready.clear()
                continue
            if not self.voice or not self.voice.is_connected():
                # Conserva la cola hasta que un nuevo /play vuelva a conectar el bot.
                self._queue_ready.clear()
                continue

            track = self._queue.popleft()
            if not self._queue:
                self._queue_ready.clear()
            self.current = track
            self._cancel_current = False
            self._next.clear()

            try:
                stream = await self.resolver.stream_for(track)
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(
                        stream.url,
                        executable=self.ffmpeg_executable,
                        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                        options="-vn",
                    ),
                    volume=self.volume,
                )
                if self._cancel_current:
                    source.cleanup()
                    continue
                loop = asyncio.get_running_loop()

                def after_playback(
                    error: Exception | None,
                    *,
                    event_loop: asyncio.AbstractEventLoop = loop,
                ) -> None:
                    if error:
                        logger.error("Error de reproduccion en guild %s: %s", self.guild_id, error)
                    event_loop.call_soon_threadsafe(self._next.set)

                self.voice.play(source, after=after_playback)
                await self._notify_track_changed(track)
                await self._notify(now_playing_message(track.title, track.requester_name))
                await self._next.wait()
            except (MediaError, discord.ClientException, OSError) as exc:
                logger.warning("No se pudo reproducir %s: %s", track.webpage_url, exc)
                await self._notify(playback_failed_message(track.title))
            except Exception:
                logger.exception("Fallo inesperado al reproducir %s", track.webpage_url)
                await self._notify(f"No pude reproducir **{track.title}**.")
            finally:
                self.current = None
                await self._notify_track_changed(None)

    async def _notify(self, message: str) -> None:
        if not self._status_callback:
            return
        try:
            await self._status_callback(message)
        except discord.HTTPException as exc:
            logger.warning("No se pudo enviar el estado en guild %s: %s", self.guild_id, exc)

    async def _notify_track_changed(self, track: Track | None) -> None:
        if not self._track_callback:
            return
        try:
            await self._track_callback(track)
        except discord.HTTPException as exc:
            logger.warning(
                "No se pudo actualizar el panel en guild %s: %s",
                self.guild_id,
                exc,
            )


class PlayerManager:
    def __init__(
        self,
        resolver: MediaResolver,
        ffmpeg_executable: str,
        volume: float,
        idle_timeout: int,
    ) -> None:
        self.resolver = resolver
        self.ffmpeg_executable = ffmpeg_executable
        self.volume = volume
        self.idle_timeout = idle_timeout
        self._players: dict[int, GuildPlayer] = {}

    def get(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer(
                guild_id=guild_id,
                resolver=self.resolver,
                ffmpeg_executable=self.ffmpeg_executable,
                volume=self.volume,
                idle_timeout=self.idle_timeout,
            )
        return self._players[guild_id]

    def find(self, guild_id: int) -> GuildPlayer | None:
        return self._players.get(guild_id)

    async def close_all(self) -> None:
        await asyncio.gather(*(player.close() for player in self._players.values()))
        self._players.clear()
