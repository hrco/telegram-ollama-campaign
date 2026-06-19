# CampaignOS — Handoff for Hermes & grok CLI

> **Who this is for:** Hermes (orchestrator) and grok CLI / Claude Code workers continuing
> development of CampaignOS so we can start **promoting** it ASAP.
> **Read this first**, then the plan at `docs/superpowers/plans/2026-06-10-campaignos-v2.md`
> and the spec at `docs/superpowers/specs/2026-06-10-campaignos-v2-design.md`.

---

## TL;DR — where we actually are

**(Updated 2026-06-19.)** All v2 features are shipped, merged, and running:

- Bot (@campaignos_bot, id 8976060475) — locked to admin only via `ADMIN_TELEGRAM_ID`
- Dashboard on port 8001 — JWT auth, settings (password/LLM/timezone), campaign CRUD, channel management, scheduling, broadcasting
- LLM provider abstraction: Ollama (default, local) / xAI (optional, paid)
- 22/22 tests passing, all code review issues resolved
- CodeRabbit reviews addressed (F.text guards, provider validation, auth hash logic, etc.)
- Admin-only lock, launch copy kit, PRs #1-#4 merged

**Running now** with `OLLAMA_MODEL=phi3:mini` on this box (dashboard:8001).

---

## STATUS 2026-06-19 — what's next

### Pre-flight (blocker before v3)
- [ ] **P0.6 smoke test** — confirm bot → schedule → broadcast works end-to-end with a real Telegram channel the bot admins
- [ ] **Token rotation** — bot token was leaked and scrubbed from git history; rotate via BotFather, update `.env`, restart

### Grok 4.3 audit (see docs/superpowers/summary/2026-06-19-status-and-grok-audit.md)

**Top 5 features CampaignOS is missing to be a real "marketing OS":**
1. Attribution & funnel analytics (click tracking, conversion events, per-campaign ROI)
2. Audience segmentation (engaged vs silent, exclusion lists)
3. Content approval workflow (human-in-the-loop before broadcast)
4. Compliance/spam risk tooling (rate limiting, duplicate detection)
5. Export + CRM handoff (CSV + webhook)

**One differentiator:** Local private campaign memory — semantic search over every sent message + performance data.

---

## v3 Roadmap — Dashboard Overhaul & Agentic Tools

> Full plan: `docs/superpowers/plans/2026-06-19-campaignos-v3-dashboard-overhaul.md`
> Designed with Grok 4.3 consultation via xbridge

### Task 1 — Nav + Base Layout Refresh

**Files:** `templates/base.html`, `static/css/`

Sidebar layout (7 pages: Dashboard, Campaigns, Channels, Schedule, Analytics, Agent, Settings). Sticky header bar with search, timezone selector, provider status. Responsive collapse at 1024px. Supersedes the old "Priority 1" mobile-first section.

### Task 2 — Campaigns Overhaul (Viral Settings)

**Files:** `templates/campaigns.html`, `campaign_detail.html`, `dashboard.py`, `database.py`

Add viral config as JSON column: referral mechanics, k-factor targets, growth loops, milestone triggers, A/B variants. Campaign detail gets tabs: Overview → Messages → Viral → A/B Variants.

**Endpoints:** `GET/POST /campaigns` (paginated), `PATCH /campaigns/{id}/viral`, `POST /campaigns/{id}/variants`

### Task 3 — Channels Detail Page

**Files:** `templates/channels.html`, `dashboard.py`, `database.py`

Throttle profiles (aggressive/conservative/default), delivery windows per channel (timezone-aware). Channel detail view with connection status, profile selector, window editor.

**Endpoints:** `PATCH /channels/{id}/throttle`, `POST /channels/{id}/windows`

### Task 4 — Schedule Dashboard

**Files:** `templates/schedule.html`, `schedule_calendar.html`, `dashboard.py`, `scheduler.py`

Queue table + month calendar view toggle. Batch scheduler (multi-select → offset-minutes). Flood control profiles, send-order randomization (jitter_seconds), conflict detection (red highlight overlapping sends).

**Endpoints:** `GET /schedule/queue` (filtered), `POST /schedule/batch`, `PATCH /schedule/items/{id}`, `GET /schedule/calendar`

### Task 5 — Analytics Page

**Files:** `templates/analytics.html` (NEW), `dashboard.py`, `database.py`

Stat cards, delivery timeline chart (inline SVG, no lib), campaign breakdown table, period selector (7d/30d/90d/custom).

**Endpoints:** `GET /analytics/delivery`, `GET /analytics/viral`

### Task 6 — Agent Tools Page (AI Interface)

**Files:** `templates/agent.html` (NEW), `agent.py` (NEW), `dashboard.py`

Split-pane: chat input + history on left, tool call results on right. Tool registry auto-discovered from `TOOL_REGISTRY` dict in `agent.py`. Initial 5 tools:

| Tool | Description |
|------|-------------|
| `schedule_post_best_time` | Schedule message in optimal delivery window |
| `find_underperforming_campaigns` | Find campaigns below target viral coefficient |
| `optimize_send_times` | Analyze history, update delivery windows |
| `suggest_ab_variants` | Generate 2-3 A/B variants via local Ollama |
| `generate_content_batch` | Create N message variations |

All tool calls logged in `tool_executions` table.

**Endpoints:** `GET /agent/tools`, `POST /agent/execute`, `POST /agent/chat`

### Task 7 — Settings Expansion

**Files:** `templates/settings.html`, `dashboard.py`, `database.py`

6 accordion sections: Provider, Notifications, Channel Defaults, Retry Policies, Rate Limit Profiles, Integrations.

**Endpoints:** `GET/PATCH /settings/{section}`

### Task 8 — REST API Layer

**Files:** `api.py` (NEW, mounted as sub-app in `main.py`)

JSON endpoints for every resource. JWT cookie + Bearer token auth. Pagination/filtering/sorting on list endpoints.

### Task 9 — Tool Definitions for External AI Agents

**Files:** `agent.py`

15+ tool definitions with JSON Schema input specs. Callable from agent page, external agents via `/api/agent/execute`, and from the bot (future `/agent` command).

---

### Migration Schedule

| Week | Tasks |
|------|-------|
| 1 | Nav + layout (Task 1), Campaign viral settings (Task 2) |
| 2 | Channels detail (Task 3), Schedule dashboard (Task 4) |
| 3 | Analytics (Task 5), Settings expansion (Task 7) |
| 4 | API layer (Task 8), Agent tools + tool registry (Tasks 6, 9) |

Each week = 1 PR, tested, green, merged.

---

## Suggested division of labor

- **Worker A (backend):** Tasks 2-5 (campaign viral, channels, schedule, analytics) + Task 8 (API layer). Builds the data model and endpoints.
- **Worker B (frontend):** Task 1 (nav layout) + Tasks 2-5 templates. Aligns with A on the endpoint contracts.
- **Worker C (agent):** Tasks 6, 9 (agent page + tool registry). Depends on Task 8 for the API.
- **Hermes:** Coordinates the endpoint contracts (they're all standard REST, no surprises), runs P0.6 smoke before week 1.

## Definition of done

Fresh clone → `make setup` → `.env` filled → `python main.py` → user can log in, see the sidebar nav, create a campaign with viral settings, view the schedule calendar, check analytics, talk to the agent, and configure everything from settings. Full suite green. No secrets in git.
