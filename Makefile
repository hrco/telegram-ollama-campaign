.PHONY: help setup all dashboard run model test db clean

help:
	@echo "CampaignOS Makefile"
	@echo ""
	@echo "  make setup     Install dependencies into .venv"
	@echo "  make model     Download the local model (llama3.1:8b)"
	@echo "  make all       Run everything: bot + dashboard + scheduler (python main.py)"
	@echo "  make dashboard Run the web dashboard only (http://localhost:8000)"
	@echo "  make run       Run the Telegram bot only"
	@echo "  make test      Run the test suite"
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

all:
	. .venv/bin/activate && python main.py

dashboard:
	. .venv/bin/activate && uvicorn dashboard:app --reload --port 8000

run:
	. .venv/bin/activate && python bot.py

test:
	. .venv/bin/activate && python -m pytest -q

db:
	. .venv/bin/activate && python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
	@echo "✓ Database initialized"

clean:
	rm -f campaigns.db
	rm -rf __pycache__ .pytest_cache
	@echo "✓ Cleaned"