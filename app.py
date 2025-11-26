# app.py - Streamlit UI for AI Service Desk (compatible version)
import streamlit as st
import streamlit.components.v1 as components
import sys
import pathlib
import os
from typing import Dict, Any
import html as _html
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[0]
SRC_PATH = str(PROJECT_ROOT / "src")
ROOT_PATH = str(PROJECT_ROOT)
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
if ROOT_PATH not in sys.path:
    sys.path.insert(0, ROOT_PATH)

# Try to import router_agent local fallback
try:
    from router_agent import local_route as router_local_route
except Exception:
    try:
        from src.router_agent import local_route as router_local_route
    except Exception:
        router_local_route = None

# Agent fallbacks
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

# Optional requests
try:
    import requests
except Exception:
    requests = None

# Page meta
st.set_page_config(page_title="AI Service Desk — Demo Chat", page_icon="🤖", layout="wide")
st.title("AI Service Desk — Demo Chat")

st.markdown(
    "This chat UI supports two modes:\n\n"
    "- **Local demo mode** (default): uses built-in local helpers — no external API.\n"
    "- **Remote Gemini mode**: sends messages to a FastAPI backend (main.py) that proxies to Gemini/ADK.\n\n"
    "Toggle the mode below."
)

# Controls layout
left, right = st.columns([3, 1])
with right:
    use_remote = st.checkbox("Use remote agent (HTTP)", value=(os.getenv('USE_REMOTE_AGENT') == "1"))
    api_url = st.text_input("Agent API base URL", value=os.getenv("AGENT_API_URL", "http://localhost:8000"))
    if st.button("Test API"):
        if requests is None:
            st.warning("Requests library not installed. Add 'requests' to requirements.txt and restart the app.")
        else:
            try:
                r = requests.get(f"{api_url.rstrip('/')}/health", timeout=3)
                st.success(f"Health: {r.status_code} {r.text}")
            except Exception as e:
                st.error(f"API health check failed: {e}")

# Session state defaults
if "messages" not in st.session_state:
    st.session_state.messages = [{"role":"assistant","text":"Hello! I'm the AI Service Desk. How can I help?"}]
if "session_data" not in st.session_state:
    st.session_state.session_data = {}
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "last_action" not in st.session_state:
    st.session_state.last_action = None

# Renderer: single components.html call to avoid DOM splitting
def render_messages_component(height_px: int = 520):
    # area height (small padding)
    area_height = max(200, height_px - 40)

    css = f"""
    <style>
    .chat-wrapper {{
        max-width: 1100px;
        margin: 8px auto;
    }}
    .chat-area {{
        height: {area_height}px;
        overflow: auto;
        padding: 18px;
        border-radius: 12px;
        background: #0b0d0f;
        border: 1px solid rgba(255,255,255,0.04);
        box-shadow: 0 8px 30px rgba(0,0,0,0.6);
    }}
    .chat {{
        display:flex;
        margin-bottom:12px;
        width:100%;
    }}
    .chat.user {{ justify-content:flex-end; }}
    .chat.agent {{ justify-content:flex-start; }}
    .bubble {{
        padding: 12px 16px;
        border-radius: 14px;
        max-width: 78%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.4);
        word-break:break-word;
        white-space:pre-wrap;
    }}
    .user .bubble {{
        background: linear-gradient(135deg,#14532d 0%,#166534 100%);
        color:#fff;
        border-bottom-right-radius:6px;
    }}
    .agent .bubble {{
        background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.02));
        color:#e6eef8;
        border:1px solid rgba(255,255,255,0.02);
        border-bottom-left-radius:6px;
    }}
    .meta {{ font-size:12px; color:#9aa7b2; margin-bottom:6px; }}
    .small {{ font-size:14px; color:#e6eef8; }}
    #chat-area::-webkit-scrollbar {{ width:8px; }}
    #chat-area::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.06); border-radius: 10px; }}
    </style>
    """

    # Build messages HTML
    rows = []
    for m in st.session_state.messages:
        role = m.get("role", "assistant")
        text_raw = m.get("text", "")
        text = _html.escape(text_raw).replace("\n", "<br/>")
        if role == "user":
            rows.append(f'<div class="chat user"><div class="bubble"><div class="meta">You</div><div class="small">{text}</div></div></div>')
        else:
            rows.append(f'<div class="chat agent"><div class="bubble"><div class="meta">Agent</div><div class="small">{text}</div></div></div>')

    # small timestamp appended to force browser to re-render unique HTML when messages change
    stamp = int(time.time() * 1000)

    html = f"""
    <!doctype html>
    <html>
      <head>{css}</head>
      <body>
        <div class="chat-wrapper">
          <div class="chat-area" id="chat-area">
            {''.join(rows)}
          </div>
        </div>

        <script>
          (function() {{
            var el = document.getElementById("chat-area");
            if (el) {{
              el.scrollTop = el.scrollHeight;
            }}
          }})();
        </script>
        <!-- stamp:{stamp} -->
      </body>
    </html>
    """

    # NOTE: do not pass unsupported kwargs like 'key' for older Streamlit
    components.html(html, height=height_px, scrolling=True)

# Render chat area (tune px if input gets pushed off-screen)
render_messages_component(height_px=480)

# Input area
st.write("---")
input_col, actions_col = st.columns([5, 1])
with input_col:
    user_text = st.text_input("Type your message here...", value=st.session_state.user_input, key="text_input")
with actions_col:
    send = st.button("Send")
    quick = st.button("Quick example")

# quick example behaviour
if quick:
    example = "My laptop won't turn on. Model A123. Name: Sita. Phone: +977-98xxxx"
    st.session_state.user_input = example
    user_text = example
    send = True
    st.session_state.last_action = "quick_example"

# send handling
if send and user_text and user_text.strip():
    # append user message
    st.session_state.messages.append({"role": "user", "text": user_text.strip()})
    # clear input stored value
    st.session_state.user_input = ""

    reply_text = ""

    # remote mode
    if use_remote and requests is not None:
        try:
            payload = {"message": user_text, "session": st.session_state.session_data}
            resp = requests.post(f"{api_url.rstrip('/')}/chat", json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                reply_text = data.get("reply") or str(data)
                if isinstance(data, dict) and data.get("session"):
                    st.session_state.session_data.update(data.get("session"))
            else:
                reply_text = f"Remote agent error: {resp.status_code} {resp.text}"
        except Exception as e:
            reply_text = f"Remote agent unreachable: {e}"
            # fallback to local router
            if router_local_route is not None:
                try:
                    fallback = router_local_route(user_text, st.session_state.session_data)
                    reply_text = fallback.get("reply", str(fallback))
                except Exception:
                    pass
    else:
        # local router or fallbacks
        if router_local_route is not None:
            try:
                resp = router_local_route(user_text, st.session_state.session_data)
                reply_text = resp.get("reply") or ""
                if resp.get("tool") == "troubleshooting" and not resp.get("result"):
                    tri = local_troubleshoot_process(user_text)
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
            # fallback intake/troubleshoot
            resp = local_intake_process(user_text)
            if resp.get("status") == "ticket_created":
                reply_text = resp.get("reply", "")
            else:
                tri = local_troubleshoot_process(user_text)
                reply_text = tri.get("reply", "")

    # append assistant reply
    st.session_state.messages.append({"role": "assistant", "text": reply_text or "Sorry — no reply generated."})

    # refresh UI to show updated messages; if your Streamlit version is older, swap to experimental_rerun()
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            # if rerun not available, just pass (user will manually see new content on next interaction)
            pass

# Helpful tips area
st.markdown("""
**Tips:** Try messages like:

- `My laptop won't turn on. Model A123. Name: Sita. Phone: +977-98xxxx`
- `Do you have BrandA A123 in stock?`
- `What's the status of ticket TICKET-0001?`
""")
