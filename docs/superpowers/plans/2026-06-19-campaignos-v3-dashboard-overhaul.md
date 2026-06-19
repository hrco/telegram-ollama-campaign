# CampaignOS v3 — Dashboard Overhaul & Agentic Tools

**Date:** 2026-06-19
**Source:** Grok 4.3 consultation via xbridge
**Priority:** After P0.6 smoke test is done

---

## What This Unlocks

CampaignOS currently has bare-minimum CRUD screens. v3 makes it a real
marketing OS — viral campaign mechanics, a scheduler dashboard that doesn't
embarrass you, an AI agent interface, and a nav that scales to 10+ pages.

---

## Architecture Principles

1. **Single source of truth** — Every page reads from the same REST API the
   agent tools use. No admin-only magic routes.
2. **AI-native** — Every endpoint has a tool definition (name, description,
   input schema) that the `/agent` page auto-discovers.
3. **Telegraphic UI** — Dense, data-rich screens. No 3-click drills for common
   actions. Modal overlays, not page navigations.
4. **Growth layout** — Sidebar nav, not hamburger menu. New pages slot in
   without breaking hierarchy.

---

## Pages & Nav

```
┌──────────────────────────────────────────────────────────┐
│ 🔥 CampaignOS    🔍 Search    [UTC+2]  🟢 Ollama  👤   │  ← sticky header
├──────────┬───────────────────────────────────────────────┤
│          │                                                │
│ 📊 Dash  │  [page content area — template per page]      │
│ 📣 Camps │                                                │
│ 📺 Chans │                                                │
│ 📅 Sched │                                                │
│ 📈 Anal  │                                                │
│ 🤖 Agent │                                                │
│ ⚙️ Sett  │                                                │
│          │                                                │
└──────────┴────────────────────────────────────────────────┘
```

7 top-level pages. Sidebar collapses to icon-only on <1024px.

---

## Task Breakdown

### Task 1 — Nav + Base Layout Refresh

**Files:** `templates/base.html`, `static/css/`

- Convert base.html from top-nav to sidebar layout
- Sticky header bar with search, timezone, provider status, avatar
- Sidebar: 7 items, active state, collapsible
- Page title + contextual action buttons below header
- Responsive breakpoint at 1024px (sidebar collapses)

### Task 2 — Campaigns Overhaul (with Viral Settings)

**Files:** `templates/campaigns.html`, `templates/campaign_detail.html`,
`dashboard.py`, `database.py`

- Campaign list: inline status badges, quick-actions (duplicate, archive)
- Campaign detail tabs: Overview | Messages | Viral Settings | A/B Variants
- **Viral settings sub-object** on `campaigns` table:
  - `viral_config` JSON column: `{referral, viral_coefficient, growth_loops,
     milestone_triggers, audience_seeding, ab_variants, share_incentive,
     viral_decay_hours}`
- A/B variant creation form (inline, no page reload)
- New endpoints:
  - `GET /campaigns` — pagination, status filter, sort
  - `PATCH /campaigns/{id}/viral`
  - `POST /campaigns/{id}/variants`

### Task 3 — Channels Detail Page

**Files:** `templates/channels.html`, `dashboard.py`, `database.py`

- Channel list: connection status indicator, throttle profile badge
- Channel detail: name, chat_id, connected_at, throttle profile selector,
  delivery windows editor
- Delivery windows: array of `{start, end, tz}` per channel
- Throttle profiles: named presets (`default`, `aggressive`, `conservative`)
- New endpoints:
  - `PATCH /channels/{id}/throttle`
  - `POST /channels/{id}/windows`

### Task 4 — Schedule Dashboard

**Files:** `templates/schedule.html`, `templates/schedule_calendar.html`,
`dashboard.py`, `scheduler.py`

- Two views toggle: **Queue** (table) | **Calendar** (month grid)
- Queue table: campaign, channel, scheduled_at, status, retry_count,
  conflict badge, actions (reschedule, cancel, force-send)
- Calendar view: month grid with dots per day, click to see day list
- Batch scheduler: multi-select messages → offset-minutes form → submit
- Flood control profiles: stored in DB, referenced by schedule items
- Send-order randomization: `jitter_seconds` per item, toggle on/off
- Conflict detection: highlight overlapping sends on same channel in red
- New endpoints:
  - `GET /schedule/queue` — channel, date range, status filters
  - `POST /schedule/batch`
  - `PATCH /schedule/items/{id}`
  - `GET /schedule/calendar` — returns day-by-day counts

### Task 5 — Analytics Page

**Files:** `templates/analytics.html`, `dashboard.py`, `database.py`

- Stat cards: campaigns active, posts scheduled, posts sent, channels,
  viral coefficient (avg)
- Delivery timeline chart (last 14 days, bar chart — inline SVG, no lib)
- Campaign breakdown table: name, sent, opened (n/a for now), clicked (n/a),
  viral_k, status
- Period selector: 7d, 30d, 90d, custom range
- New endpoint:
  - `GET /analytics/delivery` — grouped by day, campaign_id filter
  - `GET /analytics/viral` — campaign-level viral coefficient breakdown

### Task 6 — Agent Tools Page (AI Interface)

**Files:** `templates/agent.html`, `agent.py` (NEW), `dashboard.py`

- Split-pane layout: chat input + history on left, tool call results on right
- Tool definitions auto-discovered from a `TOOL_REGISTRY` dict in `agent.py`
- Each tool: name, description, input_schema (JSON Schema), handler function
- Implement the 5 tools from Grok's design:
  1. `schedule_post_best_time`
  2. `find_underperforming_campaigns`
  3. `optimize_send_times`
  4. `suggest_ab_variants`
  5. `generate_content_batch`
- Agent calls: user types prompt → LLM decides tool + args → executes →
  renders result in right pane
- All tool calls logged in a `tool_executions` table for audit
- New endpoints:
  - `GET /agent/tools` — list available tools
  - `POST /agent/execute` — execute tool by name with args
  - `POST /agent/chat` — NL prompt → tool call → result loop

### Task 7 — Settings Page Expansion

**Files:** `templates/settings.html`, `dashboard.py`, `database.py`

- New sections (tabs or accordion):
  - **Provider**: Ollama URL, model, timeout; Telegram API config
  - **Notifications**: webhook URL, events to notify on
  - **Channel Defaults**: default throttle profile, timezone, parse mode
  - **Retry**: max attempts, backoff strategy, base delay
  - **Rate Limits**: named profiles with global_rpm, per_chat_rpm
  - **Integrations**: webhook URLs, export format, external API keys
- New endpoints:
  - `GET /settings/{section}` — returns section config
  - `PATCH /settings/{section}` — updates section config

### Task 8 — REST API Layer

**Files:** `api.py` (NEW — mounted as sub-app in `main.py`)

All endpoints return JSON. Auth via same JWT cookie + `Authorization: Bearer`
header (for agent tools).

| Resource | Endpoints |
|----------|-----------|
| Campaigns | `GET/POST /api/campaigns`, `GET/PATCH/DELETE /api/campaigns/{id}` |
| Viral | `PATCH /api/campaigns/{id}/viral` |
| Variants | `POST /api/campaigns/{id}/variants` |
| Schedule Queue | `GET /api/schedule/queue`, `PATCH/DELETE /api/schedule/items/{id}` |
| Schedule Calendar | `GET /api/schedule/calendar` |
| Channels | `GET /api/channels`, `PATCH /api/channels/{id}` |
| Delivery Windows | `POST/PATCH/DELETE /api/channels/{id}/windows/{window_id}` |
| Analytics | `GET /api/analytics/delivery`, `GET /api/analytics/viral` |
| Agent Tools | `GET /api/agent/tools`, `POST /api/agent/execute`, `POST /api/agent/chat` |
| Settings | `GET/PATCH /api/settings/{section}` |

### Task 9 — Tool Definitions for AI Agents

Every resource endpoint gets a companion tool registration in `agent.py`:

```python
TOOL_REGISTRY = {
    "schedule_post_best_time": {
        "description": "Schedule a message in optimal delivery window",
        "input_schema": { ... },
        "handler": handle_schedule_best_time,
    },
    # ... 15+ tools total
}
```

Tools are callable from:
1. The Agent page (chat interface)
2. External AI agents via `POST /api/agent/execute`
3. The bot (`/agent` command — future)

---

## Migration Path

This is a big overhaul. Ship incrementally:

1. **Week 1:** Nav + Base layout (Task 1) | Campaign viral settings (Task 2)
2. **Week 2:** Channels detail + Schedule dashboard (Tasks 3-4)
3. **Week 3:** Analytics + Settings expansion (Tasks 5, 7)
4. **Week 4:** API layer + Agent tools (Tasks 6, 8-9)

Each week = 1 PR, tested, green, merged.

## Pre-flight Check

Before starting Task 1:
- [ ] Confirm P0.6 smoke test passes (bot → schedule → broadcast works)
- [ ] Decide: new DB tables or JSON columns for viral config / delivery windows?
      (Recommendation: JSON columns — no migration pain, single-admin scale)
- [ ] Pick frontend strategy: keep Alpine.js (+ hyperscript for agent chat)
      or add a lightweight reactive lib? (Recommendation: Alpine alone is fine)
