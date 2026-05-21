"""
core/training.py
================
Aprendizado automático de estilo lendo o histórico do canal.
Filtra mensagens do bot, direcionadas a ele e comandos.
"""

import json
import time
import re
from pathlib import Path

STYLE_CACHE  = Path("data/learned_style.json")
CACHE_TTL    = 3 * 60 * 60  # 3 horas
HISTORY_SAMPLE = 200


def _load_cache() -> dict:
    try:
        return json.loads(STYLE_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(channel_id: int, style_text: str, samples: list[str]):
    STYLE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = _load_cache()
    cache[str(channel_id)] = {
        "style":      style_text,
        "samples":    samples[:40],
        "updated_at": time.time(),
    }
    STYLE_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_cached_style(channel_id: int) -> str | None:
    cache = _load_cache()
    entry = cache.get(str(channel_id))
    if not entry:
        return None
    if time.time() - entry.get("updated_at", 0) > CACHE_TTL:
        return None
    return entry.get("style", "")


def get_cached_samples(channel_id: int) -> list[str]:
    cache = _load_cache()
    entry = cache.get(str(channel_id))
    return entry.get("samples", []) if entry else []


def _should_skip_message(msg, bot_user_id: int, persona_name: str) -> bool:
    """
    Retorna True se a mensagem deve ser ignorada no aprendizado.
    Ignora:
      - Mensagens do próprio bot
      - Mensagens de outros bots
      - Mensagens que mencionam o bot (@ID)
      - Mensagens que chamam pelo nome do bot
      - Comandos (!felipe, !, /)
      - Mensagens muito curtas (1-2 chars)
      - Links puros
    """
    content = msg.content.strip()

    # Bots
    if msg.author.bot:
        return True

    # Mensagens do próprio bot pelo nome
    if msg.author.display_name.lower() == persona_name.lower():
        return True

    # Muito curta
    if len(content) <= 2:
        return True

    # Comandos
    if content.startswith(("!", "/", ".")):
        return True

    # Menção ao bot por ID
    if f"<@{bot_user_id}>" in content or f"<@!{bot_user_id}>" in content:
        return True

    # Chamando pelo nome do bot (ex: "felipe", "felipe vc")
    name_lower = persona_name.lower()
    first_word = content.lower().split()[0] if content.split() else ""
    if first_word == name_lower:
        return True

    # Link puro (só URL)
    if re.match(r'^https?://\S+$', content):
        return True

    # Respostas ao status do bot (markdown com **)
    if content.startswith("**"):
        return True

    return False


async def learn_from_channel(channel, client_ai, bot_user_id: int = 0) -> str:
    """
    Lê o histórico do canal e aprende o estilo do grupo.
    Filtra mensagens do bot e direcionadas a ele.
    """
    from config import settings

    print(f"[TRAINING] Aprendendo estilo do #{channel.name}...")

    messages = []
    try:
        async for msg in channel.history(limit=HISTORY_SAMPLE):
            if _should_skip_message(msg, bot_user_id, settings.PERSONA_NAME):
                continue
            if not msg.content.strip():
                continue
            messages.append({
                "author":  msg.author.display_name,
                "content": msg.content.strip(),
            })
    except Exception as e:
        print(f"[TRAINING] Erro ao ler histórico: {e}")
        return ""

    if len(messages) < 8:
        print(f"[TRAINING] Poucas mensagens limpas ({len(messages)}), pulando...")
        return ""

    samples     = [m["content"] for m in messages]
    sample_text = "\n".join(f'{m["author"]}: {m["content"]}' for m in messages[:80])

    prompt = f"""analise as mensagens abaixo de um grupo do discord e descreva em 3-5 linhas curtas:
- como eles escrevem (maiúsculo/minúsculo, pontuação, tamanho das mensagens)
- gírias e expressões únicas que usam
- o tom geral (humor, sarcasmo, direto, etc)

mensagens (apenas de usuários reais conversando entre si):
{sample_text}

responda em português, de forma objetiva e curta. não use listas numeradas."""

    try:
        response = client_ai.chat.completions.create(
            model=settings.GROQ_MODEL if settings.AI_PROVIDER == "groq" else settings.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        style_description = response.choices[0].message.content.strip()
        _save_cache(channel.id, style_description, samples)
        print(f"[TRAINING] Estilo aprendido: {style_description[:80]}...")
        return style_description
    except Exception as e:
        print(f"[TRAINING] Erro na análise: {e}")
        return ""


def build_training_prompt(channel_id: int) -> str:
    style   = get_cached_style(channel_id)
    samples = get_cached_samples(channel_id)

    if not style and not samples:
        return ""

    parts = []

    if style:
        parts.append(f"""## como o grupo escreve (aprendido automaticamente)
{style}""")

    if samples:
        import random
        chosen   = random.sample(samples, min(15, len(samples)))
        examples = "\n".join(f'  "{s}"' for s in chosen)
        parts.append(f"""## exemplos reais de mensagens do grupo
copie esse estilo:
{examples}""")

    return "\n\n" + "\n\n".join(parts)
