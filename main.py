import os
import sys
import pathlib
import logging
import inspect
import traceback
from typing import Any, Dict, Optional
from google.adk.agents.llm_agent import LlmAgent as Agent
from google.genai import types
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search, AgentTool, ToolContext
from google.adk.code_executors import BuiltInCodeExecutor

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[0]
SRC_PATH = str(PROJECT_ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# FastAPI + Uvicorn
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    import uvicorn
    from fastapi.middleware.cors import CORSMiddleware
except Exception:
    FastAPI = None


build_router_agent = None
try:
    import src.router_agent as ra
    build_router_agent = getattr(ra, "build_router_agent", None)
except Exception:
    build_router_agent = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

class ChatRequest(BaseModel):
    message: str
    session: Optional[Dict[str, Any]] = None

if FastAPI is None:
    raise RuntimeError("FastAPI not installed. Please `pip install fastapi uvicorn pydantic`")

app = FastAPI(title="AI Service Desk Agent API", version="0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_INSTANCE = None

def _build_agent_safe():
    global AGENT_INSTANCE
    if AGENT_INSTANCE is not None:
        return AGENT_INSTANCE
    if build_router_agent is None:
        raise RuntimeError("router_agent.build_router_agent not found. Ensure router_agent.py is available.")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set. Agent may fail to initialize without API key.")
    try:
        AGENT_INSTANCE = build_router_agent()
        logger.info("Agent instance created successfully.")
    except Exception as exc:
        logger.exception("Failed to build agent instance: %s", exc)
        raise
    return AGENT_INSTANCE

@app.get("/health")
def health():
    return {"status": "ok", "agent_loaded": AGENT_INSTANCE is not None}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Chat endpoint."""
    try:
        agent_one = _build_agent_safe()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent init failed: {exc}")
    
    if not req.message.strip():
        return {"reply": "Please provide a message.", "tool": None, "result": None}
    
    try:
        runner_one = InMemoryRunner(agent=agent_one)
        resp = await runner_one.run_debug(req.message)
    except Exception as exc:
        logger.exception(f"Agent error: {exc}")
        raise HTTPException(status_code=500, detail=f"Agent failed: {exc}")

    reply = None
    tool = None
    result = None
    
    if isinstance(resp, dict):
        reply = resp.get("reply")
        tool = resp.get("tool")
        result = resp.get("result") or resp.get("ticket")
    else:
        if isinstance(resp, list) and resp:
            first_event = resp[0]
            try:
                reply = first_event.content.parts[0].text
            except AttributeError:
                reply = str(resp)
        else:
            reply = str(resp) if resp else "No reply"
    
    return {
        "reply": reply,
        "tool": tool,
        "result": result,
        "session": req.session or {}
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting server on 0.0.0.0:%d", port)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
