from __future__ import annotations

from datetime import datetime, timezone

import pytest

from personal_music_bot.media import Track
from personal_music_bot.statistics import StatisticsStore


def track(title: str, url: str, requester_id: int, requester_name: str) -> Track:
    return Track(
        title=title,
        webpage_url=url,
        duration=180,
        requester_id=requester_id,
        requester_name=requester_name,
    )


@pytest.mark.asyncio
async def test_monthly_stats_rank_tracks_and_requesters(tmp_path) -> None:
    store = StatisticsStore(tmp_path / "stats.sqlite3")
    august = datetime(2026, 8, 15, tzinfo=timezone.utc)
    september = datetime(2026, 9, 2, tzinfo=timezone.utc)
    tren = track("Tren al sur", "https://example.com/tren", 10, "Alberto")
    baile = track("El baile", "https://example.com/baile", 20, "Beatriz")

    await store.record_play(1, tren, played_at=september)
    await store.record_play(1, tren, played_at=september)
    await store.record_play(1, baile, played_at=september)
    await store.record_play(1, baile, played_at=august)
    await store.record_play(2, baile, played_at=september)

    result = await store.monthly(1, reference=september)

    assert result.total_plays == 3
    assert [(item.title, item.plays) for item in result.tracks] == [
        ("Tren al sur", 2),
        ("El baile", 1),
    ]
    assert [(item.requester_name, item.plays) for item in result.requesters] == [
        ("Alberto", 2),
        ("Beatriz", 1),
    ]


@pytest.mark.asyncio
async def test_monthly_stats_are_empty_without_plays(tmp_path) -> None:
    store = StatisticsStore(tmp_path / "stats.sqlite3")

    result = await store.monthly(
        1,
        reference=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )

    assert result.total_plays == 0
    assert result.tracks == ()
    assert result.requesters == ()
