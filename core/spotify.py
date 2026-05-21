"""
core/spotify.py
===============
Spotify API + base local de músicas como fallback.
Se a API falhar, usa a base local que tem músicas reais verificadas.
"""

import json
import time
import random
import base64
import requests
from pathlib import Path
from config import settings

_token_cache  = {"token": None, "expires_at": 0}
_CACHE_FILE   = Path("data/spotify_cache.json")
_ARTISTS_FILE = Path("data/spotify_artists.json")
_CACHE_TTL    = 24 * 60 * 60

# ── Base local de músicas reais verificadas ────────────────────────────
# Adicione mais artistas e músicas aqui conforme necessário
LOCAL_MUSIC_DB = {
    "joao gomes": {
        "artist_display": "João Gomes",
        "tracks": [
            {"name": "Meu Pedaço de Pecado", "url": "https://open.spotify.com/track/3CsPDkMqnfMWiT0R5HCRWT"},
            {"name": "Dengo", "url": "https://open.spotify.com/track/5UqCQaDshqbIk3pkhy4Pjg"},
            {"name": "Lembra", "url": "https://open.spotify.com/track/2JzWne7Sdvg4Dx6xjm0ZmC"},
            {"name": "Sigara", "url": "https://open.spotify.com/track/5VnrVgtzxsHEAHsoJToV9Z"},
            {"name": "Além da Saudade", "url": "https://open.spotify.com/track/1fFOJZTAWUNHsPZ8DFfxzU"},
            {"name": "Eu Sei de Cor", "url": "https://open.spotify.com/track/6oRBHCQiJNMeJCyVbbWcBs"},
            {"name": "Daqui pra Sempre", "url": "https://open.spotify.com/track/4mHABnMETGqiBNlT7VpEmE"},
            {"name": "Só Pra Você Lembrar", "url": "https://open.spotify.com/track/1KJfZGeBoouFHJF8Fmegq1"},
            {"name": "Não Tem Explicação", "url": "https://open.spotify.com/track/2kMRyVoJLlxQJYkiYlKFZB"},
            {"name": "Saudade do Nordeste", "url": "https://open.spotify.com/track/7tVuZFhIBq5QhJmyZQMqEA"},
            {"name": "Fui Flor", "url": "https://open.spotify.com/track/3TtbgIFnBM6VhK8MlOMiDB"},
            {"name": "Volta Comigo", "url": "https://open.spotify.com/track/6NkUMTbpkJWS4fVFUJ0fJ5"},
            {"name": "Batom de Cereja", "url": "https://open.spotify.com/track/3oNrXGFBrBjsFr4NAXM0De"},
            {"name": "Não Vai Ter Volta", "url": "https://open.spotify.com/track/0VuYBrgCCIYDr0SWQRFJXY"},
            {"name": "Dos Beijos que Dei", "url": "https://open.spotify.com/track/2TfSHkHiFO4gMQlZSt9Gfe"},
        ]
    },
    "joão gomes": "joao gomes",  # alias
}


VERIFIED_ARTIST_IDS = {
    "joao gomes": "3Iy0rMbqTSPTWnvU7OsIov",
    "joão gomes": "3Iy0rMbqTSPTWnvU7OsIov",
}


def _get_access_token() -> str | None:
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return None
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]
    try:
        credentials = base64.b64encode(
            f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {credentials}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        _token_cache["token"]      = data["access_token"]
        _token_cache["expires_at"] = time.time() + data["expires_in"] - 60
        return _token_cache["token"]
    except Exception as e:
        print(f"[SPOTIFY] Erro token: {e}")
        return None


def _load_local_db(artist_name: str) -> list[dict] | None:
    """Retorna músicas da base local se disponível."""
    key = artist_name.lower()
    entry = LOCAL_MUSIC_DB.get(key)
    if isinstance(entry, str):
        # É um alias — busca a entrada real
        entry = LOCAL_MUSIC_DB.get(entry)
    if entry:
        tracks = entry["tracks"]
        display = entry["artist_display"]
        return [{"name": t["name"], "artist": display, "artists": [display],
                 "album": "", "url": t["url"], "feature": False,
                 "popularity": 80} for t in tracks]
    return None


def _fetch_via_api(artist_name: str, token: str) -> list[dict]:
    """Tenta buscar via Spotify API sem parâmetros que causam 403."""
    tracks_found = {}
    headers = {"Authorization": f"Bearer {token}"}

    # Query simples sem operadores especiais e sem market
    queries = [
        artist_name,
        f"{artist_name} forró",
        f"{artist_name} sertanejo",
    ]

    for q in queries:
        try:
            r = requests.get(
                "https://api.spotify.com/v1/search",
                headers=headers,
                params={"q": q, "type": "track", "limit": 50},
                timeout=10,
            )
            if r.status_code == 403:
                print(f"[SPOTIFY] API retornou 403 — usando base local")
                return []
            r.raise_for_status()

            for track in r.json().get("tracks", {}).get("items", []):
                artist_names = [a["name"] for a in track["artists"]]
                # Verifica se o artista realmente participa
                artist_clean = artist_name.lower().replace("ã","a").replace("ô","o")
                found = any(
                    artist_clean in a.lower().replace("ã","a").replace("ô","o")
                    for a in artist_names
                )
                if not found:
                    continue

                name = track["name"]
                if name not in tracks_found:
                    tracks_found[name] = {
                        "name":       name,
                        "artist":     artist_names[0],
                        "artists":    artist_names,
                        "album":      track["album"]["name"],
                        "url":        track["external_urls"].get("spotify", ""),
                        "popularity": track.get("popularity", 0),
                        "feature":    False,
                    }
        except requests.exceptions.HTTPError as e:
            if "403" in str(e):
                return []
        except Exception as e:
            print(f"[SPOTIFY] Erro query: {e}")

    result = list(tracks_found.values())
    result.sort(key=lambda x: x["popularity"], reverse=True)
    return result


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict):
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_artist_top_tracks(artist_name: str, limit: int = 999) -> list[dict]:
    """
    Retorna músicas do artista.
    Prioridade: cache → API → base local.
    """
    cache_key = artist_name.lower().replace(" ", "_")
    cache     = _load_cache()
    entry     = cache.get(cache_key)

    if entry and time.time() - entry.get("cached_at", 0) < _CACHE_TTL:
        tracks = entry["tracks"]
        print(f"[SPOTIFY] {len(tracks)} músicas do cache para {artist_name}")
        return tracks[:limit]

    # Tenta API
    token = _get_access_token()
    api_tracks = []
    if token:
        api_tracks = _fetch_via_api(artist_name, token)

    if api_tracks:
        print(f"[SPOTIFY] {len(api_tracks)} músicas via API para {artist_name}")
        cache[cache_key] = {"tracks": api_tracks, "cached_at": time.time()}
        _save_cache(cache)
        return api_tracks[:limit]

    # Fallback: base local
    local = _load_local_db(artist_name)
    if local:
        print(f"[SPOTIFY] Usando base local: {len(local)} músicas para {artist_name}")
        cache[cache_key] = {"tracks": local, "cached_at": time.time()}
        _save_cache(cache)
        return local[:limit]

    print(f"[SPOTIFY] Nenhuma música encontrada para {artist_name}")
    return []


def get_random_track(artist_name: str) -> dict | None:
    tracks = get_artist_top_tracks(artist_name)
    if not tracks:
        return None
    top = tracks[:20] if len(tracks) >= 20 else tracks
    return random.choice(top)


def is_configured() -> bool:
    return bool(settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET)
