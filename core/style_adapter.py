"""
core/style_adapter.py
=====================
Analisa as mensagens do canal e descreve o estilo de escrita do grupo.
Essa descrição é injetada no system prompt para o Felipe se adaptar.
"""

import re
from core.memory import get_recent_messages


def analyze_channel_style(channel_id: int) -> str:
    messages = get_recent_messages(channel_id, n=50)
    if len(messages) < 5:
        return ""

    texts        = [m.content for m in messages]
    observations = []

    # Comprimento médio
    avg_len = sum(len(t) for t in texts) / len(texts)
    if avg_len < 30:
        observations.append("as mensagens são bem curtas e diretas")
    elif avg_len > 150:
        observations.append("as pessoas escrevem mensagens mais longas e detalhadas")

    # Gírias e linguagem informal
    girias = ["mano", "cara", "kkk", "po", "véi", "carai", "porra",
              "caralho", "foda", "nao", "tb", "vc", "vcs", "pq", "msm", "mt"]
    giria_count = sum(1 for t in texts for g in girias if g in t.lower())
    if giria_count > len(texts) * 0.4:
        observations.append("o grupo usa muitas gírias e linguagem bem informal")

    # Emojis
    emoji_pat  = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+", flags=re.UNICODE
    )
    emoji_msgs = sum(1 for t in texts if emoji_pat.search(t))
    if emoji_msgs / len(texts) > 0.5:
        observations.append("emojis são usados com bastante frequência")
    elif emoji_msgs / len(texts) < 0.1:
        observations.append("quase ninguém usa emojis aqui")

    # Risadas
    risos = sum(1 for t in texts if re.search(r'k{3,}|haha|rsrs', t.lower()))
    if risos / len(texts) > 0.3:
        observations.append("o grupo tem um tom leve e ri bastante")

    # CAPS para ênfase
    upper = sum(1 for t in texts if t == t.upper() and len(t) > 3)
    if upper / len(texts) > 0.2:
        observations.append("o grupo usa CAIXA ALTA para dar ênfase")

    if not observations:
        return "o grupo conversa de forma casual e descontraída"

    return "; ".join(observations) + "."
