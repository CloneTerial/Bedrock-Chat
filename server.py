import asyncio
import os
import sys
import json
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Request, File, UploadFile, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from services.storage import (
    get_settings, put_settings, get_conv, put_conv, 
    del_conv, list_convs, CHATS_DIR, SETTINGS_FILE
)
from services.rag import index_files, UPLOAD_DIR
from providers import get_provider
from tools.browser import browser_mgr
from config import MODELS, DEFAULT_SYSTEM_PROMPT

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    yield
    browser_mgr.close_sync()

app = FastAPI(title="Bedrock Chat", lifespan=lifespan)

def sse(data: dict) -> str:
    """Format dictionary as Server-Sent Events (SSE) string."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

class ChatReq(BaseModel):
    """Schema for chat request parameters."""
    conversation_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools_enabled: Optional[bool] = None
    edit_index: Optional[int] = None

@app.get("/")
async def index():
    """Serve the main frontend application."""
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/health")
async def health():
    """Check API health and current server time."""
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/api/models")
async def api_models():
    """List available AI models and their configurations."""
    return MODELS

@app.get("/api/settings")
async def api_get_settings():
    """Retrieve current application settings."""
    s = get_settings()
    s["default_system_prompt"] = DEFAULT_SYSTEM_PROMPT
    return s

@app.post("/api/settings")
async def api_put_settings(request: Request):
    """Update application settings."""
    data = await request.json()
    s = get_settings()
    for k, v in data.items():
        if v is not None:
            s[k] = v
    put_settings(s)
    s["default_system_prompt"] = DEFAULT_SYSTEM_PROMPT
    return s

@app.get("/api/conversations")
async def api_list():
    """List all saved chat conversations."""
    return list_convs()

@app.get("/api/conversations/{cid}")
async def api_get(cid: str):
    """Retrieve details of a specific conversation."""
    c = get_conv(cid)
    if not c:
        raise HTTPException(404, "Conversation not found")
    return c

@app.post("/api/upload")
async def api_upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Upload files and trigger background indexing for RAG."""
    filenames = []
    for file in files:
        path = os.path.join(UPLOAD_DIR, file.filename)
        with open(path, "wb") as f:
            f.write(await file.read())
        filenames.append(file.filename)
    
    background_tasks.add_task(index_files, filenames)
    return {"filenames": filenames}

@app.delete("/api/conversations/{cid}")
async def api_del(cid: str):
    """Delete a specific conversation."""
    del_conv(cid)
    return {"ok": True}

@app.put("/api/conversations/{cid}")
async def api_upd(cid: str, request: Request):
    """Update conversation metadata like title."""
    data = await request.json()
    c = get_conv(cid)
    if not c:
        raise HTTPException(404, "Conversation not found")
    if "title" in data:
        c["title"] = data["title"]
    put_conv(c)
    return c

@app.post("/api/chat")
async def api_chat(req: ChatReq):
    """Main chat endpoint with SSE streaming and tool support."""
    stg = get_settings()
    model_id = req.model or stg["default_model"]
    mcfg = MODELS.get(model_id, {})
    
    extra_context = ""
    goal_file = "active_goal.json"
    if os.path.exists(goal_file):
        try:
            with open(goal_file, "r") as f:
                goal_data = json.load(f)
                extra_context = f"\n\n[RESUME NOTIFICATION]: You have just restarted because of a code change. Your current active goal is: {json.dumps(goal_data)}. Please verify if your previous change worked and continue the next step."
        except: pass

    sys_prompt = stg["system_prompt"].replace(
        "{current_date}", datetime.now().strftime("%Y-%m-%d")
    ) + extra_context
    
    use_tools = (
        (req.tools_enabled if req.tools_enabled is not None else stg.get("tools_enabled", True))
        and mcfg.get("supports_tools", False)
    )

    async def stream():
        conv = get_conv(req.conversation_id) if req.conversation_id else None
        
        if conv and req.edit_index is not None:
            conv["messages"] = conv["messages"][:req.edit_index]
        
        if not conv:
            title = req.message[:60].strip()
            if len(req.message) > 60:
                title += "…"
            conv = {
                "id": str(uuid.uuid4()),
                "title": title,
                "model": model_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "messages": [],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
            }

        conv["messages"].append({"role": "user", "content": [{"text": req.message}]})
        yield sse({"type": "conversation_id", "id": conv["id"]})

        provider = get_provider(mcfg)
        t_in = 0
        t_out = 0
        
        async for chunk in provider.stream_chat(req, conv, sys_prompt, mcfg, use_tools):
            try:
                data = json.loads(chunk.replace("data: ", "").strip())
                if data.get("type") == "usage":
                    t_in = data.get("input_tokens", 0)
                    t_out = data.get("output_tokens", 0)
                    continue 
            except: pass
            
            yield chunk

        ci = mcfg.get("input_cost_per_1k", 0)
        co = mcfg.get("output_cost_per_1k", 0)
        cost = round((t_in / 1000 * ci) + (t_out / 1000 * co), 8)

        conv["updated_at"] = datetime.now().isoformat()
        conv["total_input_tokens"] = conv.get("total_input_tokens", 0) + t_in
        conv["total_output_tokens"] = conv.get("total_output_tokens", 0) + t_out
        conv["total_cost"] = round(conv.get("total_cost", 0.0) + cost, 8)
        put_conv(conv)

        yield sse({
            "type": "metadata",
            "input_tokens": t_in,
            "output_tokens": t_out,
            "cost": cost,
            "total_input_tokens": conv["total_input_tokens"],
            "total_output_tokens": conv["total_output_tokens"],
            "total_cost": conv["total_cost"],
        })
        yield sse({"type": "done"})

    return StreamingResponse(stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")
