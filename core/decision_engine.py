"""
core/decision_engine.py
"""

import time
import random
from core.memory import get_recent_messages
from config import settings

_last_response_time: dict[int, float] = {}
_last_spontaneous: dict[int, float] = {}

CHANNEL_COOLDOWN     = 60
SPONTANEOUS_COOLDOWN = 300

INTEREST_KEYWORDS = [
    "f1", "formula 1", "formula1", "verstappen", "max", "hamilton", "ferrari",
    "red bull", "redbull", "gp", "grande premio", "corrida", "pit stop",
    "porsche", "911", "gt3", "supra", "mazda", "mercedes", "audi", "bmw",
    "carro", "turbo", "rebaixado",
    "bloons", "btd", "btd6", "valorant", "minecraft", "jogo", "game",
    "jogar", "ranked", "partida", "cs", "counter",
    "rick and morty", "rick", "morty", "serie", "série", "netflix",
    "filme", "cinema", "episodio",
    "joao gomes", "forro", "rock", "musica",
    "programacao", "codigo", "python", "bug",
    "meme", "twitter", "instagram", "tiktok",
]

DIRECTED_AT_BOT_PATTERNS = [
    "você acha", "vc acha", "voce acha",
    "você joga", "vc joga", "voce joga",
    "você viu", "vc viu", "voce viu",
    "você conhece", "vc conhece", "voce conhece",
    "você gosta", "vc gosta", "voce gosta",
    "você já", "vc já", "vc ja", "voce ja",
    "você sabe", "vc sabe", "voce sabe",
    "o que você", "o que vc", "o que voce",
    "o que tu", "e tu", "e você", "e vc",
    "sua opinião", "sua opiniao",
    "me indica", "me recomenda",
    "alguém aqui", "alguem aqui",
    "galera", "geral",
]

SPONTANEOUS_MESSAGES = [
    "alguem aqui joga btd6",
    "mano que corrida foi essa hoje",
    "rick and morty novo ta bom demais",
    "alguem mais ta assistindo f1",
    "carai que bug foi esse no valorant hj",
    "galera porsche 911 gt3 rs e a melhor coisa que existe",
    "to ouvindo joao gomes no repeat",
    "alguem tem dica de serie boa",
    "mano o verstappen e outro nivel",
    "que dia longo esse hoje viu",
    "alguem mais ta entediado aqui",
]


def _is_mentioned(content: str, bot_user_id: int | None) -> bool:
    """
    Verifica se o bot foi mencionado pelo @mention do Discord.
    O Discord converte @ em <@USER_ID> ou <@!USER_ID> no texto.
    """
    if bot_user_id is None:
        return False
    # Dois formatos possíveis de menção no Discord
    return (
        f"<@{bot_user_id}>" in content or
        f"<@!{bot_user_id}>" in content
    )


def _is_directed_at_bot(content: str, recent_msgs: list) -> bool:
    content_lower = content.lower()
    if any(p in content_lower for p in DIRECTED_AT_BOT_PATTERNS):
        return True
    if recent_msgs:
        bot_recently_spoke = any(
            m.author_name == settings.PERSONA_NAME
            for m in recent_msgs[-3:]
        )
        if bot_recently_spoke and content.strip().endswith("?"):
            return True
    return False


def should_respond(
    message_content: str,
    message_author_id: int,
    channel_id: int,
    bot_last_message_id: int | None,
    replied_to_id: int | None,
    bot_user_id: int | None = None,
) -> tuple[bool, str]:

    content_lower = message_content.lower()
    recent = get_recent_messages(channel_id, n=8)

    # 1. Mencionado via @mention do Discord
    if _is_mentioned(message_content, bot_user_id):
        return True, "mencao direta (@)"

    # 2. Nome mencionado no texto
    if settings.ALWAYS_RESPOND_TO_NAME:
        if settings.PERSONA_NAME.lower() in content_lower:
            return True, "nome mencionado"

    # 3. Resposta direta
    if replied_to_id and replied_to_id == bot_last_message_id:
        return True, "resposta direta"

    # 4. Conversa direcionada sem citar o nome
    if _is_directed_at_bot(message_content, recent):
        last = _last_response_time.get(channel_id, 0)
        if time.time() - last >= 30:
            return True, "conversa direcionada"

    # 5. Cooldown
    last = _last_response_time.get(channel_id, 0)
    if time.time() - last < CHANNEL_COOLDOWN:
        return False, f"cooldown ({CHANNEL_COOLDOWN}s)"

    # 6. Tópico de interesse
    context = " ".join(m.content.lower() for m in recent) + " " + content_lower
    if any(kw in context for kw in INTEREST_KEYWORDS):
        chance = min(settings.BASE_RESPONSE_CHANCE * 2, 80)
        if random.randint(1, 100) <= chance:
            return True, f"topico de interesse (chance {chance}%)"

    # 7. Espontânea
    if random.randint(1, 100) <= settings.BASE_RESPONSE_CHANCE:
        return True, f"espontanea ({settings.BASE_RESPONSE_CHANCE}%)"

    return False, "silencio"


def should_send_spontaneous(channel_id: int) -> tuple[bool, str]:
    last = _last_spontaneous.get(channel_id, 0)
    if time.time() - last < SPONTANEOUS_COOLDOWN:
        return False, "cooldown espontaneo"
    if random.randint(1, 100) <= 2:
        return True, "mensagem espontanea"
    return False, "nao rolou"


def get_spontaneous_message() -> str:
    return random.choice(SPONTANEOUS_MESSAGES)


def register_response(channel_id: int):
    _last_response_time[channel_id] = time.time()


def register_spontaneous(channel_id: int):
    _last_spontaneous[channel_id] = time.time()
    _last_response_time[channel_id] = time.time()
