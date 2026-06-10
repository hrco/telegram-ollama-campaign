.PHONY: help setup run model interface db clean

help:
	@echo "Campaign Bot Makefile"
	@echo ""
	@echo "  make setup     Install dependencies + init DB"
	@echo "  make model     Download best model for this machine (llama3.1:8b)"
	@echo "  make run       Run the Telegram bot"
	@echo "  make interface Run the FastAPI web interface"
	@echo "  make db        Initialize SQLite database"
	@echo "  make clean     Remove generated files"

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	@echo "✓ Dependencies installed"

model:
	@echo "Downloading best model for this machine (llama3.1:8b)..."
	ollama pull llama3.1:8b
	@echo "✓ Model ready. You can also try: ollama pull qwen2.5:14b"

run:
	. .venv/bin/activate && python bot.py

interface:
	. .venv/bin/activate && uvicorn interface:app --reload --port 8000

db:
	. .venv/bin/activate && python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
	@echo "✓ Database initialized"

clean:
	rm -f campaigns.db
	rm -rf __pycache__ .pytest_cache
	@echo "✓ Cleaned"