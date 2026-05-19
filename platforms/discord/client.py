"""
platforms/discord/client.py
"""

import asyncio
import random
import time

import discord

from config import settings
from core import memory, brain
from core.decision_engine import (
    should_respond, register_response,
    should_send_spontaneous, register_spontaneous,
    get_spontaneous_message,
)
from core.memory import Message


class DiscordClient(discord.Client):

    def __init__(self):
        super().__init__(chunk_guilds_at_startup=False)
        self._last_sent_id: dict[int, int] = {}

    async def start(self):
        print(f"[DISCORD] Iniciando como '{settings.PERSONA_NAME}'...")
        await memory.init_db()
        await super().start(settings.DISCORD_TOKEN)

    async def on_ready(self):
        print(f"[DISCORD] Conectado como: {self.user}")
        print(f"[DISCORD] Servidores: {[g.name for g in self.guilds]}")
        print(f"[DISCORD] Pronto para conversar!")
        asyncio.create_task(self._spontaneous_loop())

    async def _spontaneous_loop(self):
        await asyncio.sleep(60)
        while True:
            try:
                for guild in self.guilds:
                    if guild.id not in settings.ALLOWED_GUILD_IDS:
                        continue
                    for channel in guild.text_channels:
                        if channel.id in settings.IGNORED_CHANNEL_IDS:
                            continue
                        if settings.ALLOWED_CHANNEL_IDS and channel.id not in settings.ALLOWED_CHANNEL_IDS:
                            continue
                        send, reason = should_send_spontaneous(channel.id)
                        if send:
                            msg = get_spontaneous_message()
                            await asyncio.sleep(random.uniform(2, 6))
                            await channel.send(msg)
                            register_spontaneous(channel.id)
                            memory.add_message(channel.id, Message(
                                author_id=self.user.id,
                                author_name=settings.PERSONA_NAME,
                                content=msg,
                                timestamp=time.time(),
                            ))
                            print(f"[ESPONTANEA] #{channel.name}: {msg}")
            except Exception as e:
                print(f"[LOOP] Erro: {e}")
            await asyncio.sleep(60)

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        if not message.guild:
            return
        if message.guild.id not in settings.ALLOWED_GUILD_IDS:
            return
        if message.channel.id in settings.IGNORED_CHANNEL_IDS:
            return
        if settings.ALLOWED_CHANNEL_IDS and message.channel.id not in settings.ALLOWED_CHANNEL_IDS:
            return
        if not message.content.strip():
            return

        # Ignora mensagens que são só um nome/menção sem conteúdo real
        # Ex: alguém só digita "felipe" — salva na memória mas não responde sozinho
        content_stripped = message.content.strip()

        msg = Message(
            author_id=message.author.id,
            author_name=message.author.display_name,
            content=content_stripped,
            timestamp=time.time(),
        )
        memory.add_message(message.channel.id, msg)

        asyncio.create_task(
            memory.learn_from_message(
                message.author.id,
                message.author.display_name,
                content_stripped,
            )
        )

        replied_to_id = (
            message.reference.message_id if message.reference else None
        )
        last_sent = self._last_sent_id.get(message.channel.id)

        respond, reason = should_respond(
            message_content=content_stripped,
            message_author_id=message.author.id,
            channel_id=message.channel.id,
            bot_last_message_id=last_sent,
            replied_to_id=replied_to_id,
        )

        status = "-> RESPONDE" if respond else "-> silencio"
        print(f"[CHAT] #{message.channel.name} | "
              f"{message.author.display_name}: "
              f"{content_stripped[:55]}{'...' if len(content_stripped) > 55 else ''} "
              f"{status} ({reason})")

        if not respond:
            return

        delay = random.uniform(settings.RESPONSE_DELAY_MIN,
                               settings.RESPONSE_DELAY_MAX)
        await asyncio.sleep(delay)

        async with message.channel.typing():
            reply = await brain.get_response(message.channel.id)

        if not reply:
            return

        sent = await message.channel.send(reply)
        self._last_sent_id[message.channel.id] = sent.id
        register_response(message.channel.id)

        memory.add_message(message.channel.id, Message(
            author_id=self.user.id,
            author_name=settings.PERSONA_NAME,
            content=reply,
            timestamp=time.time(),
        ))

        asyncio.create_task(
            memory.log_interaction(
                message.channel.id,
                message.author.id,
                content_stripped,
                reply,
            )
        )

        print(f"[DISCORD] Enviou: {reply[:70]}{'...' if len(reply) > 70 else ''}")
