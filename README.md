# 🛡️ Sentrix

**AI-powered DeFi position monitor for Injective.**

Detects liquidation risks across derivative positions, explains them in plain English using AI, and alerts you via Telegram or Discord — before it's too late.

## Quick Start

```bash
pip install sentrix
sentrix watch --demo
```

## Features

- **Position Monitoring**: Polls Injective derivative positions every 30s
- **Risk Detection**: Liquidation proximity, balance changes, margin degradation
- **AI Analysis**: Natural-language risk explanations via GPT-4o-mini / Gemini Flash
- **Multi-Channel Alerts**: Telegram, Discord, and console
- **Demo Mode**: Try it instantly with `--demo` flag (no wallet needed)
- **Alert History**: SQLite-backed local alert log

## Installation

```bash
pip install sentrix
cp config.example.yaml config.yaml  # Edit with your settings
```

## Usage

```bash
# Demo mode (mock data)
sentrix watch --demo

# Monitor a specific address
sentrix watch --address inj1abc...

# Show current positions
sentrix status --demo

# View alert history
sentrix history
```

## Configuration

Copy `config.example.yaml` and customize:

```yaml
network: mainnet
poll_interval_seconds: 30
addresses:
  - address: "inj1your_address"
    label: "My Wallet"
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
llm:
  provider: openai
  model: gpt-4o-mini
```

Or use environment variables:

```bash
export SENTRIX_ADDRESSES=inj1aaa,inj1bbb
export SENTRIX_TELEGRAM_TOKEN=your_token
export OPENAI_API_KEY=sk-...
```

## Architecture

```
Monitor → Detect → Analyze → Deliver
  │          │         │         │
  │          │         │         ├── Console (Rich)
  │          │         │         ├── Telegram Bot
  │          │         │         └── Discord Webhook
  │          │         │
  │          │         └── LLM Client (OpenAI / Gemini)
  │          │
  │          └── Risk Detector (margin ratio, balance Δ)
  │
  └── Injective Client (injective-py SDK)
```

## Development

```bash
git clone https://github.com/edycutjong/sentrix.git
cd sentrix
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Chain SDK | injective-py |
| AI | OpenAI GPT-4o-mini / Google Gemini Flash |
| Alerts | python-telegram-bot / Discord webhooks |
| CLI | Click + Rich |
| Storage | aiosqlite |
| Data | Pydantic v2 |

## License

MIT — see [LICENSE](LICENSE)
