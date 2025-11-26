from __future__ import annotations

from typing import Dict, Any, List
from pathlib import Path
import json
import threading
import logging
import os

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR
for _ in range(4):
    if any((_PROJECT_ROOT / name).exists() for name in (".git", "README.md", "data")):
        break
    if _PROJECT_ROOT.parent == _PROJECT_ROOT:
        break
    _PROJECT_ROOT = _PROJECT_ROOT.parent

_DATA_DIR = _PROJECT_ROOT / "data"
_TICKETS_PATH = _DATA_DIR / "tickets.json"

_LOCK = threading.RLock()


try:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    _DATA_DIR = Path.cwd() / "data"
    _TICKETS_PATH = _DATA_DIR / "tickets.json"
    _DATA_DIR.mkdir(parents=True, exist_ok=True)



def _read_tickets() -> List[Dict[str, Any]]:
    """Read tickets from JSON file. Returns an empty list if unreadable."""
    try:
        if not _TICKETS_PATH.exists():
            return []
        with _TICKETS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "tickets" in data and isinstance(data["tickets"], list):
                return data["tickets"]
            logger.warning("tickets.json format unexpected, returning empty list.")
            return []
    except Exception as e:
        logger.exception("Error reading tickets: %s", e)
        return []


def get_ticket_status(ticket_id: str) -> Dict[str, Any]:
    """Retrieve the status/details of a repair ticket."""
    if not ticket_id:
        return {"status": "error", "message": "ticket_id is required"}

    ticket_id_norm = str(ticket_id).strip().upper()

    try:
        with _LOCK:
            tickets = _read_tickets()
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read tickets: {exc}"}


    for t in tickets:
        if not isinstance(t, dict):
            continue
        stored_id = str(t.get("ticket_id", "")).upper()
        if stored_id == ticket_id_norm:
            logger.info("Exact ticket match found: %s", stored_id)
            return {"status": "success", "ticket": t}

  
    matches = [t for t in tickets if ticket_id_norm in str(t.get("ticket_id", "")).upper()]
    if matches:
        logger.info("Partial match for ticket %s", ticket_id_norm)
        return {"status": "success", "ticket": matches[0], "note": "partial_match"}

    logger.info("Ticket %s not found.", ticket_id_norm)
    return {"status": "error", "message": f"Ticket {ticket_id} not found"}


if __name__ == "__main__":
    print("Data path:", _TICKETS_PATH)
    print(get_ticket_status("TICKET-XXXX"))
