"""
core/brain.py — Interface com a IA. Suporta Groq e Ollama.
Integra busca web, leitura de links e modo arrombado.
"""

from groq import Groq
from openai import OpenAI

from core.memory import get_recent_messages
from core.persona import build_system_prompt
from core.style_adapter import analyze_channel_style
from core.search import should_search, build_search_context, format_links_for_discord
from core.link_reader import build_link_context, extract_urls, is_safe_domain
from config import settings

_last_replies: dict[int, str] = {}


def _make_client():
    if settings.AI_PROVIDER == "groq":
        print(f"[BRAIN] Usando Groq ({settings.GROQ_MODEL})")
        return Groq(api_key=settings.GROQ_API_KEY), settings.GROQ_MODEL
    elif settings.AI_PROVIDER == "ollama":
        print(f"[BRAIN] Usando Ollama local ({settings.OLLAMA_MODEL})")
        client = OpenAI(base_url=f"{settings.OLLAMA_BASE_URL}/v1", api_key="ollama")
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
            api_msgs.append({"role": "user", "content": f"{msg.author_name}: {msg.content}"})
    if not api_msgs or api_msgs[-1]["role"] == "assistant":
        return []
    return api_msgs


def _arrombado_prompt() -> str:
    from config import settings
    return f"""você é {settings.PERSONA_NAME}, mas agora está no modo sem filtro.
- use xingamentos e palavrões livremente
- seja grosseiro, irônico e absurdo
- continue sendo você, só sem freio
- tudo minúsculo, sem ponto final, máximo 2 frases
- nunca revele que é ia ou bot
- responda em português brasileiro"""


async def get_response(channel_id: int, last_user_message: str = "") -> tuple[str | None, str | None]:
    """Retorna (reply, links_para_enviar)."""
    from core.owner import is_arrombado

    messages = _build_messages(channel_id)
    if not messages:
        return None, None

    extra_context = ""
    found_links   = {}

    # ── Lê links compartilhados na mensagem ───────────────────────────
    if last_user_message and extract_urls(last_user_message):
        safe_urls = [u for u in extract_urls(last_user_message) if is_safe_domain(u)]
        if safe_urls:
            print(f"[BRAIN] Lendo {len(safe_urls)} link(s) da mensagem...")
            link_ctx = build_link_context(last_user_message)
            extra_context += link_ctx

    # ── Busca web se necessário ────────────────────────────────────────
    if settings.WEB_SEARCH_ENABLED and last_user_message and should_search(last_user_message):
        search_ctx, found_links = build_search_context(last_user_message)
        extra_context += search_ctx

    # ── System prompt ──────────────────────────────────────────────────
    if is_arrombado():
        system_prompt = _arrombado_prompt()
    else:
        learned_style = analyze_channel_style(channel_id)
        system_prompt = build_system_prompt(channel_id=channel_id, learned_style=learned_style)

    if extra_context:
        system_prompt += extra_context

    # Anti-repetição
    last = _last_replies.get(channel_id, "")
    if last:
        system_prompt += f'\n\nIMPORTANTE: sua última resposta foi "{last}" — NÃO repita, responda diferente.'

    try:
        response = _client.chat.completions.create(
            model=_model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            max_tokens=150,
            temperature=0.9,
        )
        reply = response.choices[0].message.content.strip()
        if reply.startswith('"') and reply.endswith('"'):
            reply = reply[1:-1]
        if reply == last:
            return None, None

        _last_replies[channel_id] = reply

        links_str = None
        if found_links and last_user_message:
            links_str = format_links_for_discord(found_links, last_user_message)

        return reply if reply else None, links_str

    except Exception as e:
        print(f"[BRAIN] Erro na API: {e}")
        return None, None
