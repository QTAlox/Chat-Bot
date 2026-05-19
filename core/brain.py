"""
core/brain.py
=============
Interface com a IA. Suporta Groq e Ollama.
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
    """
    Monta o histórico no formato correto para a API.

    IMPORTANTE: o formato "nome: mensagem" ajuda a IA entender
    quem disse o quê. Mensagens do próprio bot viram "assistant".
    """
    recent   = get_recent_messages(channel_id, n=25)
    api_msgs = []

    for msg in recent:
        is_bot = (msg.author_name == settings.PERSONA_NAME)

        if is_bot:
            # Mensagem do próprio bot — role "assistant", sem prefixo de nome
            api_msgs.append({
                "role": "assistant",
                "content": msg.content
            })
        else:
            # Mensagem de outro usuário — role "user", com nome na frente
            # Isso deixa claro para a IA quem está falando
            api_msgs.append({
                "role": "user",
                "content": f"{msg.author_name}: {msg.content}"
            })

    # A API exige que a última mensagem seja de "user"
    if not api_msgs or api_msgs[-1]["role"] == "assistant":
        return []

    return api_msgs


async def get_response(channel_id: int) -> str | None:
    messages = _build_messages(channel_id)
    if not messages:
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
            temperature=0.85,
        )
        reply = response.choices[0].message.content.strip()

        # Remove aspas se o modelo colocar a resposta entre aspas
        if reply.startswith('"') and reply.endswith('"'):
            reply = reply[1:-1]

        return reply if reply else None

    except Exception as e:
        print(f"[BRAIN] Erro na API ({settings.AI_PROVIDER}): {e}")
        return None
