import streamlit as st
import sys
import pathlib
import os
from typing import Dict, Any

# Ensure project src is importable for local fallbacks
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[0]
SRC_PATH = str(PROJECT_ROOT / "src")
ROOT_PATH = str(PROJECT_ROOT)
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
if ROOT_PATH not in sys.path:
    sys.path.insert(0, ROOT_PATH)

# Try to import local fallbacks
try:
    from router_agent import local_route as router_local_route  # if router_agent.py in repo root
except Exception:
    try:
        from src.router_agent import local_route as router_local_route  # if router_agent.py under src
    except Exception:
        router_local_route = None

try:
    from agents.intake_agent import local_intake_process
except Exception:
    def local_intake_process(msg):
        return {"status":"missing_info", "missing":["customer_name"], "reply":"intake agent not available."}

try:
    from agents.status_agent import local_status_process
except Exception:
    def local_status_process(msg):
        return {"status":"missing_info", "missing":["ticket_id"], "reply":"status agent not available."}

try:
    from agents.troubleshooting_agent import local_troubleshoot_process
except Exception:
    def local_troubleshoot_process(msg):
        return {"status":"missing_info", "reply":"troubleshooting agent not available."}

# HTTP client lib
try:
    import requests
except Exception:
    requests = None

# Streamlit UI
st.set_page_config(page_title="AI Service Desk — Demo Chat", page_icon="🤖", layout="centered")
st.title("AI Service Desk — Demo Chat")

st.markdown(
    "This chat UI supports two modes:\n\n"
    "- **Local demo mode** (default): uses built-in local helpers — no external API.\n"
    "- **Remote Gemini mode**: sends messages to a FastAPI backend (main.py) that proxies to Gemini/ADK.\n\n"
    "Toggle the mode below."
)

# Controls
col1, col2 = st.columns([2, 1])
with col2:
    use_remote = st.checkbox("Use remote agent (HTTP)", value=(os.getenv('USE_REMOTE_AGENT') == "1"))
    api_url = st.text_input("Agent API base URL", value=os.getenv("AGENT_API_URL", "http://localhost:8000"))
    if st.button("Test API"):
        if requests is None:
            st.warning("Requests library not installed. Add 'requests' to requirements.txt and restart.")
        else:
            try:
                r = requests.get(f"{api_url.rstrip('/')}/health", timeout=3)
                st.success(f"Health: {r.json()}")
            except Exception as e:
                st.error(f"API health check failed: {e}")

# Initialize session
if "messages" not in st.session_state:
    st.session_state.messages = [{"role":"assistant","text":"Hello! I'm the AI Service Desk. How can I help?"}]
if "session_data" not in st.session_state:
    st.session_state.session_data = {}

def render_messages():
    for m in st.session_state.messages:
        if m["role"] == "user":
            st.markdown(f"**You:** {m['text']}")
        else:
            st.markdown(f"**Agent:** {m['text']}")

def append_message(role: str, text: str):
    st.session_state.messages.append({"role": role, "text": text})

# Chat input
with st.form("user_input", clear_on_submit=True):
    user_input = st.text_input("Type your message here...", "")
    submitted = st.form_submit_button("Send")
if submitted and user_input:
    append_message("user", user_input)
    reply_text = ""
    # Remote mode
    if use_remote and requests is not None:
        try:
            payload = {"message": user_input, "session": st.session_state.session_data}
            resp = requests.post(f"{api_url.rstrip('/')}/chat", json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                reply_text = data.get("reply") or str(data)
                # Optionally update session_data if backend returned any session updates
                if isinstance(data, dict) and data.get("session"):
                    st.session_state.session_data.update(data.get("session"))
            else:
                reply_text = f"Remote agent error: {resp.status_code} {resp.text}"
        except Exception as e:
            reply_text = f"Remote agent unreachable: {e}"
            # fallback to local if available
            if router_local_route is not None:
                try:
                    fallback = router_local_route(user_input, st.session_state.session_data)
                    reply_text = fallback.get("reply", str(fallback))
                except Exception:
                    pass
    else:
        if router_local_route is not None:
            try:
                resp = router_local_route(user_input, st.session_state.session_data)
                reply_text = resp.get("reply") or ""
                if resp.get("tool") == "troubleshooting" and not resp.get("result"):
                    tri = local_troubleshoot_process(user_input)
                    reply_text += "\n\n" + tri.get("reply", "")
                    if tri.get("suggestions"):
                        reply_text += "\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in tri.get("suggestions")[:5])
                result = resp.get("result")
                tool = resp.get("tool")
                if isinstance(result, dict) and result.get("status"):
                    if tool == "inventory_lookup" or (result.get("results") is not None):
                        items = result.get("results", [])
                        if items:
                            reply_text += f"\n\nFound {len(items)} items. Top: {items[0].get('brand')} {items[0].get('model')} (SKU: {items[0].get('sku')}) — Rs.{items[0].get('price')}"
                        else:
                            reply_text += "\n\nNo matching items found."
                    if tool == "create_ticket" or (result.get('ticket') is not None):
                        t = result.get('ticket') or {}
                        reply_text += f"Ticket: {t.get('ticket_id')} — status: {t.get('status')}"
                    if tool == "get_ticket_status" and result.get('ticket') is not None:
                        t = result.get('ticket')
                        reply_text += f"Ticket {t.get('ticket_id')}: status={t.get('status')} (updated: {t.get('updated_at')})"
            except Exception as e:
                reply_text = f"Local router error: {e}"
        else:
            # Try specific fallbacks
            resp = local_intake_process(user_input)
            if resp.get("status") == "ticket_created":
                reply_text = resp.get("reply", "")
            else:
                # fallback troubleshooting
                tri = local_troubleshoot_process(user_input)
                reply_text = tri.get("reply", "")
    append_message("assistant", reply_text)

st.write("---")
render_messages()
st.markdown("**Tips:** Try messages like: \n- `My laptop won't turn on. Model A123. Name: Sita. Phone: +977-98xxxx` \n- `Do you have BrandA A123 in stock?` \n- `What's the status of ticket TICKET-0001?`)
