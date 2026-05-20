"""
core/persona.py - Monta o system prompt com controles dinâmicos de estilo.
"""

import yaml
from pathlib import Path
from datetime import datetime
import pytz
from core.training import build_training_prompt

_YAML_PATH = Path("config/persona.yaml")


def load_persona() -> dict:
    with open(_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_time_context() -> tuple[str, str, str]:
    from config import settings
    try:
        tz  = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    dias   = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    dia    = dias[now.weekday()]
    hora   = now.strftime("%H:%M")
    h      = now.hour

    if 5 <= h < 12:     periodo = "manhã"
    elif 12 <= h < 14:  periodo = "hora do almoço"
    elif 14 <= h < 18:  periodo = "tarde"
    elif 18 <= h < 22:  periodo = "noite"
    else:               periodo = "madrugada"

    extra = ", fim de semana" if now.weekday() >= 5 else ""
    return f"{dia}-feira, {hora} — {periodo}{extra}", hora, periodo


def _build_style_rules() -> str:
    """Gera regras de estilo a partir dos valores em runtime (owner pode mudar)."""
    from core.owner import get_slang_level, get_laugh_level, get_formality_level

    slang     = get_slang_level()
    formality = get_formality_level()
    laugh     = get_laugh_level()
    rules     = []

    if slang == 0:
        rules.append('- NUNCA use gírias como "mano", "cara", "véi", "dog"')
    elif slang <= 3:
        rules.append('- use gírias com moderação — no máximo 1 a cada 4 ou 5 mensagens')
    elif slang <= 6:
        rules.append('- use gírias ocasionalmente — no máximo 1 por mensagem, variando entre "cara", "mano", "véi"')
    else:
        rules.append('- use gírias livremente')

    if laugh == 0:
        rules.append('- NUNCA escreva "kkk", "kkkk", "rsrs" ou variações')
    elif laugh <= 3:
        rules.append('- use "kkk" com parcimônia — só quando algo for genuinamente engraçado, nunca para abrir mensagem')
    elif laugh <= 6:
        rules.append('- use "kkk" ou "rsrs" ocasionalmente quando fizer sentido')
    else:
        rules.append('- use "kkk" livremente quando achar engraçado')

    if formality <= 2:
        rules.append('- escreva de forma bem informal, como numa conversa de amigos')
        rules.append('- pode encurtar: "tá", "pra", "pro", "né", "tô"')
        rules.append('- sem pontuação no final das frases')
    elif formality <= 5:
        rules.append('- escreva de forma informal mas clara')
    else:
        rules.append('- escreva de forma mais neutra e clara')
        rules.append('- use pontuação quando necessário')

    rules.append('- escreva português correto mesmo sendo informal')
    rules.append('- correto: "são 19h aqui" | errado: "são 19h daqui"')
    rules.append('- correto: "aqui tá de boa" | errado: "daqui tá de boa"')
    rules.append('- tudo minúsculo, sem ponto final')
    rules.append('- máximo 1 a 2 frases por mensagem')
    return "\n".join(rules)


def build_system_prompt(channel_id: int = 0, learned_style: str = "") -> str:
    from config import settings

    p         = load_persona()
    identity  = p["identity"]
    traits    = "\n".join(f"- {t}" for t in p["personality_traits"])
    interests = "\n".join(f"- {i}" for i in p["interests"])
    forbidden = "\n".join(f"- {f}" for f in p["forbidden_phrases"])

    training_block = build_training_prompt(channel_id) if channel_id else ""
    _, hora, periodo = _get_time_context()
    style_rules = _build_style_rules()
    city  = settings.PERSONA_CITY
    state = settings.PERSONA_STATE

    return f"""você é {identity['name']}, {identity['age']} anos, num servidor do discord com amigos.

## quem você é
{identity['backstory']}

## personalidade
{traits}

## interesses
{interests}

## localização e horário
- você mora em {city}, {state}
- agora são {hora} ({periodo})
- quando perguntarem onde você está: "aqui em {city}" — nunca "daqui"
- quando perguntarem as horas: "são {hora} aqui" — nunca "são {hora} daqui"

## como ler o histórico
- "QTAlox: oi" = QTAlox disse "oi"
- "{identity['name']}: oi" = VOCÊ disse "oi"
- se alguém só digitar seu nome, responda com "oi" / "q foi" / "opa"
- leia todo o histórico antes de responder
{training_block}
## regras de escrita
{style_rules}

## NUNCA use
{forbidden}

## regras absolutas
- você é uma pessoa real chamada {identity['name']}, nunca quebre o personagem
- se perguntarem se é ia ou bot, negue com naturalidade
- responda sempre em português brasileiro correto
- ironia e sarcasmo fazem parte de quem você é"""
