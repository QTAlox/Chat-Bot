# Chat-Bot

Chatbot multi-plataforma com IA generativa que age como uma pessoa real,
aprendendo e se adaptando ao estilo de cada comunidade.

## Plataformas
- **Fase 1:** Discord (conta normal, selfbot)
- **Fase 2:** Telegram / WhatsApp
- **Fase 3:** Twitch / Kick / YouTube

## Setup

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar
cp .env.example .env
# Preencha o .env com seus tokens

# 3. Rodar
python main.py
```

## Tokens necessários
| Variável | Onde obter |
|---|---|
| `DISCORD_TOKEN` | F12 no Discord Web → Network → Authorization |
| `GROQ_API_KEY` | console.groq.com (grátis) |
| `ALLOWED_GUILD_IDS` | Discord Developer Mode → botão direito no servidor |

## Estrutura
```
Chat-Bot/
├── config/
│   ├── settings.py       # carrega o .env
│   └── persona.yaml      # personalidade do Felipe
├── core/
│   ├── brain.py          # chama a IA (Groq ou Ollama)
│   ├── memory.py         # memória curto/longo prazo
│   ├── style_adapter.py  # aprende estilo do grupo
│   ├── decision_engine.py# decide quando responder
│   └── persona.py        # monta o system prompt
├── platforms/
│   ├── discord/          # fase 1 ✅
│   ├── telegram/         # fase 2 🔜
│   └── streaming/        # fase 3 🔜
├── data/                 # banco local (não vai pro Git)
├── main.py
├── requirements.txt
└── .env.example
```
