from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import yt_dlp


class MediaError(RuntimeError):
    """Error comprensible al buscar o preparar contenido multimedia."""


@dataclass(frozen=True, slots=True)
class Track:
    title: str
    webpage_url: str
    duration: int | None
    requester_id: int
    requester_name: str
    thumbnail: str | None = None


@dataclass(frozen=True, slots=True)
class Stream:
    url: str
    title: str


class MediaResolver:
    def __init__(self, max_playlist_items: int) -> None:
        self.max_playlist_items = max_playlist_items
        self._search_options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "default_search": "ytsearch1",
            "extract_flat": "in_playlist",
            "noplaylist": False,
        }
        self._stream_options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "bestaudio/best",
            "noplaylist": True,
        }

    async def search(
        self, query: str, requester_id: int, requester_name: str
    ) -> list[Track]:
        try:
            info = await asyncio.to_thread(self._extract, query, self._search_options)
        except yt_dlp.utils.DownloadError as exc:
            raise MediaError("No pude encontrar o leer ese contenido.") from exc

        entries = info.get("entries") if isinstance(info, dict) else None
        raw_tracks = entries if entries is not None else [info]
        tracks: list[Track] = []
        for entry in raw_tracks[: self.max_playlist_items]:
            if not entry:
                continue
            webpage_url = entry.get("webpage_url") or entry.get("url")
            if not webpage_url:
                continue
            if not str(webpage_url).startswith(("http://", "https://")):
                extractor = entry.get("ie_key", "").lower()
                if extractor == "youtube" or entry.get("extractor", "").startswith("youtube"):
                    webpage_url = f"https://www.youtube.com/watch?v={webpage_url}"
            tracks.append(
                Track(
                    title=entry.get("title") or "Pista sin titulo",
                    webpage_url=str(webpage_url),
                    duration=entry.get("duration"),
                    requester_id=requester_id,
                    requester_name=requester_name,
                    thumbnail=entry.get("thumbnail"),
                )
            )

        if not tracks:
            raise MediaError("No encontre pistas reproducibles para esa busqueda.")
        return tracks

    async def stream_for(self, track: Track) -> Stream:
        try:
            info = await asyncio.to_thread(
                self._extract, track.webpage_url, self._stream_options
            )
        except yt_dlp.utils.DownloadError as exc:
            raise MediaError(f"No pude preparar **{track.title}** para reproducir.") from exc

        if "entries" in info:
            info = next((entry for entry in info["entries"] if entry), {})
        stream_url = info.get("url")
        if not stream_url:
            raise MediaError(f"No encontre una fuente de audio para **{track.title}**.")
        return Stream(url=stream_url, title=info.get("title") or track.title)

    @staticmethod
    def _extract(query: str, options: dict[str, Any]) -> dict[str, Any]:
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info(query, download=False)
        if not isinstance(result, dict):
            raise MediaError("La fuente devolvio una respuesta inesperada.")
        return result


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "duracion desconocida"
    minutes, remaining_seconds = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes}:{remaining_seconds:02d}"

