# CampaignOS — Full Status & Grok 4.3 Audit

**Date:** 2026-06-19
**Source:** xbridge Grok 4.3 consultation + codebase analysis

---

## Current State (reality-checked)

### What's shipped & working

- Bot (@campaignos_bot) locked to admin only (ADMIN_TELEGRAM_ID)
- Dashboard on port 8001 with login, settings (password/LLM/timezone tabs)
- Campaign phases: research → content → schedule → social_copy (LLM-generated)
- Channel management + scheduling (APScheduler one-shot + cron) + broadcasting (split/retry/flood)
- LLM provider abstraction: Ollama (default, local) / xAI (optional, paid)
- SQLite: 7 tables, all CRUD paths
- Tailwind + Alpine dark-theme dashboard, 8 templates
- 22 tests, 20 pass, 2 broken (test_llm_integration.py imports stale after refactor)

### What's broken

- `test_dashboard_create_campaign_calls_llm` — patches old import `dashboard.llm_generate_async`
- `test_dashboard_continue_campaign_calls_llm` — same
- Root: when `dashboard.py` switched from `from llm import generate_async as llm_generate` to `from llm import generate as llm_generate`, the test mock path wasn't updated

---

## Grok 4.3 Audit: What CampaignOS Actually Needs

### Top 5 Missing Features (prioritized)

| # | Feature | Why |
|---|---------|-----|
| 1 | **Attribution + funnel analytics** | `send_analytics` tracks delivery only. Need click tracking, conversion events, per-campaign ROI. Without this it's a fancy broadcaster. |
| 2 | **Audience segmentation** | Static channel lists. Need engaged vs silent, previous campaign responders, exclusion lists. |
| 3 | **Content approval workflow** | Human-in-the-loop before anything hits the wire. Review/approve/reject in dashboard. |
| 4 | **Compliance / spam risk tooling** | Rate limiting per channel, duplicate content detection, "this text flagged before" memory. Most self-hosted bots die here. |
| 5 | **Export + CRM handoff** | CSV export + webhook so CampaignOS isn't a data silo. |

### Weakest Architecture Points

1. **Analytics layer** — stores logs ("what we sent") vs events + outcomes ("what worked")
2. **Single process + SQLite** — will feel pain on locking/observability under concurrent campaigns

### One Differentiator That Matters

**Local private campaign memory** — semantic search over every sent message + performance data. "Never repeat these 3 Q3 angles that underperformed" without uploading data to a third-party API. Almost nobody else offers this.

---

## Proposed: `/brand` Command via xbridge

### What it generates

- **Logo concepts** — `grok-image-generate`, 6-9 variants across 3-4 style prompts
- **Color palette** — LLM chat (structured JSON: primary/secondary/accent/neutral/background)
- **Taglines** — 10 options from chat
- **Visual direction brief** — style, typography, imagery, mood

### FSM flow

```text
/brand → PARSING (extract name+industry+vibe) → TEXT_GEN (palette+taglines+brief)
→ IMAGE_GEN (6-9 logos in parallel batches) → ASSEMBLY (present brand kit)
→ DELIVERED → /refine "more minimalist" (grok-image-edit) or /more-logos
```

### Tool mapping

| Component | Tool | Params |
|-----------|------|--------|
| Brand strategy (voice, palette, taglines, brief) | Local LLM (ollama) — free | Structured JSON prompt |
| Logo generation | `grok-image-generate` | 9 images, 1:1, 3 batches of 3 |
| Logo refinement | `grok-image-edit` | Existing image + edit instruction |
| Text refinement | Grok 4.3 chat (when quality matters) | Cost: pennies per call |
| Inspiration research | `grok-web-search` / `grok-x-search` | Only for niche vibes |

### Why this is promotable

"No other Telegram marketing OS generates your brand kit inline. Type `/brand` → get 9 logos + a complete visual identity. All local except the image generation."

---

## @coderabbitai Question (PR #5)

> CampaignOS's v2 architecture uses a single SQLite file with APScheduler in one process. As we add funnel analytics, audience segmentation, and the `/brand` image-generation feature, what's the **minimum viable storage and concurrency upgrade** that avoids painful rewrites? Stay within SQLite family (e.g. WAL mode, aiosqlite connection pool)? Or jump to PostgreSQL now given these new features? Also: are there any TypeScript/import patterns in the Python test mocks that our agent keep tripping over?

## Recommended Storage Strategy (2026-06-19)

**Current decision: Stay on SQLite with hardening.**

### Immediate steps (no rewrite)
1. **Enable WAL mode** — `PRAGMA journal_mode=WAL;` on every connection. Allows concurrent reads + one writer without locking the entire DB.
2. **Set busy_timeout** — `PRAGMA busy_timeout=5000;` so writers wait up to 5s instead of failing immediately on contention.
3. **Single-writer queue** — Wrap all write operations in a single `asyncio.Lock` inside `database.py` so only one coroutine writes at a time. This is 5 lines of code and prevents the most common SQLite concurrency crash.

### Objective cutover triggers (migrate to PostgreSQL when ANY fires)
| Trigger | Threshold |
|---------|-----------|
| `database.lock` timeouts | >1 per week in production |
| Write latency P99 | >100ms sustained over 1h |
| Concurrent job count | >5 overlapping schedule jobs per minute |
| Dashboard query latency P95 | >500ms during broadcast |

Until a trigger fires, **do not migrate**. WAL + busy_timeout + asyncio.Lock will handle the v1 scale of a single-admin self-hosted instance. Migrate to PostgreSQL only when there is objective evidence of pain, not preemptively.
