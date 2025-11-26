from typing import Dict, Any, Optional
import logging
import re

try:
    from google.adk.agents.llm_agent import Agent  
except Exception:
    Agent = None


try:

    from tools.create_ticket import create_ticket
except Exception:
    try:
        from src.tools.create_ticket import create_ticket
    except Exception:
        # fallback stub
        def create_ticket(customer_name: str, phone: str, device_sku: str, issue: str) -> Dict[str, Any]:
            return {"status": "ok", "ticket": {"ticket_id": "stub-1", "customer_name": customer_name, "phone": phone, "device_sku": device_sku, "issue": issue}}

logger = logging.getLogger("intake_agent")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)


INTAKE_INSTRUCTION = """
You are the Repair Intake Agent.

Your job:
1. Extract these fields from the user's message using LLM analysis:
   - customer_name
   - phone
   - device_sku (or device model)
   - issue (the problem description)

2. If ANY required field is missing:
   - Do NOT call any tools.
   - Ask a short, direct follow-up question.
   - Return structure:
     {"status": "missing_info", "missing": [...], "reply": "<message>"}

3. If ALL fields exist:
   - Call the create_ticket tool:
       create_ticket(customer_name, phone, device_sku, issue)
   - Return:
       {"status": "ticket_created", "ticket": <tool_result>, "reply": "<summary>"}

4. Always answer in a short, friendly tone.
5. Output should be a JSON-like dictionary (or a Python dict when running locally).
"""

def build_intake_agent(model_name: str = "gemini-1") -> Any:
    """
    Create an ADK Agent instance configured for intake slot-filling.
    Requires google.adk to be installed. The exact Agent constructor may differ
    across ADK versions; adjust parameters to match your installed SDK.
    """
    if Agent is None:
        raise RuntimeError("google.adk is not installed. Cannot create ADK agent.")

    # The ADK Agent constructor/usage may differ; this is a template following course docs.
    intake_agent = Agent(
        model=model_name,
        name="repair_intake_agent",
        description="LLM-powered sub-agent that extracts fields and creates repair tickets.",
        instruction=INTAKE_INSTRUCTION,
        tools=[create_ticket],  # if create_ticket is an ADK Tool, pass it here
    )
    return intake_agent

def _extract_name(text: str) -> Optional[str]:
    m = re.search(r"(?:name[:\s-]*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"(?:i am|i'm|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None

def _extract_phone(text: str) -> Optional[str]:
    m = re.search(r"(\+?\d[\d\-\s]{6,}\d)", text)
    if m:
        phone = m.group(1).strip()
        # cleanup common separators
        phone = re.sub(r"[\s\-]+", " ", phone)
        return phone
    return None

def _extract_device(text: str) -> Optional[str]:
    m = re.search(r"(?:model|device|sku)[:\s-]*([A-Za-z0-9\-\s]+\w)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"(dell\s+xps|thinkpad|macbook|hp\s+laserjet|printer|iphone|samsung\s+galaxy)", text, re.IGNORECASE)
    if m2:
        return m2.group(0).strip()
    return None

def _compose_missing_reply(missing_fields: list) -> str:
    if not missing_fields:
        return ""
    field = missing_fields[0]
    if field == "customer_name":
        return "Could you please provide the customer's full name?"
    if field == "phone":
        return "What's the best phone number to reach the customer at?"
    if field == "device_sku":
        return "Can you share the device model or SKU (e.g., Dell XPS 13)?"
    return "Could you provide more details, please?"

def local_intake_process(text: str) -> Dict[str, Any]:
    """
    Offline, heuristic-based intake processor for testing without Gemini/ADK.
    Returns a dict matching the expected agent outputs.
    """
    logger.info("Running local intake on text: %s", text[:120])
    # Attempt extraction
    name = _extract_name(text)
    phone = _extract_phone(text)
    device = _extract_device(text)
    issue = text.strip()

    missing = []
    if not name:
        missing.append("customer_name")
    if not phone:
        missing.append("phone")
    if not device:
        missing.append("device_sku")

    if missing:
        reply = _compose_missing_reply(missing)
        logger.info("Missing fields: %s", missing)
        return {"status": "missing_info", "missing": missing, "reply": reply}

    try:
        ticket_res = create_ticket(name, phone, device, issue)
        ticket_id = None
        if isinstance(ticket_res, dict):
            ticket_id = ticket_res.get("ticket", {}).get("ticket_id") or ticket_res.get("ticket_id")
        reply = f"Thanks — I created a repair ticket{f' (ID: {ticket_id})' if ticket_id else ''}."
        logger.info("Ticket created: %s", ticket_res)
        return {"status": "ticket_created", "ticket": ticket_res, "reply": reply}
    except Exception as e:
        logger.exception("create_ticket tool failed: %s", e)
        return {"status": "error", "error": str(e), "reply": "Sorry, I couldn't create the ticket due to an internal error."}

if __name__ == "__main__":
    examples = [
        "Name: Rajesh KC. Phone: +977-9851234567. Model: Dell XPS 13. My laptop won't boot after update.",
        "My printer won't print. It's a HP LaserJet 1020. Contact: 9841122334",
        "Hi, I'm Asha and my phone won't charge."
    ]
    for ex in examples:
        print("-" * 60)
        print("Input:", ex)
        print("Output:", local_intake_process(ex))
