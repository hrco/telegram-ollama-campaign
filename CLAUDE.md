# CampaignOS — project context for AI agents

> Self-hosted Telegram marketing OS powered by **local** Ollama. Free, open-source, private.
> A user runs marketing campaigns end-to-end: research → content → social copy → schedule →
> broadcast to Telegram channels, driven from a Telegram bot **and** a web dashboard.

This file overrides the monorepo root `CLAUDE.md` for anything project-specific. Read it first.

## Pre-flight (do this before significant work)
1. **Read `HANDOFF.md`** — current real status, blockers, and the prioritized task list. It is
   the single source of truth for "what to do next"; this file is just orientation.
2. Then the plan `docs/superpowers/plans/2026-06-10-campaignos-v2.md` and spec
   `docs/superpowers/specs/2026-06-10-campaignos-v2-design.md`.
3. Run `source .venv/bin/activate && pytest -q` to confirm you start from green (16 tests).

## Stack
Python 3.12, aiogram 3.x (Telegram bot), FastAPI + uvicorn + Jinja2 (dashboard), aiosqlite
(SQLite), APScheduler 3.x (in-process scheduling), PyJWT + bcrypt (auth), ollama (local LLM,
default `llama3.1:8b`), Tailwind + Alpine (UI, served from local `/static`). Tests: pytest +
pytest-asyncio.

## Architecture
Single Python process. `main.py` runs the aiogram bot and the FastAPI dashboard concurrently
(`asyncio.gather`); APScheduler fires scheduled broadcasts in-process. Everything persists to
one SQLite file (`campaigns.db`). Module map:

| File | Role |
|------|------|
| `main.py` | Unified entrypoint (bot + dashboard + scheduler) |
| `bot.py` | aiogram handlers (`/new`, `/social`, `/channels`, …) |
| `dashboard.py` | FastAPI routes + auth-gated web UI |
| `auth.py` | JWT cookie auth, password verify, `require_auth` dependency |
| `broadcaster.py` | Send to channels: split, retry, flood-control |
| `scheduler.py` | APScheduler wrapper: one-shot + cron, execute/cancel |
| `database.py` | Schema + CRUD: users, campaigns, messages, channels, scheduled_posts, send_analytics |
| `campaign_protocol.py` | Phase prompt templates (research / content / schedule / social_copy) |
| `states.py` | aiogram FSM states |
| `templates/` | Jinja2 pages |

> Note: `interface.py` is legacy v1 — the live web app is `dashboard.py` via `main.py`. Don't
> add features to `interface.py`.

## Conventions (project-specific; inherit the rest from monorepo root)
- **TDD.** Failing test first → minimal code → green → commit. Plan tasks ship their tests.
- **One logical change per commit**: `feat:` / `fix:` / `test:` / `docs:`. Sign with the
  SpectreHawk soul line (see `git log`), not corporate boilerplate.
- **Secrets:** `.env` holds a **real bot token** and is gitignored — never stage it, never echo
  its values into context or commits. `.env.example` is the only committed env file.
- **Local-first:** Ollama is the default and primary LLM provider. `llm.py` supports xAI/Grok as
  an optional escape hatch (`LLM_PROVIDER=xai` + `XAI_API_KEY`). Never make a paid provider the
  default or a hard dependency.
- **Run from venv:** `source .venv/bin/activate` before pytest / uvicorn / `python main.py`.

## Run it
```bash
make setup            # venv + deps
make model            # ollama pull llama3.1:8b
make all              # bot + dashboard + scheduler at http://localhost:8000
```
Dashboard login uses `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.

## Known limitations (see HANDOFF.md for the full list)
Single-admin only (dashboard hardcodes `user_id=1`); admin password compared in plaintext from
env; APScheduler jobs are in-memory (need restart reconciliation). Fine for self-hosted demo,
flagged before any multi-user promotion.
