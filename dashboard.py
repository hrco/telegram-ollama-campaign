"""
CampaignOS Dashboard v2
With authentication, channels, scheduling, and stats
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os

from database import (
    init_db,
    list_user_campaigns,
    get_campaign_messages,
    get_dashboard_stats,
    list_channels,
    add_channel,
    remove_channel,
    list_scheduled_posts,
    create_scheduled_post,
    update_post_status,
    create_campaign,
    get_current_campaign,
    save_message,
)
from auth import (
    require_auth,
    check_credentials,
    create_token,
    NotAuthenticatedException,
    COOKIE_NAME,
)

import ollama
from campaign_protocol import get_phase_prompt

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensures tables exist when the dashboard is served standalone
    # (uvicorn dashboard:app). When launched via main.py, init runs there too;
    # init_db is idempotent (CREATE TABLE IF NOT EXISTS), so double-init is safe.
    await init_db()
    yield


app = FastAPI(title="CampaignOS v2", lifespan=lifespan)

templates = Jinja2Templates(directory="templates")
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


# ==================== AUTH ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if check_credentials(username, password):
        token = create_token(username)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(COOKIE_NAME, token, httponly=True, max_age=86400)
        return response
    return RedirectResponse("/login?error=1", status_code=302)


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ==================== PROTECTED ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(require_auth)):
    try:
        stats = await get_dashboard_stats()
    except Exception:
        stats = {"total_campaigns": 0, "posts_scheduled": 0, "posts_sent": 0, "channels_connected": 0}

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "title": "CampaignOS", "username": username, "stats": stats
    })


@app.get("/campaigns", response_class=HTMLResponse)
async def list_campaigns(request: Request, username: str = Depends(require_auth)):
    campaigns = await list_user_campaigns(1)
    return templates.TemplateResponse("campaigns.html", {
        "request": request, "campaigns": campaigns, "title": "My Campaigns", "username": username
    })


@app.post("/campaign/new")
async def create_new_campaign(topic: str = Form(...), username: str = Depends(require_auth)):
    campaign_id = await create_campaign(1, topic)
    
    prompt = get_phase_prompt("research", topic=topic, platform="multi")
    try:
        resp = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        content = resp["message"]["content"]
        await save_message(campaign_id, "assistant", content, phase="research")
    except Exception as e:
        await save_message(campaign_id, "assistant", f"Error: {str(e)}", phase="research")
    
    return RedirectResponse(f"/campaign/{campaign_id}", status_code=302)


@app.get("/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: int, username: str = Depends(require_auth)):
    messages = await get_campaign_messages(campaign_id, limit=50)
    channels = await list_channels()
    return templates.TemplateResponse("campaign_detail.html", {
        "request": request, "campaign_id": campaign_id, "messages": messages,
        "channels": channels, "title": f"Campaign #{campaign_id}", "username": username
    })


@app.post("/campaign/{campaign_id}/continue")
async def continue_campaign(campaign_id: int, phase: str = Form(...), username: str = Depends(require_auth)):
    campaign = await get_current_campaign(1)
    topic = campaign["topic"] if campaign else "Campaign"
    
    prompt = get_phase_prompt(phase, topic=topic, platform="multi")
    
    try:
        resp = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        content = resp["message"]["content"]
        await save_message(campaign_id, "assistant", content, phase=phase)
    except Exception as e:
        await save_message(campaign_id, "assistant", f"Error running phase: {str(e)}", phase=phase)
    
    return RedirectResponse(f"/campaign/{campaign_id}", status_code=302)


# ==================== CHANNELS ====================

@app.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request, username: str = Depends(require_auth)):
    channels = await list_channels()
    return templates.TemplateResponse("channels.html", {
        "request": request, "channels": channels, "title": "Channels", "username": username
    })


@app.post("/channels/add")
async def add_channel_route(chat_id: str = Form(...), name: str = Form(...), username: str = Depends(require_auth)):
    await add_channel(chat_id, name)
    return RedirectResponse("/channels", status_code=302)


@app.post("/channels/remove/{channel_id}")
async def remove_channel_route(channel_id: int, username: str = Depends(require_auth)):
    await remove_channel(channel_id)
    return RedirectResponse("/channels", status_code=302)


# ==================== SCHEDULE ====================

@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, username: str = Depends(require_auth)):
    posts = await list_scheduled_posts(status=None, limit=50)
    return templates.TemplateResponse("schedule.html", {
        "request": request, "posts": posts, "title": "Scheduled Posts", "username": username
    })


@app.post("/schedule/new")
async def create_schedule_post(
    campaign_id: int = Form(...),
    channel_id: int = Form(...),
    content: str = Form(...),
    scheduled_at: str = Form(...),  # ISO datetime from a datetime-local input
    recurring_cron: str = Form(""),
    username: str = Depends(require_auth),
):
    cron = recurring_cron.strip() or None
    post_id = await create_scheduled_post(
        campaign_id=campaign_id,
        channel_id=channel_id,
        content=content,
        scheduled_at=scheduled_at,
        recurring_cron=cron,
    )

    # Register with the live scheduler if one is running (it won't be under
    # `uvicorn dashboard:app` alone; main.py owns the scheduler). Startup
    # reconciliation re-registers any posts created while it was down.
    import scheduler as sched_module
    if sched_module.campaign_scheduler:
        if cron:
            sched_module.campaign_scheduler.schedule_recurring(post_id, cron)
        else:
            run_at = datetime.fromisoformat(scheduled_at)
            sched_module.campaign_scheduler.schedule_post(post_id, run_at)

    return RedirectResponse("/schedule", status_code=302)


@app.post("/schedule/{post_id}/cancel")
async def cancel_schedule_post(post_id: int, username: str = Depends(require_auth)):
    await update_post_status(post_id, "cancelled")
    import scheduler as sched_module
    if sched_module.campaign_scheduler:
        sched_module.campaign_scheduler.cancel_job(f"post_{post_id}")
        sched_module.campaign_scheduler.cancel_job(f"recurring_{post_id}")
    return RedirectResponse("/schedule", status_code=302)


@app.exception_handler(NotAuthenticatedException)
async def auth_exception_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse("/login", status_code=302)
