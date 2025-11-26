from __future__ import annotations

from typing import Dict, Any, List, Optional, Callable
import logging
import re


try:
    from google.adk.agents.llm_agent import Agent  
except Exception:
    Agent = None


def _import_tool(name: str) -> Callable:
    """Try common import locations for tools and return a callable or stub."""
    try:
        # try package-style import: tools.name
        mod = __import__(f"tools.{name}", fromlist=[name])
        return getattr(mod, name)
    except Exception:
        pass
    try:
        # try src.tools.name
        mod = __import__(f"src.tools.{name}", fromlist=[name])
        return getattr(mod, name)
    except Exception:
        pass
    # fallback stubs
    def _stub(*args, **kwargs):
        return {"status": "error", "message": f"Tool {name} not available in environment."}
    return _stub

inventory_lookup = _import_tool("inventory_lookup")
create_ticket = _import_tool("create_ticket")
get_ticket_status = _import_tool("get_ticket_status")


logger = logging.getLogger("router_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(h)


ROUTER_INSTRUCTION = """You are the AI Service Desk Router Agent.
Classify user messages into intents and call the appropriate tool or sub-agent.
Intents: repair_intake, inventory_query, status_query, troubleshoot, fallback.
Produce a JSON-like dict: {"reply": <str>, "tool": <str|null>, "result": <dict|null>, "intent": <str>}
Keep replies short and user-friendly. Ask for missing info when needed.
"""

TOOLS = [inventory_lookup, create_ticket, get_ticket_status]

DEFAULT_MODEL = "gemini-1"


def build_router_agent(model_name: str = DEFAULT_MODEL) -> Any:
    """
    Build and return an ADK Agent configured as the root router.
    Raises RuntimeError if ADK Agent class is not available.
    """
    if Agent is None:
        raise RuntimeError("google.adk is not installed. Install google-adk to construct the ADK Agent.")
    root_agent = Agent(
        model=model_name,
        name="ai_service_desk_router",
        description="Router agent that classifies intent and calls tools/sub-agents.",
        instruction=ROUTER_INSTRUCTION,
        tools=TOOLS,
    )
    return root_agent

def _detect_intent(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["ticket", "repair", "fix", "create ticket", "i need a repair", "repair request"]):
        return "repair_intake"
    if any(k in t for k in ["stock", "price", "how much", "availability", "in stock", "do you have"]):
        return "inventory_query"
    if any(k in t for k in ["status", "ticket-", "ticket ", "tkt", "where is my ticket"]):
        return "status_query"
    if any(k in t for k in ["doesn't work", "not working", "paper jam", "overheat", "no power", "no display", "not printing"]):
        return "troubleshoot"
    return "fallback"


def _extract_ticket_id(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(TICKET[- ]?[0-9A-Za-z]{3,})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip().upper().replace(" ", "-")
    m2 = re.search(r"ticket\s+([0-9]{2,})", text, re.IGNORECASE)
    if m2:
        return f"TICKET-{m2.group(1)}"
    return None


def local_route(user_message: str, session_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Lightweight deterministic router for offline testing.

    Args:
        user_message: incoming user text
        session_state: optional dict containing previous conversation state (e.g., extracted fields)

    Returns:
        {
            "reply": str,
            "tool": str|None,
            "result": dict|None,
            "intent": str
        }
    """
    session_state = session_state or {}
    intent = _detect_intent(user_message)
    logger.info("local_route detected intent=%s for message=%s", intent, user_message[:120])

    # Inventory query
    if intent == "inventory_query":
        result = inventory_lookup(user_message)
        count = result.get("count") if isinstance(result, dict) else len(result) if hasattr(result, "__len__") else 0
        reply = f"I found {count} matching items." if count else "No matching items found."
        return {"reply": reply, "tool": "inventory_lookup", "result": result, "intent": intent}

    # Status query
    if intent == "status_query":
        ticket_id = _extract_ticket_id(user_message) or session_state.get("ticket_id")
        if not ticket_id:
            return {"reply": "Please provide your ticket ID (e.g. TICKET-1234).", "tool": None, "result": None, "intent": intent}
        result = get_ticket_status(ticket_id)
        if result.get("status") == "success":
            ticket = result.get("ticket")
            reply = f"Ticket {ticket.get('ticket_id')}: status = {ticket.get('status')}."
            return {"reply": reply, "tool": "get_ticket_status", "result": result, "intent": intent}
        return {"reply": result.get("message", "Ticket not found."), "tool": "get_ticket_status", "result": result, "intent": intent}

    # Repair intake
    if intent == "repair_intake":
        name = session_state.get("customer_name")
        phone = session_state.get("phone")
        device = session_state.get("device_sku")
        issue = user_message
        missing = []
        if not name:
            missing.append("customer_name")
        if not phone:
            missing.append("phone")
        if not device:
            missing.append("device model or SKU")
        if missing:
            reply = f"I need the following to create a ticket: {', '.join(missing)}."
            return {"reply": reply, "tool": None, "result": None, "intent": intent}

        result = create_ticket(name, phone, device, issue)
        ticket_id = result.get("ticket", {}).get("ticket_id") if isinstance(result, dict) else None
        reply = f"Ticket created{f' (ID: {ticket_id})' if ticket_id else ''}. We'll notify you with updates."
        return {"reply": reply, "tool": "create_ticket", "result": result, "intent": intent}

    # Troubleshoot
    if intent == "troubleshoot":
        reply = "I can help troubleshoot — please describe the exact symptoms, any error messages, and device model."
        return {"reply": reply, "tool": "troubleshooting", "result": None, "intent": intent}

    # fallback
    return {
        "reply": "Sorry, I didn't understand. Do you want to create a repair ticket, check product availability, or check ticket status?",
        "tool": None,
        "result": None,
        "intent": intent
    }
