# CampaignOS — Handoff for Hermes & grok CLI

> **Who this is for:** Hermes (orchestrator) and grok CLI / Claude Code workers continuing
> development of CampaignOS so we can start **promoting** it ASAP.
> **Read this first**, then the plan at `docs/superpowers/plans/2026-06-10-campaignos-v2.md`
> and the spec at `docs/superpowers/specs/2026-06-10-campaignos-v2-design.md`.

---

## TL;DR — where we actually are

The v2 **backend modules are built and green**: `auth.py`, `broadcaster.py`, `scheduler.py`,
and the extended `database.py` schema (channels / scheduled_posts / send_analytics) all exist
and **16/16 tests pass** (`pytest -q`). Commits land cleanly on `master`.

**But the app does not work end-to-end yet.** Several features the bot advertises have no
handler, the dashboard crashes on the campaign routes, nothing can actually be scheduled or
broadcast from the UI, and the polished mobile UI from Task 8 was never built. **None of the
"promote it" path works yet** — you can't currently: log into a styled dashboard → generate
social copy → schedule it → have it broadcast to a Telegram channel.

Fix the blockers in **Priority 0** and we have a demoable, promotable product.

---

## Operating rules (do not skip)

- **You work under** `42p/legal/42p-AGENT-OPERATING-CONTRACT.md`. Three hard red lines only:
  **no real spend · no publishing to live/public · no secrets in context or commits.**
  Default to action in a branch/worktree; ask only at a red line or when genuinely stuck.
- **TDD.** This repo has a test suite. Failing test first → minimal code → green → commit.
  Each plan task already gives you the tests to write first — use them.
- **One logical change per commit.** `feat:` / `fix:` / `test:` / `docs:`. Sign with the
  SpectreHawk soul line (see existing commits), not corporate boilerplate.
- **Never commit `.env`.** It exists locally and holds a real bot token — verify `.gitignore`
  covers it before every `git add`. `.env.example` is the only env file that gets committed.
- **Run the full suite before each commit:** `source .venv/bin/activate && pytest -q`.

---

## Priority 0 — make it run end-to-end (BLOCKERS for promo)

These are real bugs / missing wiring found by reading the code on 2026-06-11. Do these first.

### P0.1 — `dashboard.py` crashes on campaign routes (missing imports)
`dashboard.py` calls `create_campaign`, `save_message`, and `get_current_campaign` in the
`/campaign/new` and `/campaign/{id}/continue` handlers, but **never imports them** — these
routes 500 with `NameError` the moment they're hit.
- Add them to the `from database import (...)` block at the top of `dashboard.py`.
- Then actually exercise the routes (see P0.6) — don't trust the import fix alone.

### P0.2 — Bot advertises `/social` and `/channels` but has no handlers
`bot.py`'s `/start` and `/help` text list `/social` and `/channels`, but **no handler exists**
for either (only start/help/new/campaigns/resume are wired). The `social_copy` phase *is*
defined in `campaign_protocol.py`, so the prompt is ready — just the command is missing.
- Implement both per **plan Task 5.2 and 5.5** (`/social` runs the `social_copy` phase via
  Ollama and saves the message; `/channels` lists `list_channels()`).

### P0.3 — No GET route for campaign detail
`templates/campaign_detail.html` exists but **nothing serves it** — there is no
`@app.get("/campaign/{campaign_id}")` route, so every "open campaign" link 404s.
- Add the GET route: load the campaign + its messages (`get_campaign_messages`) and render
  `campaign_detail.html`. This is the screen where a user reads research/content/social output.

### P0.4 — Cannot schedule or broadcast from the UI (core value prop is missing)
There is a `GET /schedule` page but **no `POST /schedule/new` and no `POST /schedule/{id}/cancel`**,
and the dashboard never touches the scheduler. So scheduled posts can't be created, and the
broadcaster is never invoked from the product — only from tests.
- Implement **plan Task 7.2** (`/schedule/new` + `/schedule/{post_id}/cancel`, wiring into
  `scheduler.campaign_scheduler`).
- The `campaign_detail` screen needs a "Schedule this post" form (channel picker + datetime)
  that POSTs to `/schedule/new`. Without this there is no path from generated copy → channel.

### P0.5 — `main.py` startup is fragile / double-inits, scheduler not bound to the bot
`main.py` runs the bot polling loop and the dashboard concurrently, but:
- `init_db()` runs in both `main()` and the dashboard's own `@app.on_event("startup")`.
- `dashboard.py` still uses the deprecated `@app.on_event("startup")` instead of the lifespan
  pattern `main.py` already defines.
- `init_scheduler(bot)` is called but `start_scheduler()` is **not** called in the
  `asyncio.gather` path (only in the unused FastAPI `lifespan`), so the scheduler never starts
  when you run `python main.py`. **Scheduled posts will silently never fire.**
- **Also:** APScheduler jobs live in memory only. On restart, pending posts in the DB are **not**
  re-registered with the scheduler. Add a startup reconciler that loads
  `list_scheduled_posts(status="pending")` and re-schedules each one.
- Pick ONE startup path and make it correct: DB init once, scheduler started once and bound to
  the live `bot`, pending posts reconciled. Add a smoke test that starts main, hits `/login`,
  and confirms the scheduler is `running`.

### P0.6 — Manual end-to-end smoke before declaring P0 done
With Ollama running locally and a real channel the bot is admin of:
1. `python main.py` → open `http://localhost:8000` → redirected to `/login` → sign in.
2. Create a campaign → research renders → open its detail page (P0.3).
3. `/social` in Telegram → copy generated and saved.
4. Add a channel in the dashboard → schedule a post 2 min out → confirm it broadcasts.
5. Confirm `send_analytics` row written and `/schedule` shows it as `sent`.
Capture this as a short checklist in the PR description (evidence, not assertions).

---

## Priority 1 — make it look promotable (Task 8 UI)

The whole point of "promote ASAP" is screenshots/video that don't look like a toy.
**Plan Task 8 (mobile-first UI) was never built:**
- `templates/base.html` **does not exist**; no template `extends` it. Each page is standalone.
- Build `base.html` (Tailwind + Alpine via local `/static` assets, desktop sidebar + mobile
  bottom nav) exactly as in plan Task 8.1, then convert `dashboard.html`, `campaigns.html`,
  `campaign_detail.html`, `channels.html`, `schedule.html` to `{% extends "base.html" %}`.
- **Asset note:** templates reference `/static/tailwind.min.js` and `/static/alpine.min.js`.
  Confirm those files exist under `static/` (the dir is auto-created but may be empty). If
  missing, vendor them locally — do **not** rely on a CDN at demo time.
- Optional but high-leverage for promo: a public-facing landing/hero on `/` *before* login, or
  a short Loom-style walkthrough. Consider the `frontend-design` and `landing-page-marketer`
  skills here.

---

## Priority 2 — polish & hardening (after it demos)

- **`datetime.utcnow()` deprecation** throughout `database.py` (lines ~97, ~158, ~275) — swap to
  `datetime.now(timezone.utc)`. Tests warn 16×; harmless now, breaks on a future Python.
- **Real user mapping.** Dashboard hardcodes `user_id=1` everywhere (`# TODO: map username to
  user_id`). Fine for single-admin demo; note it as a known limitation, don't pretend it's done.
- **Password storage.** `auth.check_credentials` compares the plaintext `ADMIN_PASSWORD` from
  env. Acceptable for self-hosted single admin; if we ever promote multi-user, move to hashed
  creds (the `get_password_hash`/`verify_password` helpers already exist).
- **Scheduler persistence** — if reconciliation (P0.5) proves flaky, consider APScheduler's
  SQLAlchemy jobstore against the same SQLite file instead of hand-rolled reconcile.
- **README/Makefile drift.** README says `make dashboard` and `make run`; the Makefile target is
  `make interface` (pointing at the old `interface.py`, not `dashboard.py`/`main.py`). Update
  Makefile + README to the real v2 entrypoint (`python main.py`) so first-run users don't bounce.

---

## Priority 3 — promotion prep (parallel track, no code dependency)

Can run alongside P0/P1 since it doesn't touch the runtime:
- One-paragraph positioning + 5 launch posts (use the product's own `social_copy` phase dog-food
  it — generate CampaignOS's launch copy *with* CampaignOS, that's the story).
- Target channels: r/selfhosted, Hacker News "Show HN", relevant Telegram/Indie communities.
- Screenshots/GIF from the P1 UI. **Do not post anything live until a human gives the go** —
  publishing to public is a red line for agents.

---

## Suggested division of labor

- **Worker A (backend):** P0.1 → P0.2 → P0.3 → P0.4 → P0.5, TDD, one commit per item.
- **Worker B (frontend):** P1 — can start on `base.html` + asset vendoring immediately; it only
  depends on routes existing, and the routes A is adding are small. Coordinate on the
  `campaign_detail` "schedule" form (A owns the route, B owns the markup).
- **Hermes:** sequence A's P0 items (they're mostly independent except P0.4 wants P0.3's detail
  page), run the P0.6 smoke once both land, then green-light P1 polish and P3 copy.
- These split cleanly across worktrees — see `superpowers:using-git-worktrees` /
  `superpowers:dispatching-parallel-agents`.

## Definition of done for "promotable"
Fresh clone → `make setup` → `.env` filled → `python main.py` → a non-technical person can log
in, generate a campaign + social copy, connect a channel, schedule a post, and watch it
broadcast — on a UI that looks intentional in a screenshot. Full suite green. No secrets in git.
