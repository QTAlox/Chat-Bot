"""
platforms/discord/client.py
============================
Selfbot com: memória persistente, aprendizado automático,
comandos do dono, busca web e modo arrombado.
"""

import asyncio
import random
import time

import discord

from config import settings
from core import memory, brain
from core.owner import is_owner, is_silent, handle_owner_command
from core.training import learn_from_channel, get_cached_style, CACHE_TTL
from core.decision_engine import (
    should_respond, register_response,
    should_send_spontaneous, register_spontaneous,
    get_spontaneous_message,
)
from core.memory import Message, load_buffer, save_all_buffers


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
        await self._restore_memory()
        asyncio.create_task(self._learn_all_channels())
        asyncio.create_task(self._spontaneous_loop())
        asyncio.create_task(self._relearn_loop())
        asyncio.create_task(self._autosave_loop())
        print(f"[DISCORD] Pronto!")

    # ── Memória ───────────────────────────────────────────────────────
    async def _restore_memory(self):
        print("[MEMORY] Restaurando memória anterior...")
        for guild in self.guilds:
            if guild.id not in settings.ALLOWED_GUILD_IDS:
                continue
            for channel in guild.text_channels:
                if channel.id in settings.IGNORED_CHANNEL_IDS:
                    continue
                if settings.ALLOWED_CHANNEL_IDS and channel.id not in settings.ALLOWED_CHANNEL_IDS:
                    continue
                await load_buffer(channel.id)

    async def _autosave_loop(self):
        while True:
            await asyncio.sleep(300)
            await save_all_buffers()

    async def close(self):
        print("[MEMORY] Salvando memória antes de desligar...")
        await save_all_buffers()
        await super().close()

    # ── Aprendizado ───────────────────────────────────────────────────
    async def _learn_all_channels(self):
        ai_client = brain.get_ai_client()
        for guild in self.guilds:
            if guild.id not in settings.ALLOWED_GUILD_IDS:
                continue
            for channel in guild.text_channels:
                if channel.id in settings.IGNORED_CHANNEL_IDS:
                    continue
                if settings.ALLOWED_CHANNEL_IDS and channel.id not in settings.ALLOWED_CHANNEL_IDS:
                    continue
                if get_cached_style(channel.id):
                    continue
                await learn_from_channel(channel, ai_client)
                await asyncio.sleep(2)

    async def _relearn_loop(self):
        while True:
            await asyncio.sleep(CACHE_TTL)
            print("[TRAINING] Atualizando estilo...")
            await self._learn_all_channels()

    # ── Espontâneas ───────────────────────────────────────────────────
    async def _spontaneous_loop(self):
        await asyncio.sleep(60)
        while True:
            try:
                if not is_silent():
                    for guild in self.guilds:
                        if guild.id not in settings.ALLOWED_GUILD_IDS:
                            continue
                        for channel in guild.text_channels:
                            if channel.id in settings.IGNORED_CHANNEL_IDS:
                                continue
                            if settings.ALLOWED_CHANNEL_IDS and channel.id not in settings.ALLOWED_CHANNEL_IDS:
                                continue
                            send, _ = should_send_spontaneous(channel.id)
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
            except Exception as e:
                print(f"[LOOP] Erro: {e}")
            await asyncio.sleep(60)

    # ── Evento principal ──────────────────────────────────────────────
    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)

        # ── Comandos do dono (DM ou menção no servidor) ──────────────
        if is_owner(message.author.id):
            # Em DM: qualquer mensagem é comando
            # No servidor: só se mencionar o bot ou usar !felipe
            is_command = is_dm or (
                self.user in message.mentions or
                message.content.lower().startswith("!felipe")
            )
            if is_command:
                response = await handle_owner_command(message, self)
                if response:
                    await message.channel.send(response)
                return

        # Ignora DMs de não-donos
        if is_dm:
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

        # Silêncio ativo (exceto para o dono)
        if is_silent():
            return

        content = message.content.strip()
        msg = Message(
            author_id=message.author.id,
            author_name=message.author.display_name,
            content=content,
            timestamp=time.time(),
        )
        memory.add_message(message.channel.id, msg)

        asyncio.create_task(
            memory.learn_from_message(
                message.author.id,
                message.author.display_name,
                content,
            )
        )

        replied_to_id = (
            message.reference.message_id if message.reference else None
        )
        last_sent    = self._last_sent_id.get(message.channel.id)
        bot_user_id  = self.user.id if self.user else None

        respond, reason = should_respond(
            message_content=content,
            message_author_id=message.author.id,
            channel_id=message.channel.id,
            bot_last_message_id=last_sent,
            replied_to_id=replied_to_id,
            bot_user_id=bot_user_id,
        )

        status = "-> RESPONDE" if respond else "-> silencio"
        print(f"[CHAT] #{message.channel.name} | "
              f"{message.author.display_name}: "
              f"{content[:55]}{'...' if len(content) > 55 else ''} "
              f"{status} ({reason})")

        if not respond:
            return

        delay = random.uniform(settings.RESPONSE_DELAY_MIN,
                               settings.RESPONSE_DELAY_MAX)
        await asyncio.sleep(delay)

        async with message.channel.typing():
            reply, links = await brain.get_response(message.channel.id, content)

        if not reply:
            return

        # Envia resposta + links separados se houver
        await message.channel.send(reply)
        if links:
            await asyncio.sleep(0.5)
            await message.channel.send(links)

        self._last_sent_id[message.channel.id] = (
            await message.channel.fetch_message(message.channel.last_message_id)
        ).id if message.channel.last_message_id else last_sent

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
                content,
                reply,
            )
        )
