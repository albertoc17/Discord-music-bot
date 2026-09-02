from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from personal_music_bot.media import Track


@dataclass(frozen=True, slots=True)
class TrackRanking:
    title: str
    webpage_url: str
    plays: int


@dataclass(frozen=True, slots=True)
class RequesterRanking:
    requester_id: int
    requester_name: str
    plays: int


@dataclass(frozen=True, slots=True)
class MonthlyStats:
    year: int
    month: int
    total_plays: int
    tracks: tuple[TrackRanking, ...]
    requesters: tuple[RequesterRanking, ...]


class StatisticsStore:
    """Guarda reproducciones reales y genera rankings mensuales por servidor."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS plays (
                    id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    track_title TEXT NOT NULL,
                    webpage_url TEXT NOT NULL,
                    requester_id INTEGER NOT NULL,
                    requester_name TEXT NOT NULL,
                    played_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS plays_guild_date_idx
                ON plays (guild_id, played_at);
                """
            )

    async def record_play(
        self,
        guild_id: int,
        track: Track,
        *,
        played_at: datetime | None = None,
    ) -> None:
        timestamp = (played_at or datetime.now().astimezone()).timestamp()
        await asyncio.to_thread(self._record_play, guild_id, track, timestamp)

    def _record_play(self, guild_id: int, track: Track, timestamp: float) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO plays (
                    guild_id, track_title, webpage_url,
                    requester_id, requester_name, played_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    track.title,
                    track.webpage_url,
                    track.requester_id,
                    track.requester_name,
                    timestamp,
                ),
            )

    async def monthly(
        self,
        guild_id: int,
        *,
        reference: datetime | None = None,
        limit: int = 5,
    ) -> MonthlyStats:
        if limit <= 0:
            raise ValueError("limit debe ser mayor que cero")

        current = reference or datetime.now().astimezone()
        if current.tzinfo is None:
            current = current.astimezone()
        start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        tracks, requesters, total = await asyncio.to_thread(
            self._monthly_query,
            guild_id,
            start.timestamp(),
            end.timestamp(),
            limit,
        )
        return MonthlyStats(
            year=start.year,
            month=start.month,
            total_plays=total,
            tracks=tracks,
            requesters=requesters,
        )

    def _monthly_query(
        self,
        guild_id: int,
        start_timestamp: float,
        end_timestamp: float,
        limit: int,
    ) -> tuple[tuple[TrackRanking, ...], tuple[RequesterRanking, ...], int]:
        parameters = (guild_id, start_timestamp, end_timestamp)
        with self._connect() as connection:
            total = connection.execute(
                """
                SELECT COUNT(*) FROM plays
                WHERE guild_id = ? AND played_at >= ? AND played_at < ?
                """,
                parameters,
            ).fetchone()[0]
            track_rows = connection.execute(
                """
                SELECT track_title, webpage_url, COUNT(*) AS play_count
                FROM plays
                WHERE guild_id = ? AND played_at >= ? AND played_at < ?
                GROUP BY webpage_url
                ORDER BY play_count DESC, track_title COLLATE NOCASE
                LIMIT ?
                """,
                (*parameters, limit),
            ).fetchall()
            requester_rows = connection.execute(
                """
                SELECT requester_id, requester_name, COUNT(*) AS play_count
                FROM plays
                WHERE guild_id = ? AND played_at >= ? AND played_at < ?
                GROUP BY requester_id
                ORDER BY play_count DESC, requester_name COLLATE NOCASE
                LIMIT ?
                """,
                (*parameters, limit),
            ).fetchall()

        return (
            tuple(TrackRanking(*row) for row in track_rows),
            tuple(RequesterRanking(*row) for row in requester_rows),
            int(total),
        )
