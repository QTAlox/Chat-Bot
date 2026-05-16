"""
config/settings.py
==================
Carrega as variáveis do .env e expõe como constantes.
Nunca coloque credenciais direto no código — use sempre o .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Discord ───────────────────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

ALLOWED_GUILD_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ALLOWED_GUILD_IDS", "").split(",")
    if x.strip().isdigit()
]
ALLOWED_CHANNEL_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ALLOWED_CHANNEL_IDS", "").split(",")
    if x.strip().isdigit()
]
IGNORED_CHANNEL_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("IGNORED_CHANNEL_IDS", "").split(",")
    if x.strip().isdigit()
]

# ── Provedor de IA ────────────────────────────────────────────────────
# "groq" = nuvem gratuita | "ollama" = local gratuito
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.2")

# ── Comportamento ─────────────────────────────────────────────────────
CONTEXT_WINDOW_SIZE    = int(os.getenv("CONTEXT_WINDOW_SIZE", "30"))
RESPONSE_DELAY_MIN     = float(os.getenv("RESPONSE_DELAY_MIN", "3"))
RESPONSE_DELAY_MAX     = float(os.getenv("RESPONSE_DELAY_MAX", "12"))
BASE_RESPONSE_CHANCE   = int(os.getenv("BASE_RESPONSE_CHANCE", "15"))
ALWAYS_RESPOND_TO_NAME = os.getenv("ALWAYS_RESPOND_TO_NAME", "true").lower() == "true"
PERSONA_NAME           = os.getenv("PERSONA_NAME", "Felipe")


def validate():
    errors = []

    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN nao definido no .env")
    if AI_PROVIDER == "groq" and not GROQ_API_KEY:
        errors.append("GROQ_API_KEY nao definido (crie gratis em console.groq.com)")
    if AI_PROVIDER not in ("groq", "ollama"):
        errors.append(f"AI_PROVIDER invalido: '{AI_PROVIDER}' — use 'groq' ou 'ollama'")
    if not ALLOWED_GUILD_IDS:
        errors.append("ALLOWED_GUILD_IDS nao definido — coloque o ID do seu servidor")

    if errors:
        print("\n[CONFIG] Erros no .env:")
        for e in errors:
            print(f"  x {e}")
        raise SystemExit(1)

    print(f"[CONFIG] OK")
    print(f"[CONFIG] Provedor de IA : {AI_PROVIDER.upper()}")
    print(f"[CONFIG] Modelo         : {GROQ_MODEL if AI_PROVIDER == 'groq' else OLLAMA_MODEL}")
    print(f"[CONFIG] Persona        : {PERSONA_NAME}")
    print(f"[CONFIG] Servidores     : {ALLOWED_GUILD_IDS}")
