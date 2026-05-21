"""
core/link_reader.py
===================
Lê e entende links compartilhados no chat.

DOMÍNIOS SUPORTADOS:
  Streaming: youtube, twitch, kick, spotify
  Redes sociais: twitter/x, instagram, reddit
  Notícias: g1, uol, folha, estadao, cnn brasil
  Tech: github, stackoverflow
  Outros: qualquer site com meta tags

COMO FUNCIONA:
  1. Detecta URLs na mensagem
  2. Verifica se o domínio é seguro/conhecido
  3. Faz a requisição HTTP e extrai título + descrição
  4. Retorna um resumo para a IA usar na resposta
"""

import re
import requests
from urllib.parse import urlparse

# Domínios permitidos — só abre links desses sites
SAFE_DOMAINS = {
    # Streaming / música
    "youtube.com", "youtu.be", "twitch.tv", "kick.com",
    "open.spotify.com", "soundcloud.com",
    # Redes sociais
    "twitter.com", "x.com", "instagram.com", "reddit.com",
    "tiktok.com", "threads.net",
    # Notícias BR
    "g1.globo.com", "globo.com", "uol.com.br", "folha.uol.com.br",
    "estadao.com.br", "cnnbrasil.com.br", "r7.com", "terra.com.br",
    "ig.com.br", "band.com.br", "metropoles.com", "gazetaesportiva.com",
    # Notícias internacionais
    "bbc.com", "cnn.com", "reuters.com", "theguardian.com",
    # Tech
    "github.com", "stackoverflow.com", "medium.com",
    # Esportes
    "globoesporte.globo.com", "espn.com.br", "ge.globo.com",
    "motorsport.com", "autosport.com", "f1.com",
}

URL_REGEX = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+',
    re.IGNORECASE
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def extract_urls(text: str) -> list[str]:
    """Extrai todas as URLs de um texto."""
    return URL_REGEX.findall(text)


def is_safe_domain(url: str) -> bool:
    """Verifica se a URL é de um domínio seguro/conhecido."""
    try:
        hostname = urlparse(url).hostname or ""
        # Remove www. e subdomínios
        for domain in SAFE_DOMAINS:
            if hostname == domain or hostname.endswith(f".{domain}"):
                return True
    except Exception:
        pass
    return False


def _get_meta(html: str, property_name: str) -> str:
    """Extrai meta tag por property ou name."""
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(property_name)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(property_name)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(property_name)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']{re.escape(property_name)}["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return ""


def _get_title(html: str) -> str:
    """Extrai o título da página."""
    # Tenta og:title primeiro
    title = _get_meta(html, "og:title")
    if title:
        return title
    # Fallback: tag <title>
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _get_description(html: str) -> str:
    """Extrai a descrição da página."""
    desc = _get_meta(html, "og:description")
    if not desc:
        desc = _get_meta(html, "description")
    return desc[:300] if desc else ""


def _clean_html_entities(text: str) -> str:
    """Remove entidades HTML básicas."""
    return (text
            .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))


def _get_domain_type(hostname: str) -> str:
    """Identifica o tipo de site."""
    if any(d in hostname for d in ["youtube", "youtu.be"]):
        return "youtube"
    if "twitch" in hostname:
        return "twitch"
    if "kick" in hostname:
        return "kick"
    if "spotify" in hostname:
        return "spotify"
    if any(d in hostname for d in ["twitter", "x.com"]):
        return "twitter"
    if "instagram" in hostname:
        return "instagram"
    if "reddit" in hostname:
        return "reddit"
    if "github" in hostname:
        return "github"
    return "site"


def fetch_link_info(url: str) -> dict | None:
    """
    Busca informações de uma URL segura.
    Retorna dict com tipo, título, descrição ou None se falhar.
    """
    if not is_safe_domain(url):
        return None

    try:
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        r.raise_for_status()
        html = r.text

        title       = _clean_html_entities(_get_title(html))
        description = _clean_html_entities(_get_description(html))
        hostname    = urlparse(url).hostname or ""
        domain_type = _get_domain_type(hostname)

        if not title:
            return None

        return {
            "url":         url,
            "type":        domain_type,
            "title":       title,
            "description": description,
            "domain":      hostname,
        }

    except Exception as e:
        print(f"[LINK] Erro ao ler {url[:50]}: {e}")
        return None


def build_link_context(message_content: str) -> str:
    """
    Detecta links na mensagem, lê os seguros e monta contexto para a IA.
    """
    urls = extract_urls(message_content)
    if not urls:
        return ""

    contexts = []
    for url in urls[:2]:  # máx 2 links por mensagem
        if not is_safe_domain(url):
            continue

        info = fetch_link_info(url)
        if not info:
            continue

        tipo  = info["type"]
        title = info["title"]
        desc  = info["description"]

        if tipo == "youtube":
            ctx = f"Link do YouTube: '{title}'"
        elif tipo == "kick":
            ctx = f"Live no Kick: '{title}'"
        elif tipo == "twitch":
            ctx = f"Canal na Twitch: '{title}'"
        elif tipo == "spotify":
            ctx = f"Link do Spotify: '{title}'"
        elif tipo == "twitter":
            ctx = f"Post no Twitter/X: '{title}'"
        else:
            ctx = f"Link ({info['domain']}): '{title}'"

        if desc:
            ctx += f" — {desc[:150]}"

        contexts.append(ctx)
        print(f"[LINK] Lido: {ctx[:80]}")

    if not contexts:
        return ""

    return f"""
## links compartilhados na conversa (você conseguiu abrir e ler)
{chr(10).join(contexts)}
use essas informações para comentar sobre o link de forma natural.
"""
