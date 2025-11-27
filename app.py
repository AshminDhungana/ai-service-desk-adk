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
    from src.router_agent import local_route as router_local_route
except Exception:
    try:
        from src.router_agent import local_route as router_local_route
    except Exception:
        router_local_route = None

# Agent fallbacks
try:
    from src.agents.intake_agent import local_intake_process
except Exception:
    def local_intake_process(msg):
        return {"status":"missing_info", "missing":["customer_name"], "reply":"intake agent not available."}

try:
    from src.agents.status_agent import local_status_process
except Exception:
    def local_status_process(msg):
        return {"status":"missing_info", "missing":["ticket_id"], "reply":"status agent not available."}

try:
    from src.agents.troubleshooting_agent import local_troubleshoot_process
except Exception:
    def local_troubleshoot_process(msg):
        return {"status":"missing_info", "reply":"troubleshooting agent not available."}

try:
    import requests
except Exception:
    requests = None

st.set_page_config(page_title="AI Service Desk — Chat", page_icon="🤖", layout="wide")

left, right = st.columns([3, 1])

# LEFT SIDE — Title + Description
with left:
    st.title("AI Service Desk — Chat")

    st.markdown(
        "This chat UI supports two modes:\n\n"
        "- **Local demo mode** (default): uses built-in local helpers — no external API.\n"
        "- **Remote Gemini mode**: sends messages to a FastAPI backend (main.py) that proxies to Gemini/ADK.\n\n"
        "Toggle the mode on the right."
    )

# RIGHT SIDE — Controls
with right:
    use_remote = st.checkbox(
        "Use remote agent (HTTP)",
        value=(os.getenv('USE_REMOTE_AGENT') == "1")
    )

    api_url = st.text_input(
        "Agent API base URL",
        value=os.getenv("AGENT_API_URL", "http://localhost:8000")
    )

    if st.button("Test API"):
        if requests is None:
            st.warning("Requests library not installed. Add 'requests' to requirements.txt and restart the app.")
        else:
            try:
                r = requests.get(f"{api_url.rstrip('/')}/health", timeout=3)
                health_data = r.json()
                agent_loaded = health_data.get("agent_loaded")
                st.success(f"Health: {'good' if r.status_code == 200 else 'bad'}, Agent AI Loaded: {agent_loaded}")
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

def render_messages_component(height_px: int = 520):
    area_height = max(200, height_px - 40)

    css = f"""
    <style>
    html, body {{
        height: 100%;
        margin: 0;
        padding: 0;
        background: transparent;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}

    * {{
        box-sizing: border-box;
    }}

    .chat-wrapper {{
        display: flex;
        justify-content: stretch;
        align-items: flex-start;    
        width: 100%;
        padding: 8px 0;
        height: 100%;
    }}

    .chat-area {{
        width: 100%;
        max-width: 100%;         
        height: {area_height}px;
        overflow-y: auto;
        padding: 20px;
        border-radius: 16px;
        background: linear-gradient(135deg, #0b0d0f 0%, #121416 100%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        box-shadow:
            0 10px 30px rgba(0, 0, 0, 0.65),
            inset 0 1px 0 rgba(255, 255, 255, 0.02);
        display: flex;
        flex-direction: column;
        gap: 14px;
        margin: 0 24px;           
        scroll-behavior: smooth;   
    }}

    .chat {{
        display: flex;
        width: 100%;
        animation: slideIn 0.18s ease-out;
    }}

    .chat.user {{
        justify-content: flex-end;
    }}

    .chat.agent {{
        justify-content: flex-start;
    }}

    .bubble {{
        max-width: 75%;
        padding: 12px 16px;
        border-radius: 14px;
        word-break: break-word;
        white-space: pre-wrap;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
        animation: fadeIn 0.18s ease-out;
        border: 1px solid rgba(255,255,255,0.02);
    }}

    .user .bubble {{
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: #ffffff;
        border-bottom-right-radius: 6px;
        border: 1px solid rgba(16, 185, 129, 0.28);
    }}

    .agent .bubble {{
        background: linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%);
        color: #e6eef8;
        border-bottom-left-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(2px);
    }}

    .meta {{
        font-size: 11px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.62);
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }}

    .user .meta {{
        color: rgba(255, 255, 255, 0.85);
    }}

    .message-text {{
        font-size: 14px;
        line-height: 1.55;
        letter-spacing: 0.2px;
        white-space: pre-wrap;
    }}

    /* Scrollbar styling */
    .chat-area::-webkit-scrollbar {{
        width: 10px;
    }}

    .chat-area::-webkit-scrollbar-track {{
        background: transparent;
    }}

    .chat-area::-webkit-scrollbar-thumb {{
        background: rgba(255, 255, 255, 0.08);
        border-radius: 10px;
    }}

    .chat-area::-webkit-scrollbar-thumb:hover {{
        background: rgba(255, 255, 255, 0.14);
    }}

    @keyframes slideIn {{
        from {{
            opacity: 0;
            transform: translateY(8px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
    }}
    </style>
    """

    rows = []
    for m in st.session_state.messages:
        role = m.get("role", "assistant")
        text_raw = m.get("text", "")
        text = _html.escape(text_raw).replace("\n", "<br/>")
        
        if role == "user":
            rows.append(
                f'<div class="chat user">'
                f'<div class="bubble">'
                f'<div class="meta">You</div>'
                f'<div class="message-text">{text}</div>'
                f'</div>'
                f'</div>'
            )
        else:
            rows.append(
                f'<div class="chat agent">'
                f'<div class="bubble">'
                f'<div class="meta">Agent</div>'
                f'<div class="message-text">{text}</div>'
                f'</div>'
                f'</div>'
            )

    stamp = int(time.time() * 1000)

    html = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {css}
      </head>
      <body>
        <div class="chat-wrapper">
          <div class="chat-area" id="chat-area">
            {''.join(rows)}
            <div id="__chat-end-marker__" aria-hidden="true"></div>
          </div>
        </div>

        <script>
          (function() {{
            try {{
              var end = document.getElementById("__chat-end-marker__");
              if (end) {{
                // scroll the last element into view smoothly
                end.scrollIntoView({{ behavior: 'smooth', block: 'end' }});
              }} else {{
                var el = document.getElementById("chat-area");
                if (el) {{
                  el.scrollTop = el.scrollHeight;
                }}
              }}
            }} catch (e) {{
              // fail silently - we don't want errors leaking to the page
              console && console.warn && console.warn('scroll error', e);
            }}
          }})();
        </script>
        <!-- stamp:{stamp} -->
      </body>
    </html>
    """
    
    st.html(html)

render_messages_component(height_px=480)

# Input area
st.write("---")
input_col, actions_col = st.columns([5, 1])
with input_col:
    user_text = st.text_input("Type your message here...", value=st.session_state.user_input, key="text_input")
with actions_col:
    send = st.button("Send")
    quick = st.button("Quick example")


if quick:
    example = "My laptop won't turn on. Model A123. Name: Sita. Phone: +977-98xxxx"
    st.session_state.user_input = example
    user_text = example
    send = True
    st.session_state.last_action = "quick_example"

if send and user_text and user_text.strip():
    st.session_state.messages.append({"role": "user", "text": user_text.strip()})
    st.session_state.user_input = ""

    reply_text = ""

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
            resp = local_intake_process(user_text)
            if resp.get("status") == "ticket_created":
                reply_text = resp.get("reply", "")
            else:
                tri = local_troubleshoot_process(user_text)
                reply_text = tri.get("reply", "")


    st.session_state.messages.append({"role": "assistant", "text": reply_text or "Sorry — no reply generated."})

    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

st.markdown("""
**Tips:** Try messages like:

- `My laptop won't turn on. Model A123. Name: Sita. Phone: +977-98xxxx`
- `Do you have BrandA A123 in stock?`
- `What's the status of ticket TICKET-0001?`
""")
