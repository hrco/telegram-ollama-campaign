# Plan: xBridge Promo Campaign on Telegram

## Overview
Use CampaignOS to run a promotional campaign for [xBridge MCP](https://xbridgemcp.com/) (Grok-API bridge for Claude Code) on Telegram channels. Full sweep-and-resend cycle, AI-generated copy, CodeRabbit reviews.

## Branch
`promo/xbridge` — all work branches from `master`, lands via PR with CodeRabbit review.

## Task 1 — Commit In-Flight Work
The working tree has uncommitted changes that need clean commits:
1. `git checkout -b promo/xbridge master`
2. `git add docs/launch-copy.md && git commit -m "docs: launch copy kit for CampaignOS promo"`
3. `git add llm.py templates/settings.html requirements.txt && git commit -m "feat: LLM provider abstraction + settings UI"`
4. `git add auth.py bot.py dashboard.py campaign_protocol.py database.py templates/base.html .env.example README.md CLAUDE.md && git commit -m "chore: sync remaining working-tree fixes"`
5. Verify tests: `source .venv/bin/activate && pytest -q` (expect 19/19 green)

## Task 2 — Track All Split Message IDs
**Why:** `broadcaster.py` only saves the last fragment's `message_id` when content is split at 4096 chars. Can't sweep what we don't track.

**Files:** `broadcaster.py`, `database.py`, `scheduler.py`

**Changes:**
- `broadcaster.py:send_to_channel()` → return `list[int]` (all message IDs), not `Optional[int]`
- `broadcaster.py:send_with_retry()` → return `list[int]` (chain all parts)
- `database.py` — add `message_ids TEXT` column to `send_analytics` (ALTER TABLE, comma-separated)
- `database.py:record_send_analytics()` → accept `message_ids: str` param
- `scheduler.py:_execute_post()` → pass all message IDs to `record_send_analytics`
- Add `list_channel_message_ids(campaign_id, channel_id)` query to fetch all IDs for sweep

## Task 3 — Add `sweep_channel` to Broadcaster
**Files:** `broadcaster.py`

**New function:**
```python
async def sweep_channel_messages(bot, chat_id: str, message_ids: list[int]):
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except (TelegramAPIError, MessageToDeleteNotFound):
            pass
        await asyncio.sleep(0.3)
```

## Task 4 — Add `/promo` Bot Command
**Files:** `bot.py`, `states.py`

**New command:** `@campaignos_bot /promo`
1. Finds or creates an "xBridge" campaign for this user
2. Generates 5 fresh social copy variants via `llm.generate()` (xBridge-tuned prompts)
3. Queries all tracked message_ids for this campaign's channels
4. Calls `sweep_channel_messages()` to delete old promo posts
5. Calls `broadcast_campaign()` to send fresh copy
6. Records all new message_ids in `send_analytics`
7. Replies: "✅ Promo cycle complete — 5 posts sent, {N} old messages swept"

**Also add `/sweep`** — standalone command to delete all tracked messages for a campaign without generating/broadcasting.

## Task 5 — xBridge-Specific Campaign Prompts
**Files:** `campaign_protocol.py`

**New phase:**
```python
"xbridge_promo": CampaignPhase(
    name="xBridge Promo Pack",
    objective="Promote xBridge MCP on Telegram",
    prompt_template="""You are promoting xBridge MCP — an open-source tool that bridges xAI's Grok API into Claude Code via the Model Context Protocol (MCP).

Real features (ONLY use these, do NOT invent):
- 19+ tools: web search, X/Twitter search, image/video generation, research chains, persistent sessions
- Powered by Grok models (grok-4.20, grok-4, grok-4-1-fast, etc.)
- Zero telemetry, privacy-focused, BYOK (bring your own xAI key)
- MIT licensed, self-hostable via pip or Docker
- Works on Linux, macOS, Windows
- Free tier available (limited calls) or low-cost Pro
- $XBRDG token as optional community loyalty perk

CRITICAL RULES:
- Do NOT invent statistics, user counts, testimonials, or "thousands of users"
- Do NOT claim features that aren't listed above
- Keep it technical but approachable — developers are the audience

Create 5 ready-to-post Telegram messages. Each must have:
- Sharp hook (first line, max 10 words)
- Body (2-4 lines, plain language)
- Clear call to action (last line — e.g. "pip install xbridge-mcp")
Vary the angle. Keep each under 280 words. Separate with ---

Topic: {topic}
Tone: {tone}
""",
)
```

## Task 6 — Dashboard Promo Controls
**Files:** `templates/campaign_detail.html`, `dashboard.py`

- Add "Sweep & Resend" button on campaign detail page (POST to `/campaign/{id}/promo`)
- Add `POST /campaign/{id}/promo` route — runs sweep + generate + broadcast
- Add "Last Promo Cycle" info to campaign detail (messages sent, messages swept, timestamp)
- Dashboard stat card: "Promo Cycles Run"

## Task 7 — CodeRabbit Setup
- Install [CodeRabbit GitHub App](https://github.com/apps/coderabbit) on repo `hrco/telegram-ollama-campaign`
- Create `.coderabbit.yaml` at repo root:
```yaml
reviews:
  auto_review: true
  path_filters:
    - "!*.md"
    - "!*.html"
    - "!docs/**"
  max_issues: 10
  tools:
    shellcheck: true
chat:
  auto_reply: true
```
- Create GitHub branch protection rule for `master`: require PR review, dismiss stale reviews
- Create PR from `promo/xbridge` → `master` for CodeRabbit to review

## Task 8 — Live Smoke Test
```bash
source .venv/bin/activate
# Ensure Ollama is running with llama3.1:8b
python main.py
```
1. Open dashboard at `http://localhost:8001` → login
2. Create "xBridge MCP" campaign
3. `/social` in Telegram → verify copy generated
4. Add a test channel via dashboard
5. `/promo` in Telegram → verify sweep + generate + broadcast
6. Check `send_analytics` rows in DB
7. Schedule recurring promo (Mon/Thu 10am UTC) via dashboard
8. `pytest -q` — confirm 19/19 green

---

# HANDOFF — Fresh Session Start

**Project:** `/home/supremeleader/mylab/telegram-ollama-campaign`
**Branch to create:** `promo/xbridge` from `master`
**Goal:** Run promotional campaign for xBridge MCP on Telegram using CampaignOS

## Current state
- CampaignOS v2 is built and tested (19/19 green)
- Working tree has uncommitted in-flight work (llm.py, settings.html, launch-copy.md)
- The app runs: `python main.py` starts bot + dashboard + scheduler

## What needs doing (in order)
1. **Commit in-flight work** to new `promo/xbridge` branch — see Task 1 above
2. **Fix message tracking** in broadcaster to return all split message IDs — see Task 2
3. **Add `sweep_channel_messages()`** to broadcaster — see Task 3
4. **Add `/promo` command** to bot — see Task 4
5. **Add xBridge-tuned prompts** to campaign_protocol — see Task 5
6. **Add dashboard promo controls** — see Task 6
7. **Set up CodeRabbit** — see Task 7
8. **Smoke test** full cycle — see Task 8

## Suggested skills
- `tdd` — run red-green-refactor for each feature
- `agent-manager` — if you want to parallelize (e.g. backend vs frontend)
- `firecrawl-scrape` — if you need to re-verify xBridge features from xbridgemcp.com

## Key design decisions (from user)
- Full sweep — delete ALL previous promo messages from channel before each new cycle
- Generate copy via Ollama each cycle (not pre-written)
- Use xAI/Grok as optional provider (already wired in llm.py)
- CodeRabbit auto-reviews all PRs

## Known constraints
- Single admin, dashboard hardcodes `user_id=1`
- APScheduler is in-memory (restart reconciliation works)
- Never commit `.env` — verify `.gitignore` before `git add`
- Run from venv: `source .venv/bin/activate`
- Dashboard port is 8001 (`DASHBOARD_PORT` in `.env`)
- Bot handle: `@campaignos_bot` (id 8976060475)
