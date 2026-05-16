"""
core/decision_engine.py
=======================
Decide SE e QUANDO o Felipe deve responder — coração do comportamento autônomo.

Critérios (em ordem de prioridade):
  1. Mencionou o nome "Felipe"?            -> responde sempre
  2. É resposta direta a uma msg dele?     -> responde sempre
  3. Cooldown do canal ainda ativo?        -> silêncio
  4. Tópico de interesse detectado?        -> chance aumentada
  5. Sorteio com a chance base             -> entrada espontânea
"""

import time
import random
from core.memory import get_recent_messages
from config import settings

_last_response_time: dict[int, float] = {}
CHANNEL_COOLDOWN = 45  # segundos mínimos entre respostas no mesmo canal

# Palavras-chave dos interesses do Felipe — alinhado com o persona.yaml
INTEREST_KEYWORDS = [
    # F1 e automobilismo
    "f1", "formula 1", "formula1", "verstappen", "max", "hamilton", "ferrari",
    "red bull", "redbull", "gp", "grande premio", "corrida", "pit stop",
    # Carros
    "porsche", "911", "gt3", "supra", "mazda", "mercedes", "audi", "bmw",
    "carro", "turbo", "rebaixado",
    # Jogos
    "bloons", "btd", "btd6", "valorant", "minecraft", "jogo", "game",
    "jogar", "ranked", "partida", "cs", "counter",
    # Séries e cultura
    "rick and morty", "rick", "morty", "serie", "série", "netflix",
    "filme", "cinema", "episodio",
    # Música
    "joao gomes", "joão gomes", "forró", "forro", "rock", "musica", "música",
    # Tech
    "programacao", "programação", "codigo", "código", "python", "bug",
    # Internet
    "meme", "twitter", "instagram", "tiktok",
]


def should_respond(
    message_content: str,
    message_author_id: int,
    channel_id: int,
    bot_last_message_id: int | None,
    replied_to_id: int | None,
) -> tuple[bool, str]:
    """Retorna (deve_responder, motivo)."""

    content_lower = message_content.lower()

    # 1. Nome mencionado
    if settings.ALWAYS_RESPOND_TO_NAME:
        if settings.PERSONA_NAME.lower() in content_lower:
            return True, "nome mencionado"

    # 2. Resposta direta ao Felipe
    if replied_to_id and replied_to_id == bot_last_message_id:
        return True, "resposta direta"

    # 3. Cooldown
    last = _last_response_time.get(channel_id, 0)
    if time.time() - last < CHANNEL_COOLDOWN:
        return False, f"cooldown ({CHANNEL_COOLDOWN}s)"

    # 4. Tópico de interesse — olha as últimas msgs do canal
    recent  = get_recent_messages(channel_id, n=8)
    context = " ".join(m.content.lower() for m in recent) + " " + content_lower
    if any(kw in context for kw in INTEREST_KEYWORDS):
        chance = min(settings.BASE_RESPONSE_CHANCE * 2, 80)
        if random.randint(1, 100) <= chance:
            return True, f"topico de interesse (chance {chance}%)"

    # 5. Entrada espontânea
    if random.randint(1, 100) <= settings.BASE_RESPONSE_CHANCE:
        return True, f"espontanea ({settings.BASE_RESPONSE_CHANCE}%)"

    return False, "silencio"


def register_response(channel_id: int):
    """Marca que o Felipe acabou de responder neste canal."""
    _last_response_time[channel_id] = time.time()
