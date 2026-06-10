"""
CampaignOS Dashboard
Free, open-source campaign management tool for businesses & creators.
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from database import (
    init_db, get_or_create_user, create_campaign, get_current_campaign,
    save_message, get_campaign_messages, list_user_campaigns
)
import ollama
from campaign_protocol import get_phase_prompt

app = FastAPI(title="CampaignOS", description="Free campaign management for businesses")

# Templates
templates = Jinja2Templates(directory="templates")

# Create templates directory if it doesn't exist
os.makedirs("templates", exist_ok=True)

# Static files (for future CSS/JS)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard showing all campaigns"""
    # For now we show a general view. In real use, we'd filter by user.
    # This is a demo-friendly version.
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "CampaignOS"
    })


@app.get("/campaigns", response_class=HTMLResponse)
async def list_campaigns(request: Request, user_id: int = 1):
    """List campaigns for a user"""
    campaigns = await list_user_campaigns(user_id)
    return templates.TemplateResponse("campaigns.html", {
        "request": request,
        "campaigns": campaigns,
        "title": "My Campaigns"
    })


@app.get("/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: int):
    """Show detailed view of one campaign with phases"""
    messages = await get_campaign_messages(campaign_id, limit=50)
    return templates.TemplateResponse("campaign_detail.html", {
        "request": request,
        "campaign_id": campaign_id,
        "messages": messages,
        "title": f"Campaign #{campaign_id}"
    })


@app.post("/campaign/new")
async def create_new_campaign(topic: str = Form(...), user_id: int = Form(1)):
    """Create a new campaign from the web"""
    campaign_id = await create_campaign(user_id, topic)
    
    # Run first phase automatically
    prompt = get_phase_prompt("research", topic=topic, platform="multi")
    try:
        resp = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        content = resp['message']['content']
        await save_message(campaign_id, "assistant", content, "research")
    except Exception as e:
        await save_message(campaign_id, "assistant", f"Error: {str(e)}", "research")

    return RedirectResponse(f"/campaign/{campaign_id}", status_code=303)


@app.post("/campaign/{campaign_id}/continue")
async def continue_campaign(campaign_id: int, phase: str = Form(...)):
    """Continue to the next phase of a campaign"""
    # Get campaign topic
    # For simplicity we use the first message as topic
    messages = await get_campaign_messages(campaign_id, limit=5)
    topic = messages[0]['content'] if messages else "Unknown topic"

    prompt = get_phase_prompt(phase, topic=topic, platform="multi")
    
    try:
        resp = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        content = resp['message']['content']
        await save_message(campaign_id, "assistant", content, phase)
    except Exception as e:
        await save_message(campaign_id, "assistant", f"Error: {str(e)}", phase)

    return RedirectResponse(f"/campaign/{campaign_id}", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)