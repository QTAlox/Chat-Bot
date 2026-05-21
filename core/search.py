"""
core/search.py — Busca web (DuckDuckGo) + Spotify API oficial.
Prioridade: Spotify para músicas, YouTube como fallback.
"""

from ddgs import DDGS
from core.spotify import get_artist_top_tracks, is_configured as spotify_configured

SEARCH_TRIGGERS = [
    "recomenda", "indica", "sugere", "qual musica", "qual música",
    "qual filme", "qual série", "qual serie", "qual jogo",
    "me fala sobre", "o que é", "quem é", "quando foi",
    "letra de", "música do", "musica do", "música da", "musica da",
    "album", "álbum", "lançou", "lancou", "novo clipe",
    "link", "youtube", "spotify", "assiste", "ouve", "predileta",
    "favorita", "melhor", "meme", "trend", "viral", "twitter",
]

MUSIC_WORDS = [
    "musica", "música", "ouvir", "ouv", "spotify", "indica",
    "recomend", "predileta", "favorita", "melhor", "clipe",
    "artista", "cantor", "banda", "som", "escutar", "playlist",
]

KNOWN_ARTISTS = [
    "joao gomes", "joão gomes",
    "mc ryan", "mc ryan sp",
    "luan santana", "gustavo mioto",
]


def should_search(message_content: str) -> bool:
    return any(t in message_content.lower() for t in SEARCH_TRIGGERS)


def _detect_artist(message: str) -> str | None:
    msg = message.lower()
    for artist in KNOWN_ARTISTS:
        if artist in msg:
            return artist
    return None


def _find_youtube_video(artist_name: str) -> str | None:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.videos(
                f"{artist_name} música oficial",
                max_results=8, region="br-pt",
            ))
        artist_clean = (artist_name.lower()
                        .replace(" ","").replace("ã","a")
                        .replace("ô","o").replace("é","e"))
        for r in results:
            url      = r.get("content","") or r.get("embed_url","")
            uploader = r.get("uploader","").lower().replace(" ","")
            if artist_clean in uploader:
                if "youtube.com/embed/" in url:
                    return f"https://www.youtube.com/watch?v={url.split('/embed/')[1].split('?')[0]}"
                if "youtube.com/watch" in url:
                    return url
        # Fallback — primeiro resultado
        for r in results:
            url = r.get("content","") or r.get("embed_url","")
            if "youtube.com/embed/" in url:
                return f"https://www.youtube.com/watch?v={url.split('/embed/')[1].split('?')[0]}"
            if "youtube.com/watch" in url:
                return url
    except Exception as e:
        print(f"[SEARCH] YouTube erro: {e}")
    return None


def web_search(query: str) -> dict:
    links       = {"youtube": None, "spotify": None, "twitter": None}
    summary     = ""
    real_tracks = []

    artist = _detect_artist(query)

    # ── Spotify (fonte principal para músicas) ─────────────────────────
    if artist and spotify_configured():
        print(f"[SPOTIFY] Buscando músicas de: {artist}")
        tracks = get_artist_top_tracks(artist, limit=999)
        if tracks:
            import random
            real_tracks = tracks
            # Randomiza o link — pega das top 25 para variar
            top25        = tracks[:25] if len(tracks) >= 25 else tracks
            chosen       = random.choice(top25)
            links["spotify"] = chosen["url"]
            track_list = "\n".join(f"  - {t['name']}" for t in tracks[:20])
            summary    = f"Músicas reais de {tracks[0]['artist']} no Spotify:\n{track_list}"

    # ── YouTube — só busca se não achou no Spotify ou como fallback ────
    if artist:
        links["youtube"] = _find_youtube_video(artist)

    # ── Busca geral para contexto extra (não-músicas) ──────────────────
    if not summary:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5, region="br-pt"))
            snippets = []
            for r in results:
                url   = r.get("href","")
                title = r.get("title","")
                body  = r.get("body","")[:180]
                if "youtube.com/watch" in url and not links["youtube"]:
                    links["youtube"] = url
                if "open.spotify.com" in url and not links["spotify"]:
                    links["spotify"] = url
                if ("twitter.com" in url or "x.com" in url) and not links["twitter"]:
                    links["twitter"] = url
                if title:
                    snippets.append(f"- {title}: {body}")
            summary = "\n".join(snippets[:3])
        except Exception as e:
            print(f"[SEARCH] Erro geral: {e}")

    print(f"[SEARCH] youtube={bool(links['youtube'])} spotify={bool(links['spotify'])}")
    return {"summary": summary, "links": links, "real_tracks": real_tracks}


def build_search_context(query: str) -> tuple[str, dict]:
    result      = web_search(query)
    summary     = result["summary"]
    links       = result["links"]
    real_tracks = result.get("real_tracks", [])

    if not summary and not real_tracks:
        return "", {}

    if real_tracks:
        names = [t["name"] for t in real_tracks]
        context = f"""
## músicas REAIS e VERIFICADAS no Spotify
{summary}

REGRA CRÍTICA ABSOLUTA: cite SOMENTE músicas desta lista: {names}
PROIBIDO inventar qualquer outro nome. Escolha um nome EXATO da lista.
Diga que mandou o link do Spotify junto.
"""
    else:
        context = f"""
## resultados reais da web
{summary}
Cite apenas informações que aparecem explicitamente acima.
"""
    return context, links


def format_links_for_discord(links: dict, message_content: str) -> str | None:
    """
    Prioridade para músicas:
      1. Spotify (se disponível)
      2. YouTube (só se Spotify não encontrou)
    Para vídeos/clipes: YouTube
    Para memes: Twitter
    """
    msg   = message_content.lower()
    parts = []

    is_music = any(w in msg for w in MUSIC_WORDS)
    is_meme  = any(w in msg for w in ["meme", "trend", "viral", "twitter"])
    is_video = any(w in msg for w in ["video", "vídeo", "clipe", "assiste"])

    if is_music:
        if links.get("spotify"):
            # Tem Spotify — manda só Spotify
            parts.append(links["spotify"])
        elif links.get("youtube"):
            # Não tem Spotify — fallback para YouTube
            parts.append(links["youtube"])

    elif is_video and links.get("youtube"):
        # Pediu especificamente vídeo/clipe — manda YouTube
        parts.append(links["youtube"])

    if is_meme and links.get("twitter"):
        parts.append(links["twitter"])

    # Fallback geral
    if not parts:
        if links.get("spotify"):
            parts.append(links["spotify"])
        elif links.get("youtube"):
            parts.append(links["youtube"])

    return "\n".join(parts) if parts else None
