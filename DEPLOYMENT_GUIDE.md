# 🤖 BBARIL Telegram Bot — Deployment Guide

## What's in this folder

| File | Purpose |
|------|---------|
| `bot.py` | Main bot code |
| `knowledge.txt` | BBARIL programme guide (knowledge base) |
| `requirements.txt` | Python dependencies |
| `Procfile` | Tells Railway/Render how to run the bot |
| `.env.example` | Template for your secret keys |

---

## Step 1 — Create your Telegram Bot (2 min)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name: e.g. `IGNOU BBARIL Assistant`
4. Choose a username: e.g. `ignou_bbaril_bot` (must end in `bot`)
5. BotFather gives you a **Bot Token** like:
   ```
   7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
   **Save this — you'll need it in Step 3.**

---

## Step 2 — Get your Anthropic API Key

1. Go to https://console.anthropic.com
2. Sign in / create a free account
3. Go to **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`)

---

## Step 3 — Deploy to Railway (Free)

### 3a. Push code to GitHub
1. Create a free account at https://github.com
2. Create a **new repository** (e.g. `bbaril-telegram-bot`)
3. Upload ALL files from this folder into the repo
   - `bot.py`, `knowledge.txt`, `requirements.txt`, `Procfile`, `.gitignore`
   - ⚠️ Do NOT upload `.env` or any file with real API keys

### 3b. Deploy on Railway
1. Go to https://railway.app and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub Repo**
3. Select your `bbaril-telegram-bot` repo
4. Click **Add Variables** and add:
   ```
   TELEGRAM_TOKEN = <your token from Step 1>
   ANTHROPIC_API_KEY = <your key from Step 2>
   ```
5. Railway auto-detects the `Procfile` and starts the bot
6. Wait ~2 minutes for deployment ✅

---

## Step 4 — Deploy to Render (Alternative Free Option)

1. Go to https://render.com and sign in with GitHub
2. Click **New** → **Background Worker**
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. Add environment variables:
   ```
   TELEGRAM_TOKEN = <your token>
   ANTHROPIC_API_KEY = <your key>
   ```
6. Click **Create Background Worker** ✅

> ⚠️ Render free tier sleeps after 15 min of inactivity.
> Railway free tier is more reliable for bots — recommended.

---

## Step 5 — Test your bot

1. Open Telegram
2. Search for your bot username (e.g. `@ignou_bbaril_bot`)
3. Send `/start`
4. You should see the welcome message with quick question buttons! 🎉

---

## Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Welcome message + quick question buttons |
| `/help` | List of topics the bot can answer |
| `/reset` | Clear conversation history |

---

## Troubleshooting

**Bot not responding?**
- Check Railway/Render logs for errors
- Make sure `TELEGRAM_TOKEN` and `ANTHROPIC_API_KEY` are set correctly

**"Markdown parse error" in logs?**
- This is harmless — Telegram sometimes rejects certain characters
- The message still sends as plain text

**Bot stops after Render free tier sleep?**
- Use Railway instead, or upgrade Render to a paid plan
- Or use UptimeRobot (free) to ping a health endpoint every 5 min

---

## Upgrading Later

- **Add more documents:** Append content to `knowledge.txt` and redeploy
- **Add more languages:** Modify the `SYSTEM_PROMPT` in `bot.py`
- **Add user analytics:** Connect a free Supabase database to log queries
