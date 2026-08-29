from __future__ import annotations

import logging

from personal_music_bot.bot import create_bot
from personal_music_bot.config import Settings


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    bot = create_bot(settings)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()

