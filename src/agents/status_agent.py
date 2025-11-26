from typing import Dict, Any, Optional
import logging
import re

# ADK imports (guarded)
try:
    from google.adk.agents.llm_agent import Agent  
except Exception:
    Agent = None


try:
    from tools.get_ticket_status import get_ticket_status
except Exception:
    try:
        from src.tools.get_ticket_status import get_ticket_status
    except Exception:
        def get_ticket_status(ticket_id: str) -> Dict[str, Any]:
            if not ticket_id:
                return {"status": "error", "message": "missing ticket_id"}
            # simple fake database
            fake_db = {
                "TICKET-1001": {"ticket_id": "TICKET-1001", "status": "open", "summary": "Laptop slow"},
                "TICKET-2002": {"ticket_id": "TICKET-2002", "status": "in_progress", "summary": "Printer issue"},
            }
            ticket = fake_db.get(ticket_id.upper())
            if ticket:
                return {"status": "success", "ticket": ticket}
            return {"status": "error", "message": "ticket not found"}

logger = logging.getLogger("status_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


STATUS_INSTRUCTION = """
You are the Repair Status Agent.

Your job:
1. Extract `ticket_id` from user's message (examples: TICKET-1A2B3C4D, ticket 1234).
2. If ticket_id is missing, ask the user for it and return:
   {"status": "missing_info", "missing": ["ticket_id"], "reply": <message>}
3. If ticket_id is found, call get_ticket_status(ticket_id) and return:
   {"status": "ticket_found", "ticket": <tool_result>, "reply": <short_reply>}
4. Keep replies short, helpful, and user-facing.
5. Return outputs as a JSON-like dictionary.
"""

def build_status_agent(model_name: str = "gemini-1") -> Any:
    """
    Build an ADK Agent instance for status retrieval.
    The ADK Agent constructor signature may vary across ADK versions.
    """
    if Agent is None:
        raise RuntimeError("google.adk is not installed. Cannot create ADK agent.")
    status_agent = Agent(
        model=model_name,
        name="repair_status_agent",
        description="LLM-powered sub-agent that extracts ticket id and retrieves ticket status.",
        instruction=STATUS_INSTRUCTION,
        tools=[get_ticket_status],
    )
    return status_agent

def _extract_ticket_id(text: str) -> Optional[str]:
    """
    Extract ticket id patterns:
    - TICKET-XXXX (hex/alphanumeric)
    - 'ticket 1234' -> converted to TICKET-1234
    """
    if not text:
        return None
    m = re.search(r"(TICKET[- ]?[0-9A-Za-z]{3,})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip().upper().replace(" ", "-")
    m2 = re.search(r"ticket\s+([0-9]{2,})", text, re.IGNORECASE)
    if m2:
        return f"TICKET-{m2.group(1)}"
    return None


def local_status_process(text: str) -> Dict[str, Any]:
    """
    Naive local processing:
    - Attempts to parse ticket id using regex.
    - Calls get_ticket_status if found.
    - Otherwise asks for ticket id.
    """
    logger.info("Processing status query: %s", text[:120])
    ticket_id = _extract_ticket_id(text)
    if not ticket_id:
        reply = "Please provide your ticket ID (e.g. TICKET-1A2B3C4D) so I can look up the status."
        logger.info("Ticket id missing in text")
        return {"status": "missing_info", "missing": ["ticket_id"], "reply": reply}

    result = get_ticket_status(ticket_id)
    if result.get("status") == "success":
        ticket = result.get("ticket")
        reply = f"Ticket {ticket.get('ticket_id')}: status = {ticket.get('status')}."
        return {"status": "ticket_found", "ticket": ticket, "reply": reply}
    else:
        message = result.get("message", "Ticket not found.")
        return {"status": "error", "message": message, "reply": message}
    
    
if __name__ == "__main__":
    examples = [
        "What's the status of TICKET-1001?",
        "Can you check ticket 2002 for me?",
        "I need an update on my repair."
    ]
    for ex in examples:
        print("-" * 50)
        print("Input:", ex)
        print("Output:", local_status_process(ex))
