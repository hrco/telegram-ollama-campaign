"""
Simple FastAPI Interface for the Campaign Bot
Run with: uvicorn interface:app --reload
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import ollama

app = FastAPI(title="Ollama Campaign Interface")

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Campaign Protocol</title>
    <style>
        body { font-family: system-ui; background: #0a0a0c; color: #f4f4f5; padding: 40px; }
        .container { max-width: 720px; margin: 0 auto; }
        textarea { width: 100%; height: 120px; background: #111; color: white; border: 1px solid #333; }
        button { background: #3b82f6; color: white; border: none; padding: 12px 24px; border-radius: 8px; }
    </style>
</head>
<body>
<div class="container">
    <h1>Campaign Protocol</h1>
    <p>Local Ollama + Telegram Bot</p>
    
    <h3>Quick Research</h3>
    <form action="/research" method="post">
        <textarea name="topic" placeholder="Campaign topic..."></textarea><br><br>
        <button type="submit">Run Research Phase</button>
    </form>
</div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.post("/research")
async def research(topic: str):
    prompt = f"Research this topic deeply: {topic}"
    response = ollama.chat(model="llama3.1:8b", messages=[{"role": "user", "content": prompt}])
    return {"result": response['message']['content']}