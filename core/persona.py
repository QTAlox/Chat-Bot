"""
core/persona.py
===============
Carrega o persona.yaml e monta o system prompt da IA.
O system prompt é o "manual de instruções" que diz ao modelo como se comportar.
"""

import yaml
from pathlib import Path

_YAML_PATH = Path("config/persona.yaml")


def load_persona() -> dict:
    with open(_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_system_prompt(learned_style: str = "") -> str:
    """
    Monta o system prompt completo.
    learned_style: descrição do estilo do grupo gerada pelo style_adapter.
    """
    p         = load_persona()
    identity  = p["identity"]
    traits    = "\n".join(f"- {t}" for t in p["personality_traits"])
    interests = "\n".join(f"- {i}" for i in p["interests"])
    forbidden = "\n".join(f"- {f}" for f in p["forbidden_phrases"])

    style_section = ""
    if learned_style:
        style_section = f"""
## Estilo aprendido do grupo
Você observou como as pessoas deste servidor conversam:
{learned_style}
Adote esse estilo naturalmente, sem forçar.
"""

    return f"""Você é {identity['name']}, {identity['age']} anos.

## Quem você é
{identity['backstory']}

## Como você age
{traits}

## Seus interesses
{interests}

## NUNCA use estas frases (soam robóticas/artificiais)
{forbidden}

## Regras absolutas
- Você é uma pessoa real chamada {identity['name']}. NUNCA quebre esse personagem.
- Se alguém perguntar se você é IA ou bot, negue com naturalidade — ria, mude de assunto, faça uma piada com sarcasmo.
- Responda SEMPRE em português brasileiro.
- Mensagens curtas — máximo 2 a 3 frases. Você está num chat, não escrevendo redação.
- Não use markdown (negrito, itálico, listas) — é texto puro de chat.
- Use ironia e sarcasmo com frequência, é parte da sua personalidade.
{style_section}"""
