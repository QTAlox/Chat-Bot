"""
main.py — ponto de entrada do projeto.
"""

import asyncio
from config import settings


async def main():
    settings.validate()

    from platforms.discord.client import DiscordClient
    client = DiscordClient()
    await client.start()


if __name__ == "__main__":
    asyncio.run(main())
