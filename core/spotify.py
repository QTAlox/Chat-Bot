"""
core/spotify.py
===============
Integração com a API oficial do Spotify (gratuita).

SETUP:
  1. developer.spotify.com → Create App
  2. Nome: Chat-Bot | Redirect URI: http://localhost
  3. Copia Client ID e Client Secret para o .env
"""

import time
import base64
import requests
from config import settings

_token_cache = {"token": None, "expires_at": 0}

# IDs verificados de artistas no Spotify BR
# Para adicionar mais: abra o Spotify → artista → compartilhar → copiar link
# O ID é o código após /artist/ na URL
VERIFIED_ARTIST_IDS = {
    "joao gomes":  "3Iy0rMbqTSPTWnvU7OsIov",
    "joão gomes":  "3Iy0rMbqTSPTWnvU7OsIov",
    # Adicione mais aqui:
    # "mc ryan sp": "ID_DO_ARTISTA",
    # "luan santana": "ID_DO_ARTISTA",
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
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        _token_cache["token"]      = data["access_token"]
        _token_cache["expires_at"] = time.time() + data["expires_in"] - 60
        print("[SPOTIFY] Token obtido")
        return _token_cache["token"]
    except Exception as e:
        print(f"[SPOTIFY] Erro token: {e}")
        return None


def get_artist_top_tracks(artist_name: str, limit: int = 10) -> list[dict]:
    """
    Busca as top tracks de um artista usando o ID verificado.
    Garante que são músicas reais do artista correto.
    """
    token = _get_access_token()
    if not token:
        return []

    # Usa ID verificado se disponível — evita pegar artista errado
    artist_id = VERIFIED_ARTIST_IDS.get(artist_name.lower())

    if not artist_id:
        # Busca o artista pelo nome
        try:
            r = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": artist_name, "type": "artist", "market": "BR", "limit": 3},
                timeout=10,
            )
            r.raise_for_status()
            items = r.json().get("artists", {}).get("items", [])

            # Pega o artista com nome mais parecido
            for item in items:
                name_clean    = item["name"].lower().replace("ã","a").replace("ô","o").replace("é","e")
                artist_clean  = artist_name.lower().replace("ã","a").replace("ô","o").replace("é","e")
                if artist_clean in name_clean or name_clean in artist_clean:
                    artist_id = item["id"]
                    print(f"[SPOTIFY] Artista encontrado: {item['name']} ({artist_id})")
                    break

        except Exception as e:
            print(f"[SPOTIFY] Erro busca artista: {e}")
            return []

    if not artist_id:
        print(f"[SPOTIFY] Artista não encontrado: {artist_name}")
        return []

    try:
        r = requests.get(
            f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks",
            headers={"Authorization": f"Bearer {token}"},
            params={"market": "BR"},
            timeout=10,
        )
        r.raise_for_status()
        tracks = r.json().get("tracks", [])[:limit]

        result = []
        for t in tracks:
            result.append({
                "name":       t["name"],
                "artist":     t["artists"][0]["name"],
                "album":      t["album"]["name"],
                "url":        t["external_urls"]["spotify"],
                "popularity": t["popularity"],
            })

        names = [t["name"] for t in result]
        print(f"[SPOTIFY] Músicas reais: {names}")
        return result

    except Exception as e:
        print(f"[SPOTIFY] Erro top tracks: {e}")
        return []


def is_configured() -> bool:
    return bool(settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET)
