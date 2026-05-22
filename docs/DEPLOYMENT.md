# ☁️ Sentrix Deployment Guide

Sentrix is designed to run as a lightweight background daemon (worker process) that continuously polls Injective positions and sends AI-analyzed alerts to your Telegram or Discord channels.

This guide explains how to deploy Sentrix to **Railway** for 24/7 monitoring.

---

## 🚀 Deploying to Railway

### Prerequisites
- A [Railway](https://railway.app) account.
- A GitHub repository containing your Sentrix codebase.

### Step 1: Create a Railway Service
1. Log in to [Railway](https://railway.app).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your cloned `sentrix` repository.

### Step 2: Configure Environment Variables
In your Railway dashboard under the **Variables** tab of the service, add the following variables (refer to your [env example](file:///Users/edycu/Projects/Hackathon/Sentrix/.env.example) for details):

| Variable | Description | Example / Source |
|---|---|---|
| `SENTRIX_NETWORK` | The Injective network to connect to | `mainnet` or `testnet` |
| `SENTRIX_POLL_INTERVAL` | Polling frequency in seconds | `30` |
| `SENTRIX_DEMO` | Use mock positions (for testing) | `false` |
| `SENTRIX_ADDRESSES` | Injective addresses to monitor (comma-separated) | `inj1...,inj1...` |
| `OPENAI_API_KEY` | OpenAI API Key (optional) | `sk-...` |
| `GEMINI_API_KEY` | Google Gemini API Key (optional) | `AIza...` |
| `SENTRIX_TELEGRAM_TOKEN` | Telegram Bot Token (optional) | Get from `@BotFather` |
| `SENTRIX_TELEGRAM_CHAT_ID` | Telegram Chat ID (optional) | Get from `@userinfobot` |
| `SENTRIX_DISCORD_WEBHOOK` | Discord Webhook URL (optional) | Channel Settings -> Integrations |

### Step 3: Nixpacks Build & Run
Railway uses the [railway.json](file:///Users/edycu/Projects/Hackathon/Sentrix/railway.json) file automatically:
- **Build Provider**: `Nixpacks` (automatically installs Python, dependencies, and packages defined in `pyproject.toml`).
- **Start Command**: `PYTHONPATH=src python -m sentrix.cli watch`
- **Health Check**: No port binding or HTTP health check is needed since it runs as a background worker.

Once the deployment completes, check the **Deployments** tab to see real-time console logs of the Sentrix monitoring loop!
