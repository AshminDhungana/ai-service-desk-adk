import os
import sys
import pathlib
import logging
import inspect
from typing import Any, Dict, Optional


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
    try:
        import router_agent as ra
    except Exception:
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
    """
    Async chat endpoint. Returns JSON:
    { "reply": "...", "tool": <tool name or null>, "result": <tool result or null>, "session": {...} }
    """
    try:
        agent = _build_agent_safe()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent initialization error: {exc}")

    payload = {"input": req.message, "session": req.session or {}}

    try:
        if hasattr(agent, "run"):
            resp = agent.run(payload)
            if inspect.isawaitable(resp):
                resp = await resp
        elif hasattr(agent, "invoke"):
            resp = agent.invoke(payload)
            if inspect.isawaitable(resp):
                resp = await resp
        elif callable(agent):
            resp = agent(payload)
            if inspect.isawaitable(resp):
                resp = await resp
        else:
            try:
                import router_agent as ra_mod
                if hasattr(ra_mod, "local_route"):
                    resp = ra_mod.local_route(req.message, req.session or {})
                else:
                    raise RuntimeError("Agent does not provide run/invoke and no local_route available.")
            except Exception as e:
                raise RuntimeError(f"No runnable agent available: {e}")
    except Exception as exc:
        logger.exception("Error calling agent: %s", exc)
        raise HTTPException(status_code=500, detail=f"Agent call error: {exc}")

    reply = None
    tool = None
    result = None
    session_out: Optional[Dict[str, Any]] = None

    if isinstance(resp, dict):
        session_out = resp.get("session") or None
        reply = resp.get("reply") or resp.get("output") or None
        tool = resp.get("tool")
        result = resp.get("result") or resp.get("ticket") or resp.get("results") or resp.get("payload")
        if reply is None:
            if isinstance(result, dict) and result.get("status"):
                reply = str(result)
            else:
                reply = str(resp)
    else:
        reply = str(resp)

    response_payload = {"reply": reply, "tool": tool, "result": result}
    if session_out:
        response_payload["session"] = session_out

    return response_payload

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting server on 0.0.0.0:%d", port)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
