"""
core/brain.py
=============
Interface com a IA — suporta Groq (nuvem grátis) e Ollama (local grátis).
Troque entre eles mudando AI_PROVIDER no .env — sem mexer no código.
"""

from groq import Groq
from openai import OpenAI

from core.memory import get_recent_messages
from core.persona import build_system_prompt
from core.style_adapter import analyze_channel_style
from config import settings


def _make_client():
    if settings.AI_PROVIDER == "groq":
        print(f"[BRAIN] Usando Groq ({settings.GROQ_MODEL})")
        return Groq(api_key=settings.GROQ_API_KEY), settings.GROQ_MODEL
    elif settings.AI_PROVIDER == "ollama":
        print(f"[BRAIN] Usando Ollama local ({settings.OLLAMA_MODEL})")
        client = OpenAI(
            base_url=f"{settings.OLLAMA_BASE_URL}/v1",
            api_key="ollama",
        )
        return client, settings.OLLAMA_MODEL
    else:
        raise ValueError(f"AI_PROVIDER invalido: {settings.AI_PROVIDER}")


_client, _model = _make_client()


def _build_messages(channel_id: int) -> list[dict]:
    """Converte o buffer do canal para o formato da API."""
    recent   = get_recent_messages(channel_id, n=20)
    api_msgs = []
    for msg in recent:
        is_bot  = (msg.author_name == settings.PERSONA_NAME)
        role    = "assistant" if is_bot else "user"
        content = msg.content if is_bot else f"{msg.author_name}: {msg.content}"
        api_msgs.append({"role": role, "content": content})
    return api_msgs


async def get_response(channel_id: int) -> str | None:
    """Gera uma resposta para o canal. Retorna None se algo falhar."""
    messages = _build_messages(channel_id)
    if not messages:
        return None
    if messages[-1]["role"] == "assistant":
        return None

    learned_style = analyze_channel_style(channel_id)
    system_prompt = build_system_prompt(learned_style)

    try:
        response = _client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            max_tokens=120,
            temperature=0.9,  # um pouco mais alto para o sarcasmo fluir
        )
        reply = response.choices[0].message.content.strip()
        return reply if reply else None
    except Exception as e:
        print(f"[BRAIN] Erro na API ({settings.AI_PROVIDER}): {e}")
        return None
