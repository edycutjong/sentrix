<div align="center">
  <h1>Sentrix 🛡️</h1>
  <p><em>AI-powered DeFi position monitor for Injective</em></p>
  <img src="docs/readme-hero.png" alt="Sentrix" width="100%">

  <br/>

  [![Live Demo](https://img.shields.io/badge/🚀_Live-Demo-06b6d4?style=for-the-badge)](https://github.com/edycutjong/sentrix)
  [![Pitch Video](https://img.shields.io/badge/🎬_Pitch-Video-ef4444?style=for-the-badge)](https://youtu.be/your-video)
  [![Pitch Deck](https://img.shields.io/badge/📊_Pitch-Deck-f59e0b?style=for-the-badge)](https://github.com/edycutjong/sentrix/pitch)
  [![Built for Injective](https://img.shields.io/badge/Devpost-Injective_Hackathon-8b5cf6?style=for-the-badge)](https://devpost.com/)

  <br/>

  ![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white)
  ![Injective](https://img.shields.io/badge/Injective-00A3FF?style=flat&logoColor=white)
  ![OpenAI](https://img.shields.io/badge/GPT--4o-412991?style=flat&logo=openai&logoColor=white)
  [![CI](https://github.com/edycutjong/sentrix/actions/workflows/ci.yml/badge.svg)](https://github.com/edycutjong/sentrix/actions/workflows/ci.yml)

</div>

---

## 📸 See it in Action

<div align="center">
  <img src="docs/readme.png" alt="Sentrix Demo" width="100%">
</div>

> **Stay ahead of liquidations.** Monitor → Detect → Analyze → Deliver.

---

## 💡 The Problem & Solution
DeFi traders often lose funds to liquidations because monitoring multiple positions 24/7 is impossible. 
**Sentrix** solves this by polling Injective derivative positions and using AI to explain liquidation risks in plain English, alerting you via Telegram or Discord before it's too late.

**Key Features:**
- ⚡ **Position Monitoring:** Polls Injective derivative positions every 30s.
- 🔒 **Risk Detection:** Detects liquidation proximity, balance changes, and margin degradation.
- 🎨 **AI Analysis:** Natural-language risk explanations via GPT-4o-mini / Gemini Flash.

## 🏗️ Architecture & Tech Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.12 |
| **Chain SDK** | injective-py |
| **AI** | OpenAI GPT-4o-mini / Google Gemini Flash |
| **Alerts** | python-telegram-bot / Discord webhooks |
| **CLI** | Click + Rich |
| **Storage** | aiosqlite |
| **Data** | Pydantic v2 |

## 🏆 Sponsor Tracks Targeted
- **Injective** — Utilizing injective-py for live on-chain monitoring.
- **OpenAI / Google** — Utilizing AI models for real-time natural language risk analysis.

## 🚀 Getting Started

### Prerequisites
- Python ≥ 3.11

### Installation
1. Clone: `git clone https://github.com/edycutjong/sentrix.git`
2. Install: `pip install -e .`
3. Configure: `cp config.example.yaml config.yaml` and add your keys
4. Run: `sentrix watch --demo`

> **For Judges:** Skip account creation! Use the demo flag:
> `sentrix watch --demo`

## 🧪 Testing & CI
```bash
ruff check .          # Linting
pytest -v             # Run tests
```

## 📁 Project Structure
```
sentrix/
├── docs/              # README assets (hero, screenshots)
├── src/
│   └── sentrix/       # Core application
├── tests/             # Pytest test suite
├── .env.example       # Environment template
├── config.example.yaml# Config template
├── .github/           # CI workflows
└── README.md          # You are here
```

## 📄 License
[MIT](LICENSE) © 2026 Edy Cu

## 🙏 Acknowledgments
Built for the Injective Ecosystem. Thank you to the sponsors for the APIs and tools.
