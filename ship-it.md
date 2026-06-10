# Ship-it Guide — Telegram Ollama Campaign Bot

This document contains the exact steps to ship the Campaign Bot to production.

## 1. Prerequisites

- Ubuntu/Debian server with at least 16GB RAM (recommended 23GB+)
- Ollama installed
- Python 3.10+
- Telegram bot token from @BotFather
- Root or sudo access

## 2. One-time Server Setup

```bash
# Install Ollama (if not installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the recommended model
ollama pull llama3.1:8b

# Clone or copy this project to the server
git clone <your-repo> /opt/campaign-bot
cd /opt/campaign-bot
```

## 3. Environment Setup

```bash
make setup
cp .env.example .env

# Edit .env and add your token
nano .env
```

Required variables:
```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
OLLAMA_MODEL=llama3.1:8b
```

## 4. Initialize Database

```bash
make db
```

## 5. Run Locally (Testing)

```bash
make run
```

Test commands in Telegram:
- `/start`
- `/campaign Test topic`
- `/mycampaigns`
- `/resume`

## 6. Production Deployment (Recommended)

### Option A: Systemd Service (Recommended)

Create `/etc/systemd/system/campaign-bot.service`:

```ini
[Unit]
Description=Telegram Ollama Campaign Bot
After=network.target

[Service]
Type=simple
User=supremeleader
WorkingDirectory=/opt/campaign-bot
Environment="PATH=/opt/campaign-bot/.venv/bin"
ExecStart=/opt/campaign-bot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable campaign-bot
sudo systemctl start campaign-bot
sudo systemctl status campaign-bot
```

### Option B: Docker (Alternative)

```bash
# Future improvement — not yet implemented
```

## 7. Monitoring & Maintenance

```bash
# View logs
sudo journalctl -u campaign-bot -f

# Restart bot
sudo systemctl restart campaign-bot

# Update model
ollama pull llama3.1:8b

# Backup database
cp campaigns.db campaigns.db.backup
```

## 8. Security Notes

- Never commit `.env`
- Keep `TELEGRAM_BOT_TOKEN` secret
- Run as non-root user when possible
- Consider running behind a firewall

## 9. Quick Ship Checklist

- [ ] `make setup` completed
- [ ] `llama3.1:8b` downloaded
- [ ] `.env` configured with real token
- [ ] `make db` executed
- [ ] Bot tested with `/campaign`
- [ ] Systemd service created and enabled
- [ ] Logs verified with `journalctl`

---

**Current recommended model**: `llama3.1:8b`  
**Alternative**: `qwen2.5:14b` (if more power is needed)