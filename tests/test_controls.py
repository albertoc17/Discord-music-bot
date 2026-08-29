from types import SimpleNamespace
from typing import cast

import pytest

from personal_music_bot.media import Track
from personal_music_bot.music import Music, MusicControls
from personal_music_bot.player import GuildPlayer


@pytest.mark.asyncio
async def test_music_controls_have_expected_buttons() -> None:
    controls = MusicControls(cast(Music, object()))

    assert controls.timeout is None
    assert [item.custom_id for item in controls.children] == [
        "arturo:music:toggle",
        "arturo:music:stop",
        "arturo:music:next",
    ]
    controls.stop()


def test_control_panel_embed_shows_now_playing() -> None:
    track = Track(
        title="Tren al sur",
        webpage_url="https://example.com/track",
        duration=245,
        requester_id=1,
        requester_name="Alberto",
    )
    player = cast(
        GuildPlayer,
        SimpleNamespace(current=track, queue=(track, track)),
    )

    embed = Music._control_panel_embed(player)

    assert embed.title == "🎛️ Panel de Arturo"
    assert embed.description == "[Tren al sur](https://example.com/track)"
    assert [field.value for field in embed.fields] == ["4:05", "Alberto", "2"]
