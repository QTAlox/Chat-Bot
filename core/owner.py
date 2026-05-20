"""
core/owner.py
=============
Sistema de controle do bot pelo dono.
Só o OWNER_ID definido no .env pode usar esses comandos.

COMANDOS (via DM ou mencionando o bot no servidor):
  !felipe status          — mostra configurações atuais
  !felipe silencio [min]  — fica quieto por X minutos
  !felipe falar [msg]     — força ele a mandar uma mensagem
  !felipe girias [0-10]   — ajusta nível de gírias na hora
  !felipe reset           — limpa a memória do canal
  !felipe arrombado       — ativa modo arrombado
  !felipe normal          — volta ao modo normal
"""

import time
from config import settings

# Estado atual do bot (modificável em runtime pelo dono)
_state = {
    "silent_until": 0,          # timestamp até quando fica quieto
    "arrombado_mode": False,     # modo arrombado ativo
    "slang_level": settings.SLANG_LEVEL,
    "laugh_level": settings.LAUGH_LEVEL,
    "formality_level": settings.FORMALITY_LEVEL,
}


def is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


def is_silent() -> bool:
    return time.time() < _state["silent_until"]


def is_arrombado() -> bool:
    return _state["arrombado_mode"]


def get_state() -> dict:
    return _state.copy()


def get_slang_level() -> int:
    return _state["slang_level"]


def get_laugh_level() -> int:
    return _state["laugh_level"]


def get_formality_level() -> int:
    return _state["formality_level"]


async def handle_owner_command(message, bot_client) -> str | None:
    """
    Processa um comando do dono.
    Retorna a resposta a ser enviada, ou None se não for comando.
    """
    from core.memory import _channel_buffers

    content = message.content.strip()

    # Remove o prefixo de menção ou "!felipe" para pegar só o comando
    cmd = content.lower()
    for prefix in [f"<@{bot_client.user.id}>", f"<@!{bot_client.user.id}>",
                   "!felipe", "!felipe"]:
        cmd = cmd.replace(prefix, "").strip()

    if not cmd:
        return None

    parts = cmd.split()
    command = parts[0] if parts else ""
    args = parts[1:] if len(parts) > 1 else []

    # ── !status ──────────────────────────────────────────────────────
    if command == "status":
        silent_left = max(0, int(_state["silent_until"] - time.time()))
        mode = "ARROMBADO 🔥" if _state["arrombado_mode"] else "normal"
        return (
            f"**status do felipe:**\n"
            f"modo: {mode}\n"
            f"silêncio: {'sim (' + str(silent_left) + 's)' if silent_left else 'não'}\n"
            f"gírias: {_state['slang_level']}/10\n"
            f"kkk: {_state['laugh_level']}/10\n"
            f"formalidade: {_state['formality_level']}/10"
        )

    # ── !silencio [minutos] ───────────────────────────────────────────
    elif command == "silencio":
        mins = int(args[0]) if args and args[0].isdigit() else 10
        _state["silent_until"] = time.time() + (mins * 60)
        return f"ok, fico quieto por {mins} minuto(s)"

    # ── !falar [mensagem] ─────────────────────────────────────────────
    elif command == "falar":
        if not args:
            return "me diz o que falar"
        msg = " ".join(args)
        await message.channel.send(msg)
        return None  # já mandou

    # ── !girias [0-10] ────────────────────────────────────────────────
    elif command == "girias":
        if args and args[0].isdigit():
            val = max(0, min(10, int(args[0])))
            _state["slang_level"] = val
            return f"nível de gírias ajustado para {val}/10"
        return "usa: !felipe girias [0-10]"

    # ── !kkk [0-10] ───────────────────────────────────────────────────
    elif command == "kkk":
        if args and args[0].isdigit():
            val = max(0, min(10, int(args[0])))
            _state["laugh_level"] = val
            return f"nível de kkk ajustado para {val}/10"
        return "usa: !felipe kkk [0-10]"

    # ── !formalidade [0-10] ───────────────────────────────────────────
    elif command == "formalidade":
        if args and args[0].isdigit():
            val = max(0, min(10, int(args[0])))
            _state["formality_level"] = val
            return f"formalidade ajustada para {val}/10"
        return "usa: !felipe formalidade [0-10]"

    # ── !reset ────────────────────────────────────────────────────────
    elif command == "reset":
        if message.channel.id in _channel_buffers:
            _channel_buffers[message.channel.id].clear()
        return "memória desse canal limpa"

    # ── !arrombado ────────────────────────────────────────────────────
    elif command == "arrombado":
        _state["arrombado_mode"] = True
        return "modo arrombado ativado 🔥"

    # ── !normal ───────────────────────────────────────────────────────
    elif command == "normal":
        _state["arrombado_mode"] = False
        _state["silent_until"] = 0
        return "voltei ao modo normal"

    # ── !ajuda ────────────────────────────────────────────────────────
    elif command in ("ajuda", "help", "comandos"):
        return (
            "**comandos disponíveis:**\n"
            "`!felipe status` — situação atual\n"
            "`!felipe silencio [min]` — fica quieto\n"
            "`!felipe falar [msg]` — manda uma msg\n"
            "`!felipe girias [0-10]` — ajusta gírias\n"
            "`!felipe kkk [0-10]` — ajusta risadas\n"
            "`!felipe formalidade [0-10]` — ajusta formalidade\n"
            "`!felipe reset` — limpa memória do canal\n"
            "`!felipe arrombado` — ativa modo arrombado 🔥\n"
            "`!felipe normal` — volta ao modo normal"
        )

    return None
