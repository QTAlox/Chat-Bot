"""
platforms/discord/client.py
============================
Selfbot do Discord usando conta NORMAL (discord.py-self).
ATENÇÃO: use uma conta dedicada — viola os Termos de Serviço do Discord.
"""

import asyncio
import random
import time

import discord

from config import settings
from core import memory, brain
from core.decision_engine import should_respond, register_response
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

    async def on_message(self, message: discord.Message):
        # Ignora a própria conta
        if message.author == self.user:
            return

        # Ignora DMs
        if not message.guild:
            return

        # Filtra servidor
        if message.guild.id not in settings.ALLOWED_GUILD_IDS:
            return

        # Filtra canais ignorados
        if message.channel.id in settings.IGNORED_CHANNEL_IDS:
            return

        # Filtra canais permitidos (se definido)
        if settings.ALLOWED_CHANNEL_IDS:
            if message.channel.id not in settings.ALLOWED_CHANNEL_IDS:
                return

        # Ignora mensagens vazias
        if not message.content.strip():
            return

        # Salva na memória de curto prazo
        msg = Message(
            author_id=message.author.id,
            author_name=message.author.display_name,
            content=message.content,
            timestamp=time.time(),
        )
        memory.add_message(message.channel.id, msg)

        # Aprende o estilo do usuário em background
        asyncio.create_task(
            memory.learn_from_message(
                message.author.id,
                message.author.display_name,
                message.content,
            )
        )

        # Decide se responde
        replied_to_id = (
            message.reference.message_id if message.reference else None
        )
        last_sent = self._last_sent_id.get(message.channel.id)

        respond, reason = should_respond(
            message_content=message.content,
            message_author_id=message.author.id,
            channel_id=message.channel.id,
            bot_last_message_id=last_sent,
            replied_to_id=replied_to_id,
        )

        status = "-> RESPONDE" if respond else "-> silencio"
        print(f"[CHAT] #{message.channel.name} | "
              f"{message.author.display_name}: "
              f"{message.content[:55]}{'...' if len(message.content) > 55 else ''} "
              f"{status} ({reason})")

        if not respond:
            return

        # Delay humano
        delay = random.uniform(settings.RESPONSE_DELAY_MIN,
                               settings.RESPONSE_DELAY_MAX)
        await asyncio.sleep(delay)

        # Digita e gera resposta
        async with message.channel.typing():
            reply = await brain.get_response(message.channel.id)

        if not reply:
            return

        sent = await message.channel.send(reply)

        self._last_sent_id[message.channel.id] = sent.id
        register_response(message.channel.id)

        # Salva a própria resposta na memória
        memory.add_message(message.channel.id, Message(
            author_id=self.user.id,
            author_name=settings.PERSONA_NAME,
            content=reply,
            timestamp=time.time(),
        ))

        # Loga no banco
        asyncio.create_task(
            memory.log_interaction(
                message.channel.id,
                message.author.id,
                message.content,
                reply,
            )
        )

        print(f"[DISCORD] Enviou: {reply[:70]}{'...' if len(reply) > 70 else ''}")
