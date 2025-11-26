from __future__ import annotations

from typing import Dict, Any, List
from pathlib import Path
import json
import uuid
import datetime
import threading
import tempfile
import os
import logging

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR
for _ in range(4):
    if any((_PROJECT_ROOT / name).exists() for name in (".git", "README.md")):
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
    """Read tickets from the JSON store; return empty list if missing or invalid."""
    try:
        if not _TICKETS_PATH.exists():
            return []
        with _TICKETS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "tickets" in data and isinstance(data["tickets"], list):
                return data["tickets"]
            logger.warning("Unexpected tickets.json format, resetting to empty list.")
            return []
    except Exception as e:
        logger.exception("Error reading tickets file: %s", e)
        return []


def _atomic_write_tickets(tickets: List[Dict[str, Any]]) -> None:
    """Atomically write tickets list to the JSON store using a temp file + replace."""
    dirpath = _TICKETS_PATH.parent
    fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix=".tickets_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(tickets, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, _TICKETS_PATH)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise


def _validate_phone(phone: str) -> str:
    """Basic phone normalization - strip spaces. Extend for country-specific validation."""
    if not phone:
        return ""
    return " ".join(phone.split())


def _current_iso_ts() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def create_ticket(customer_name: str, phone: str, device_sku: str, issue: str, priority: str = "normal") -> Dict[str, Any]:
    """Create a repair ticket and persist it to data/tickets.json

    Returns:
      { "status": "success", "ticket": { ... } }
    or on error:
      { "status": "error", "message": "..." }
    """
    try:
        if not (customer_name and device_sku and issue):
            return {"status": "error", "message": "Missing required fields: customer_name, device_sku, and issue are required."}

        customer_name = customer_name.strip()
        device_sku = device_sku.strip()
        issue = issue.strip()
        phone_norm = _validate_phone(phone)

        ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
        ticket = {
            "ticket_id": ticket_id,
            "customer_name": customer_name,
            "phone": phone_norm,
            "device": device_sku,
            "issue": issue,
            "priority": priority,
            "status": "received",
            "created_at": _current_iso_ts(),
            "updated_at": _current_iso_ts(),
            "notes": []
        }

        with _LOCK:
            tickets = _read_tickets()
            tickets.append(ticket)
            _atomic_write_tickets(tickets)

        logger.info("Created ticket %s for %s", ticket_id, customer_name)
        return {"status": "success", "ticket": ticket}
    except Exception as exc:
        logger.exception("Failed creating ticket: %s", exc)
        return {"status": "error", "message": f"Failed to write ticket: {exc}"}


def list_tickets() -> List[Dict[str, Any]]:
    return _read_tickets()


if __name__ == "__main__":
    print("Data path:", _TICKETS_PATH)
    r = create_ticket("Test User", "+977 9850000000", "XPS-13", "Battery not charging", priority="high")
    print(r)
    print("All tickets:", list_tickets())
