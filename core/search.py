"""
core/search.py — Busca web com DuckDuckGo + busca em canais oficiais de artistas.
"""

from ddgs import DDGS

SEARCH_TRIGGERS = [
    "recomenda", "indica", "sugere", "qual musica", "qual música",
    "qual filme", "qual série", "qual serie", "qual jogo",
    "me fala sobre", "o que é", "quem é", "quando foi",
    "letra de", "música do", "musica do", "música da", "musica da",
    "album", "álbum", "lançou", "lancou", "novo clipe",
    "link", "youtube", "spotify", "assiste", "ouve", "predileta",
    "favorita", "melhor", "meme", "trend", "viral", "twitter",
]

# Canais oficiais conhecidos — adicione mais aqui quando quiser
# formato: "nome do artista em minúsculo": "@handle_do_canal"
ARTIST_CHANNELS = {
    "joao gomes": "@joaogomesvq",
    "joão gomes": "@joaogomesvq",
    # Adicione outros artistas aqui:
    # "jota.pe": "@Jota.Pe.Oficial",
    # "mestrinho": "@mestrinhooficial",
}


def should_search(message_content: str) -> bool:
    return any(t in message_content.lower() for t in SEARCH_TRIGGERS)


def _detect_artist(message: str) -> str | None:
    """Detecta se a mensagem menciona um artista conhecido."""
    msg = message.lower()
    for artist in ARTIST_CHANNELS:
        if artist in msg:
            return artist
    return None


def _find_artist_channel(artist_name: str) -> str | None:
    """
    Tenta encontrar o canal oficial do artista automaticamente
    se não estiver em ARTIST_CHANNELS.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                f"{artist_name} canal oficial youtube",
                max_results=5,
                region="br-pt",
            ))
        for r in results:
            url  = r.get("href", "")
            # Pega URL de canal YouTube (@handle ou /channel/)
            if "youtube.com/@" in url:
                handle = url.split("youtube.com/")[1].split("/")[0]
                return handle
            if "youtube.com/channel/" in url:
                return url.split("youtube.com/channel/")[1].split("/")[0]
    except Exception as e:
        print(f"[SEARCH] Erro ao buscar canal: {e}")
    return None


def _find_song_from_channel(artist_name: str, channel_handle: str, query: str) -> str | None:
    """
    Busca uma música específica do artista no canal oficial.
    """
    search_query = f"{artist_name} {query} youtube.com/{channel_handle}"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.videos(
                f"{artist_name} música oficial",
                max_results=8,
                region="br-pt",
            ))
        for r in results:
            url      = r.get("content", "") or r.get("embed_url", "")
            uploader = r.get("uploader", "").lower()
            # Prefere vídeos do canal oficial
            if artist_name.lower().replace(" ", "") in uploader.replace(" ", ""):
                if "youtube.com/embed/" in url:
                    vid_id = url.split("/embed/")[1].split("?")[0]
                    return f"https://www.youtube.com/watch?v={vid_id}"
                if "youtube.com/watch" in url:
                    return url

        # Fallback: pega o primeiro resultado de qualquer forma
        for r in results:
            url = r.get("content", "") or r.get("embed_url", "")
            if "youtube.com/embed/" in url:
                vid_id = url.split("/embed/")[1].split("?")[0]
                return f"https://www.youtube.com/watch?v={vid_id}"
            if "youtube.com/watch" in url:
                return url

    except Exception as e:
        print(f"[SEARCH] Erro busca canal: {e}")
    return None


def _find_spotify_link(query: str) -> str | None:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query + " spotify ouvir",
                max_results=8,
                region="br-pt",
            ))
        for r in results:
            url = r.get("href", "")
            if "open.spotify.com/track" in url:
                return url
            if "open.spotify.com/album" in url:
                return url
    except Exception as e:
        print(f"[SEARCH] Spotify erro: {e}")
    return None


def web_search(query: str) -> dict:
    summary = ""
    links   = {"youtube": None, "spotify": None, "twitter": None}

    # Detecta artista na mensagem
    artist = _detect_artist(query)

    if artist:
        # Pega o canal — do dicionário ou busca automaticamente
        channel = ARTIST_CHANNELS.get(artist)
        if not channel:
            print(f"[SEARCH] Buscando canal de {artist} automaticamente...")
            channel = _find_artist_channel(artist)
            if channel:
                print(f"[SEARCH] Canal encontrado: {channel}")
                ARTIST_CHANNELS[artist] = channel  # salva em memória pra próxima vez

        if channel:
            print(f"[SEARCH] Buscando música de {artist} no canal {channel}")
            links["youtube"] = _find_song_from_channel(artist, channel, query)

    # Busca geral para contexto e links extras
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5, region="br-pt"))

        snippets = []
        for r in results:
            url   = r.get("href", "")
            title = r.get("title", "")
            body  = r.get("body", "")[:180]

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

    # Spotify separado se não achou
    if not links["spotify"]:
        links["spotify"] = _find_spotify_link(query)

    print(f"[SEARCH] youtube={bool(links['youtube'])} spotify={bool(links['spotify'])}")
    return {"summary": summary, "links": links}


def build_search_context(query: str) -> tuple[str, dict]:
    result  = web_search(query)
    summary = result["summary"]
    links   = result["links"]

    if not summary:
        return "", {}

    context = f"""
## resultados reais da web
{summary}
IMPORTANTE: cite apenas músicas/artistas/filmes reais encontrados acima. nunca invente nomes.
se tiver link disponível, diga que mandou o link junto.
"""
    return context, links


def format_links_for_discord(links: dict, message_content: str) -> str | None:
    msg   = message_content.lower()
    parts = []

    music_words = ["musica", "música", "ouv", "spotify", "indica",
                   "recomend", "predileta", "favorita", "melhor", "clipe"]
    video_words = ["video", "vídeo", "clipe", "youtube", "assiste"]
    meme_words  = ["meme", "trend", "viral", "twitter"]

    is_music = any(w in msg for w in music_words)
    is_video = any(w in msg for w in video_words)
    is_meme  = any(w in msg for w in meme_words)

    if links.get("spotify") and is_music:
        parts.append(links["spotify"])
    if links.get("youtube") and (is_music or is_video):
        parts.append(links["youtube"])
    if links.get("twitter") and is_meme:
        parts.append(links["twitter"])

    return "\n".join(parts) if parts else None
