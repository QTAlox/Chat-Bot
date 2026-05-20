"""
core/search.py
==============
Busca web gratuita usando DuckDuckGo.
Não precisa de API key — 100% grátis.

QUANDO BUSCA:
  Detecta se a mensagem envolve recomendação de música, filme, série,
  meme, notícia, etc. e busca informações reais antes de responder.
  Também extrai links de YouTube e Spotify quando relevante.
"""

import re
from duckduckgo_search import DDGS

# Palavras que indicam que vale a pena buscar antes de responder
SEARCH_TRIGGERS = [
    "recomenda", "indica", "sugere", "qual musica", "qual música",
    "qual filme", "qual série", "qual serie", "qual jogo",
    "me fala sobre", "o que é", "quem é", "quando foi",
    "letra de", "música do", "musica do", "música da", "musica da",
    "album", "álbum", "lançou", "lancou", "novo clipe",
    "link", "youtube", "spotify", "assiste", "ouve",
    "meme", "trend", "viral", "twitter",
]


def should_search(message_content: str) -> bool:
    """Verifica se vale fazer uma busca para essa mensagem."""
    content_lower = message_content.lower()
    return any(trigger in content_lower for trigger in SEARCH_TRIGGERS)


def _extract_links(results: list[dict]) -> dict:
    """Extrai links úteis dos resultados de busca."""
    links = {"youtube": None, "spotify": None, "twitter": None, "general": None}

    for r in results:
        url = r.get("href", "")
        if not links["youtube"] and "youtube.com" in url:
            links["youtube"] = url
        elif not links["spotify"] and "spotify.com" in url:
            links["spotify"] = url
        elif not links["twitter"] and ("twitter.com" in url or "x.com" in url):
            links["twitter"] = url
        elif not links["general"] and url:
            links["general"] = url

    return links


def web_search(query: str, max_results: int = 4) -> dict:
    """
    Faz uma busca no DuckDuckGo e retorna resultados + links relevantes.

    Retorna:
      {
        "summary": "resumo dos resultados para injetar no prompt",
        "links": {"youtube": url, "spotify": url, ...}
      }
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="br-pt"))

        if not results:
            return {"summary": "", "links": {}}

        links = _extract_links(results)

        # Monta um resumo curto dos resultados
        snippets = []
        for r in results[:3]:
            title = r.get("title", "")
            body  = r.get("body", "")[:150]
            if title or body:
                snippets.append(f"- {title}: {body}")

        summary = "\n".join(snippets)
        return {"summary": summary, "links": links}

    except Exception as e:
        print(f"[SEARCH] Erro na busca: {e}")
        return {"summary": "", "links": {}}


def build_search_context(query: str) -> tuple[str, dict]:
    """
    Busca e retorna (texto_para_prompt, links_encontrados).
    """
    result = web_search(query)
    summary = result["summary"]
    links   = result["links"]

    if not summary:
        return "", {}

    context = f"""
## informações reais encontradas na web (use isso para responder com precisão)
{summary}
use essas informações para dar uma resposta verdadeira — não invente nomes, músicas ou fatos.
"""
    return context, links


def format_links_for_discord(links: dict, message_content: str) -> str | None:
    """
    Decide quais links incluir na resposta baseado no contexto.
    Retorna uma string com os links ou None se não houver.
    """
    content_lower = message_content.lower()
    parts = []

    # Inclui YouTube se falam de vídeo/clipe/música
    if links.get("youtube") and any(
        w in content_lower for w in ["musica", "música", "clipe", "video", "vídeo", "youtube", "ouv"]
    ):
        parts.append(links["youtube"])

    # Inclui Spotify se falam de música/ouvir
    if links.get("spotify") and any(
        w in content_lower for w in ["musica", "música", "ouv", "spotify", "playlist"]
    ):
        parts.append(links["spotify"])

    # Inclui Twitter/X se falam de meme/trend
    if links.get("twitter") and any(
        w in content_lower for w in ["meme", "trend", "viral", "twitter"]
    ):
        parts.append(links["twitter"])

    return "\n".join(parts) if parts else None
