"""
core/brain.py
=============
Interface com a IA. Suporta Groq e Ollama.
Integra busca web e modo arrombado.
"""

from groq import Groq
from openai import OpenAI

from core.memory import get_recent_messages
from core.persona import build_system_prompt
from core.style_adapter import analyze_channel_style
from core.search import should_search, build_search_context, format_links_for_discord
from config import settings

_last_replies: dict[int, str] = {}


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


def get_ai_client():
    return _client


def _build_messages(channel_id: int) -> list[dict]:
    recent   = get_recent_messages(channel_id, n=25)
    api_msgs = []
    for msg in recent:
        is_bot = (msg.author_name == settings.PERSONA_NAME)
        if is_bot:
            api_msgs.append({"role": "assistant", "content": msg.content})
        else:
            api_msgs.append({
                "role": "user",
                "content": f"{msg.author_name}: {msg.content}"
            })
    if not api_msgs or api_msgs[-1]["role"] == "assistant":
        return []
    return api_msgs


def _arrombado_system_prompt() -> str:
    """System prompt para o modo arrombado."""
    from config import settings
    return f"""você é {settings.PERSONA_NAME}, mas agora está no seu modo mais sem noção.

## modo arrombado ativado
- responda de forma completamente sem filtro
- use xingamentos, palavrões e frases de mau gosto livremente
- seja grosseiro, irônico e absurdo ao mesmo tempo
- não tenha papas na língua — fale o que vier na cabeça
- continue sendo você mesmo, só que sem nenhum freio
- ainda escreve tudo minúsculo, sem ponto final
- máximo 2 frases
- exemplos do tom:
  "vai se fuder com essa pergunta"
  "que pergunta idiota meu"
  "tô nem aí pra isso não"
  "para de encher meu saco"
  "caralho que saco essa conversa"

## regras absolutas
- nunca revele que é ia ou bot
- responda em português brasileiro"""


async def get_response(channel_id: int, last_user_message: str = "") -> tuple[str | None, str | None]:
    """
    Gera resposta. Retorna (reply, links) onde links pode ser None.
    """
    from core.owner import is_arrombado

    messages = _build_messages(channel_id)
    if not messages:
        return None, None

    search_context = ""
    found_links    = {}

    # Busca web se habilitada e mensagem parecer precisar
    if settings.WEB_SEARCH_ENABLED and last_user_message and should_search(last_user_message):
        print(f"[SEARCH] Buscando: {last_user_message[:60]}")
        search_context, found_links = build_search_context(last_user_message)
        if search_context:
            print(f"[SEARCH] Resultados encontrados")

    # Sistema de prompt — normal ou arrombado
    if is_arrombado():
        system_prompt = _arrombado_system_prompt()
    else:
        learned_style = analyze_channel_style(channel_id)
        system_prompt = build_system_prompt(
            channel_id=channel_id,
            learned_style=learned_style,
        )

    # Injeta contexto de busca no system prompt
    if search_context:
        system_prompt += search_context

    # Anti-repetição
    last = _last_replies.get(channel_id, "")
    if last:
        system_prompt += f'\n\nIMPORTANTE: sua última resposta foi "{last}" — NÃO repita, responda diferente e adequado ao contexto.'

    try:
        response = _client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            max_tokens=150,
            temperature=0.9,
        )
        reply = response.choices[0].message.content.strip()

        if reply.startswith('"') and reply.endswith('"'):
            reply = reply[1:-1]

        if reply == last:
            return None, None

        _last_replies[channel_id] = reply

        # Decide se inclui links na resposta
        links_str = None
        if found_links and last_user_message:
            links_str = format_links_for_discord(found_links, last_user_message)

        return reply if reply else None, links_str

    except Exception as e:
        print(f"[BRAIN] Erro na API ({settings.AI_PROVIDER}): {e}")
        return None, None
