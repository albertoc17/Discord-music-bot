from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un numero entero") from exc
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero")
    return value


def _volume(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un numero") from exc
    if not 0 <= value <= 1:
        raise ValueError(f"{name} debe estar entre 0 y 1")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    guild_id: int | None = None
    command_prefix: str = "!"
    default_volume: float = 0.7
    idle_timeout_seconds: int = 300
    max_playlist_items: int = 50
    ffmpeg_executable: str = "ffmpeg"
    audio_bitrate: str = "128k"
    stats_database_path: str = "data/arturo_stats.sqlite3"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Falta DISCORD_TOKEN. Copia .env.example a .env y agrega el token del bot."
            )

        guild_id_text = os.getenv("DISCORD_GUILD_ID", "").strip()
        try:
            guild_id = int(guild_id_text) if guild_id_text else None
        except ValueError as exc:
            raise ValueError("DISCORD_GUILD_ID debe ser un numero entero") from exc

        return cls(
            discord_token=token,
            guild_id=guild_id,
            command_prefix=os.getenv("COMMAND_PREFIX", "!"),
            default_volume=_volume("DEFAULT_VOLUME", 0.7),
            idle_timeout_seconds=_positive_int("IDLE_TIMEOUT_SECONDS", 300),
            max_playlist_items=_positive_int("MAX_PLAYLIST_ITEMS", 50),
            ffmpeg_executable=os.getenv("FFMPEG_EXECUTABLE", "ffmpeg"),
            audio_bitrate=os.getenv("AUDIO_BITRATE", "128k"),
            stats_database_path=os.getenv(
                "STATS_DATABASE_PATH", "data/arturo_stats.sqlite3"
            ),
        )

