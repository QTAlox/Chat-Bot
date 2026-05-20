"""
core/training.py
================
Aprendizado automático de estilo a partir do histórico do canal.

COMO FUNCIONA:
  1. Ao iniciar, o bot lê as últimas N mensagens do canal
  2. Analisa padrões: gírias, tamanho, pontuação, vocabulário único
  3. Manda esse histórico pra IA e pede que ela descreva o estilo
  4. Salva o resultado em cache (data/learned_style.json)
  5. A cada X horas, atualiza o aprendizado automaticamente

  Resultado: o bot aprende como o grupo escreve sem você fazer nada.
"""

import json
import time
import asyncio
from pathlib import Path

STYLE_CACHE  = Path("data/learned_style.json")
CACHE_TTL    = 3 * 60 * 60  # atualiza a cada 3 horas

# Quantas mensagens ler do histórico para aprender
HISTORY_SAMPLE = 150


def _load_cache() -> dict:
    try:
        data = json.loads(STYLE_CACHE.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {}


def _save_cache(channel_id: int, style_text: str, samples: list[str]):
    STYLE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = _load_cache()
    cache[str(channel_id)] = {
        "style": style_text,
        "samples": samples[:30],
        "updated_at": time.time(),
    }
    STYLE_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_cached_style(channel_id: int) -> str | None:
    """Retorna o estilo em cache se ainda estiver válido."""
    cache = _load_cache()
    entry = cache.get(str(channel_id))
    if not entry:
        return None
    age = time.time() - entry.get("updated_at", 0)
    if age > CACHE_TTL:
        return None  # cache expirado
    return entry.get("style", "")


def get_cached_samples(channel_id: int) -> list[str]:
    """Retorna amostras de mensagens reais do cache."""
    cache = _load_cache()
    entry = cache.get(str(channel_id))
    if not entry:
        return []
    return entry.get("samples", [])


async def learn_from_channel(channel, client_ai) -> str:
    """
    Lê o histórico do canal do Discord, analisa com a IA
    e salva o estilo aprendido.

    channel   : objeto discord.TextChannel
    client_ai : cliente Groq/OpenAI já inicializado
    """
    from config import settings

    print(f"[TRAINING] Aprendendo estilo do #{channel.name}...")

    # Coleta mensagens reais do canal (exclui bots e mensagens vazias)
    messages = []
    try:
        async for msg in channel.history(limit=HISTORY_SAMPLE):
            # Ignora a própria conta do bot e mensagens vazias
            if msg.author.bot:
                continue
            if not msg.content.strip():
                continue
            # Ignora comandos e links
            if msg.content.startswith(("/", "!", "http")):
                continue
            messages.append({
                "author": msg.author.display_name,
                "content": msg.content.strip(),
            })
    except Exception as e:
        print(f"[TRAINING] Erro ao ler histórico: {e}")
        return ""

    if len(messages) < 10:
        print(f"[TRAINING] Poucas mensagens ({len(messages)}), pulando...")
        return ""

    # Prepara amostra para análise
    samples = [m["content"] for m in messages]
    sample_text = "\n".join(
        f'{m["author"]}: {m["content"]}' for m in messages[:80]
    )

    # Pede para a IA descrever o estilo do grupo
    prompt = f"""analise as mensagens abaixo de um grupo do discord e descreva em 3-5 linhas curtas:
- como eles escrevem (maiúsculo/minúsculo, pontuação, tamanho)
- gírias e expressões únicas que usam
- o tom geral (humor, sarcasmo, direto, etc)
- exemplos de expressões características

mensagens do grupo:
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
    """
    Monta o bloco de treino para injetar no system prompt.
    Combina a descrição de estilo com exemplos reais de mensagens.
    """
    style   = get_cached_style(channel_id)
    samples = get_cached_samples(channel_id)

    if not style and not samples:
        return ""

    parts = []

    if style:
        parts.append(f"""## como o grupo escreve (aprendido automaticamente)
{style}""")

    if samples:
        # Pega 15 exemplos aleatórios das mensagens reais
        import random
        chosen = random.sample(samples, min(15, len(samples)))
        examples = "\n".join(f'  "{s}"' for s in chosen)
        parts.append(f"""## exemplos reais de mensagens do grupo
copie esse estilo exatamente:
{examples}""")

    return "\n\n" + "\n\n".join(parts)
