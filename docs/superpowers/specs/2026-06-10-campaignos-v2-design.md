# CampaignOS v2 — Design Spec
**Date:** 2026-06-10  
**Author:** Claude (research + Grok-4.20-reasoning)  
**Implementer:** Hermes  
**Status:** Approved — ready for implementation plan

---

## 1. What We Have (v1 Baseline)

Existing `telegram-ollama-campaign/` project:

| File | What it does |
|------|-------------|
| `bot.py` | aiogram bot — `/new`, `/campaigns`, `/resume`, `/help` |
| `dashboard.py` | FastAPI — 4 routes, Jinja2 HTML templates, no auth |
| `database.py` | aiosqlite — `users`, `campaigns`, `messages` tables |
| `campaign_protocol.py` | 3 phases: research → content → schedule (prompt templates) |
| `templates/` | Basic unstyled HTML |
| `states.py` | aiogram FSM states |

**Critical gaps:** no auth, no real scheduler, no broadcaster, no mobile UI, no analytics, no channel management.

---

## 2. Goals for v2

Build CampaignOS into a **self-hosted marketing OS** that a solo creator or small agency can actually use daily. The north star: a beautiful mobile-friendly dashboard where you create AI-generated campaigns, schedule broadcasts to Telegram channels, and track results — all free, all local.

### Must-have (v2 scope)
1. **Auth** — dashboard protected by login (admin password, JWT cookie)
2. **Scheduler** — delayed and recurring sends using APScheduler
3. **Broadcaster** — send campaign content to Telegram channels the bot admins
4. **Mobile-first dashboard redesign** — Tailwind CDN + Alpine.js, no build step
5. **Analytics** — basic send/engagement tracking in DB + dashboard cards
6. **Campaign phase improvements** — add `social_copy` phase, better prompts

### Out of scope for v2
- Multi-user / team workspaces (single-admin is enough)
- Redis / Celery (APScheduler in-process handles this scale)
- Telegram Mini App
- Email / SMS channels
- Docker packaging (ship-it.md already handles systemd)

---

## 3. Architecture

```
┌─────────────────────────────────────────────────┐
│                   CampaignOS v2                  │
│                                                   │
│  ┌──────────────┐     ┌────────────────────────┐ │
│  │  Telegram Bot │     │   FastAPI Dashboard     │ │
│  │  (aiogram)   │     │   + Jinja2 + Tailwind   │ │
│  │              │     │   + Alpine.js            │ │
│  └──────┬───────┘     └──────────┬─────────────┘ │
│         │                        │                │
│         └──────────┬─────────────┘                │
│                    │                              │
│         ┌──────────▼──────────┐                  │
│         │   database.py       │                  │
│         │   aiosqlite / SQLite│                  │
│         │   5 tables          │                  │
│         └──────────┬──────────┘                  │
│                    │                              │
│         ┌──────────▼──────────┐                  │
│         │   scheduler.py      │                  │
│         │   APScheduler       │                  │
│         │   AsyncIOScheduler  │                  │
│         └──────────┬──────────┘                  │
│                    │                              │
│         ┌──────────▼──────────┐                  │
│         │   broadcaster.py    │                  │
│         │   aiogram Bot send  │                  │
│         │   rate-limited      │                  │
│         └─────────────────────┘                  │
└─────────────────────────────────────────────────┘
```

Both `bot.py` and `dashboard.py` run in the same process via `asyncio` — bot polls, dashboard serves HTTP. Single `asyncio` event loop, shared DB.

---

## 4. Database Schema (v2 additions)

Keep existing `users`, `campaigns`, `messages`. Add:

```sql
-- Channels the bot can send to
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL UNIQUE,   -- Telegram channel/group ID (e.g. -100123456789)
    name TEXT NOT NULL,
    added_at TEXT
);

-- Scheduled broadcast posts
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,       -- ISO8601 UTC
    recurring_cron TEXT,              -- NULL = one-shot, e.g. "0 9 * * 1" = every Mon 9am
    status TEXT DEFAULT 'pending',    -- pending | sent | failed | cancelled
    sent_at TEXT,
    error TEXT,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY(channel_id) REFERENCES channels(id)
);

-- Basic analytics per send
CREATE TABLE IF NOT EXISTS send_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheduled_post_id INTEGER NOT NULL,
    telegram_message_id INTEGER,
    sent_at TEXT,
    status TEXT,                      -- sent | failed
    FOREIGN KEY(scheduled_post_id) REFERENCES scheduled_posts(id)
);
```

---

## 5. Auth Layer

**Approach:** Single-admin JWT cookie auth. No user registration — credentials come from `.env`.

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme   # hashed with bcrypt on first run
SECRET_KEY=<random 32 bytes>
```

**Flow:**
1. All dashboard routes except `/login` redirect to `/login` if no valid JWT cookie
2. `POST /login` validates credentials → sets `campaignos_session` cookie (httponly, 24h expiry)
3. `GET /logout` clears cookie
4. JWT payload: `{"sub": "admin", "exp": <timestamp>}`

**Files added/modified:**
- `auth.py` — new: `create_token()`, `verify_token()`, `get_password_hash()`, `verify_password()`
- `dashboard.py` — add `Depends(require_auth)` to all routes, add `/login` + `/logout`
- `templates/login.html` — new login page

---

## 6. Scheduler

**Library:** `apscheduler[asyncio]` — AsyncIOScheduler with SQLAlchemy job store (SQLite, same DB).

**Module:** `scheduler.py`

```python
# Key functions
async def schedule_post(post_id: int, run_at: datetime) -> str
async def schedule_recurring(post_id: int, cron_expr: str) -> str
async def cancel_job(job_id: str) -> bool
async def get_upcoming_jobs(limit: int = 20) -> list
async def execute_post(post_id: int)   # actual send via broadcaster
```

**Startup:** Scheduler starts with the app in `lifespan` handler. On startup, it loads all `pending` scheduled_posts from DB and re-registers them (handles restarts).

**Cron format:** Standard 5-field cron (`min hour dom month dow`). Validate on input.

---

## 7. Broadcaster

**Module:** `broadcaster.py`

```python
async def send_to_channel(bot: Bot, chat_id: str, content: str) -> int  # returns message_id
async def send_with_retry(bot: Bot, chat_id: str, content: str, retries: int = 3) -> int
async def broadcast_campaign(bot: Bot, campaign_id: int, channel_ids: list[int]) -> list[dict]
```

**Rate limiting:**
- 1 message per channel per 3 seconds minimum (Telegram group/channel flood limit)
- On `TelegramRetryAfter` → wait `retry_after` seconds, then retry
- Max 3 retries per message, then mark as `failed`

**Content formatting:**
- Messages > 4096 chars split into parts
- Supports HTML parse mode (existing bot already uses HTML)

---

## 8. Campaign Protocol v2

Add one new phase to `campaign_protocol.py`:

```python
"social_copy": CampaignPhase(
    name="Social Copy Pack",
    objective="Generate ready-to-post variants for Telegram",
    prompt_template="""Based on the research and content:
Create 5 ready-to-post Telegram messages.
Each must have: hook (first line), body (2-4 lines), CTA (call to action).
Vary the angle for each. Keep each under 280 words.
Use plain language, no corporate speak.

Topic: {topic}
Tone: {tone}
"""
)
```

Bot gets `/social` command to trigger this phase on the current campaign.

---

## 9. Dashboard UI Redesign

**Stack:** Tailwind CSS v3 play CDN + Alpine.js v3, both vendored to `static/` by `make setup` (no CDN at runtime — avoids SRI/CDN-compromise risk). No build step. Jinja2 templates.

**Pages:**

### `/login`
- Centered card, brand mark, username + password fields, submit button
- Error flash on bad credentials

### `/` — Dashboard Home
- Top: stat cards (Total Campaigns, Posts Scheduled, Posts Sent, Channels Connected)
- Middle: "Upcoming Schedule" — next 5 scheduled posts as a list
- Bottom: "Recent Campaigns" — last 5 with status badge

### `/campaigns` — Campaign List
- Filterable list (Alpine.js, no server round-trip): all / active / completed
- Each card: topic, created date, phase badges (Research ✓, Content ✓, Schedule ✓, Social ✓), action buttons
- FAB (floating action button) "New Campaign"

### `/campaign/{id}` — Campaign Detail
- Header: topic, status, created date
- Phase tabs: Research | Content | Schedule | Social Copy
- Active tab shows phase content (scrollable)
- "Run Phase" buttons for incomplete phases
- "Schedule a Post" section: pick channel, date/time, content picker

### `/channels` — Channel Manager
- List connected channels (name, chat_id, last post)
- "Add Channel" form: enter chat_id + verify (bot sends a test message)
- Remove channel

### `/schedule` — Schedule View
- Table: upcoming posts sorted by scheduled_at
- Columns: Date/Time, Campaign, Channel, Status, Actions (cancel)
- "Schedule New Post" modal

**Mobile-first rules:**
- All pages work at 375px width
- Nav: bottom tab bar on mobile, left sidebar on desktop
- No horizontal scroll
- Touch targets ≥ 44px

**Color scheme:** Dark background (#0f0f0f), accent electric blue (#3b82f6), cards on #1a1a1a. Clean, minimal, no gradients.

---

## 10. Bot Commands (v2)

| Command | Description |
|---------|-------------|
| `/start` | Welcome, show commands |
| `/new` | Start new campaign (existing flow) |
| `/campaigns` | List campaigns |
| `/resume` | Resume latest campaign |
| `/social` | Generate social copy for current campaign |
| `/schedule <channel> <datetime> <campaign_id>` | Schedule a post (power-user shortcut) |
| `/channels` | List connected channels |
| `/help` | Show help |

---

## 11. Requirements Changes

Add to `requirements.txt`:
```
apscheduler[asyncio]>=3.10
PyJWT>=2.8
bcrypt>=4.1
python-multipart>=0.0.9   # for form auth
```

---

## 12. File Map (v2)

```
telegram-ollama-campaign/
├── main.py                   # NEW — single entrypoint: runs bot + dashboard in same asyncio loop
├── bot.py                    # MODIFY — add /social, /schedule, /channels commands
├── dashboard.py              # MODIFY — add auth, channels, schedule routes
├── database.py               # MODIFY — add channels, scheduled_posts, send_analytics tables
├── campaign_protocol.py      # MODIFY — add social_copy phase
├── states.py                 # MODIFY — add scheduling FSM states
├── auth.py                   # NEW — JWT auth helpers
├── scheduler.py              # NEW — APScheduler wrapper
├── broadcaster.py            # NEW — Telegram channel sender
├── requirements.txt          # MODIFY — add apscheduler, PyJWT, bcrypt
├── templates/
│   ├── base.html             # NEW — shared layout (nav, sidebar, mobile tabs)
│   ├── login.html            # NEW
│   ├── dashboard.html        # REPLACE — stat cards, upcoming schedule
│   ├── campaigns.html        # REPLACE — filterable cards
│   ├── campaign_detail.html  # REPLACE — phase tabs, schedule section
│   ├── channels.html         # NEW — channel manager
│   └── schedule.html         # NEW — schedule view
├── static/
│   ├── tailwind.min.js     # Vendored by make setup (Tailwind 3.4.16 play CDN)
│   └── alpine.min.js       # Vendored by make setup (Alpine.js 3.14.9)
├── .env.example              # MODIFY — add ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY
├── Makefile                  # MODIFY — add `make all` (runs main.py — bot+dashboard together)
└── CLAUDE.md                 # NEW — project overview for agents
```

---

## 13. Non-Goals / Constraints

- **No Redis or Celery** — APScheduler in-process is sufficient for <100 scheduled posts
- **No user registration** — single admin, credentials from env
- **No Telegram User API (Telethon/Pyrogram)** — bot API only, no account scraping
- **No external AI** — Ollama only, free forever
- **No paid analytics APIs** — track what we send, not what Telegram tracks
- **Keep Python** — don't rewrite in Node.js; the AI stack (Ollama) is Python-native

---

## 14. Testing Approach

Hermes should write tests as files are created:

- `tests/test_auth.py` — token creation, verification, expiry
- `tests/test_scheduler.py` — schedule/cancel/reschedule, restart recovery
- `tests/test_broadcaster.py` — send, retry on flood, message splitting
- `tests/test_database.py` — new table CRUD operations
- `tests/test_campaign_protocol.py` — all 4 phases produce non-empty output

Use `pytest` + `pytest-asyncio`. Mock aiogram Bot for broadcaster tests.

---

## 15. Success Criteria

CampaignOS v2 is done when:
- [ ] Dashboard requires login — unauthenticated requests redirect to `/login`
- [ ] Can add a Telegram channel and see it listed in `/channels`
- [ ] Can schedule a post from `/campaign/{id}` — it appears in `/schedule`
- [ ] APScheduler fires the send at the correct time and marks status `sent`
- [ ] Dashboard renders correctly on iPhone SE width (375px)
- [ ] All new modules have passing tests
- [ ] `make run` starts both bot and dashboard together
