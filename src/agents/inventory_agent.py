from __future__ import annotations

import json
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging
import tempfile
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_serial(serial: str) -> str:
    return serial.strip().upper()


class InventoryAgent:
    def __init__(self, persist_path: Optional[str] = None, autosave: bool = True):
        """
        Initialize the InventoryAgent.

        Args:
            persist_path: Optional path to a JSON file to load/save inventory.
            autosave: If True, saves on every mutating operation.
        """
        self._lock = threading.RLock()
        self.persist_path = persist_path
        self.autosave = autosave
        self._items: Dict[str, Dict[str, Any]] = {}
        if self.persist_path:
            self._load()

    def _load(self) -> None:
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                normalized = {}
                for k, v in data.items():
                    nk = _normalize_serial(str(k))
                    v["serial"] = nk
                    normalized[nk] = v
                self._items = normalized
            else:
                logger.warning("Inventory file format unexpected, starting empty.")
                self._items = {}
            logger.info("Loaded inventory from %s (%d items).", self.persist_path, len(self._items))
        except FileNotFoundError:
            logger.info("No inventory file found at %s. Starting with empty inventory.", self.persist_path)
            self._items = {}
        except Exception as e:
            logger.exception("Failed loading inventory file: %s", e)
            self._items = {}

    def save(self, path: Optional[str] = None) -> None:
        """
        Atomically save inventory to disk. Writes to a temp file and renames it.
        """
        path = path or self.persist_path
        if not path:
            raise ValueError("No persist_path provided to save inventory.")
        with self._lock:
            dirpath = os.path.dirname(os.path.abspath(path)) or "."
            fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix=".tmp_inventory_")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._items, f, indent=2, default=str, ensure_ascii=False)
                os.replace(tmp_path, path)
            except Exception:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                raise
        logger.info("Saved inventory to %s (%d items).", path, len(self._items))

    def add_item(self, item: Dict[str, Any], autosave: Optional[bool] = None) -> Dict[str, Any]:
        """
        Add a new inventory item. Item must contain a unique 'serial' key.

        Returns the stored item.
        """
        autosave = self.autosave if autosave is None else autosave
        serial = item.get("serial")
        if not serial:
            raise ValueError("Item must contain a 'serial' field.")
        serial_n = _normalize_serial(str(serial))
        with self._lock:
            if serial_n in self._items:
                raise KeyError(f"Item with serial {serial} already exists.")
            # enrich item
            now = _now_iso()
            stored = {
                "serial": serial_n,
                "model": item.get("model"),
                "make": item.get("make"),
                "status": item.get("status", "available"),  
                "owner": item.get("owner"),
                "location": item.get("location"),
                "tags": item.get("tags", []),
                "added_at": item.get("added_at", now),
                "last_updated": now,
                "metadata": item.get("metadata", {})
            }
            self._items[serial_n] = stored
            logger.info("Added inventory item %s", serial_n)
            if autosave and self.persist_path:
                self.save()
            return stored

    def update_item(self, serial: str, updates: Dict[str, Any], autosave: Optional[bool] = None) -> Dict[str, Any]:
        """
        Update an existing item. Returns the updated item.
        """
        autosave = self.autosave if autosave is None else autosave
        serial_n = _normalize_serial(serial)
        with self._lock:
            if serial_n not in self._items:
                raise KeyError(f"Item with serial {serial_n} not found.")
            item = self._items[serial_n]
            updates = dict(updates)
            updates.pop("serial", None)
            item.update(updates)
            item["last_updated"] = _now_iso()
            self._items[serial_n] = item
            logger.info("Updated inventory item %s", serial_n)
            if autosave and self.persist_path:
                self.save()
            return item

    def remove_item(self, serial: str, autosave: Optional[bool] = None) -> Dict[str, Any]:
        """
        Remove an item by serial. Returns the removed item.
        """
        autosave = self.autosave if autosave is None else autosave
        serial_n = _normalize_serial(serial)
        with self._lock:
            if serial_n not in self._items:
                raise KeyError(f"Item with serial {serial_n} not found.")
            removed = self._items.pop(serial_n)
            logger.info("Removed inventory item %s", serial_n)
            if autosave and self.persist_path:
                self.save()
            return removed

    def get_item(self, serial: str) -> Optional[Dict[str, Any]]:
        """
        Return a copy of the item to avoid accidental external mutation.
        """
        serial_n = _normalize_serial(serial)
        with self._lock:
            item = self._items.get(serial_n)
            return dict(item) if item is not None else None

    def list_items(self, filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = [dict(i) for i in self._items.values()]
        if filter_fn:
            return [i for i in items if filter_fn(i)]
        return items

    def allocate_device(self, serial: str, user: str, reason: Optional[str] = None, autosave: Optional[bool] = None) -> Dict[str, Any]:
        """
        Allocate a device to a user. Changes status to 'allocated' and sets owner.
        """
        autosave = self.autosave if autosave is None else autosave
        serial_n = _normalize_serial(serial)
        with self._lock:
            if serial_n not in self._items:
                raise KeyError(f"Item with serial {serial_n} not found.")
            item = self._items[serial_n]
            if item.get("status") == "allocated":
                raise RuntimeError(f"Item {serial_n} is already allocated to {item.get('owner')}.")
            item["status"] = "allocated"
            item["owner"] = user
            item.setdefault("allocations", []).append({
                "user": user,
                "reason": reason,
                "allocated_at": _now_iso()
            })
            item["last_updated"] = _now_iso()
            self._items[serial_n] = item
            logger.info("Allocated device %s to %s", serial_n, user)
            if autosave and self.persist_path:
                self.save()
            return dict(item)

    def release_device(self, serial: str, autosave: Optional[bool] = None) -> Dict[str, Any]:
        """
        Release a device back to inventory. Sets status to 'available' and clears owner.
        """
        autosave = self.autosave if autosave is None else autosave
        serial_n = _normalize_serial(serial)
        with self._lock:
            if serial_n not in self._items:
                raise KeyError(f"Item with serial {serial_n} not found.")
            item = self._items[serial_n]
            item["status"] = "available"
            previous_owner = item.get("owner")
            item["owner"] = None
            item.setdefault("releases", []).append({
                "previous_owner": previous_owner,
                "released_at": _now_iso()
            })
            item["last_updated"] = _now_iso()
            self._items[serial_n] = item
            logger.info("Released device %s (previous owner: %s)", serial_n, previous_owner)
            if autosave and self.persist_path:
                self.save()
            return dict(item)
        
    def find_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(i) for i in self._items.values() if tag in (i.get("tags") or [])]

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Naive search across serial, model, make, owner, and metadata values.
        """
        q = (query or "").lower()
        with self._lock:
            results = []
            for item in self._items.values():
                hay = " ".join([
                    str(item.get("serial") or ""),
                    str(item.get("model") or ""),
                    str(item.get("make") or ""),
                    str(item.get("owner") or ""),
                    " ".join([str(v) for v in (item.get("tags") or [])]),
                    json.dumps(item.get("metadata") or {})
                ]).lower()
                if q in hay:
                    results.append(dict(item))
            return results

    def report_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._items)
            by_status: Dict[str, int] = {}
            by_model: Dict[str, int] = {}
            for item in self._items.values():
                st = item.get("status") or "unknown"
                by_status[st] = by_status.get(st, 0) + 1
                model = item.get("model") or "unknown"
                by_model[model] = by_model.get(model, 0) + 1
        return {
            "total": total,
            "by_status": by_status,
            "by_model": by_model,
            "generated_at": _now_iso()
        }

if __name__ == "__main__":
    agent = InventoryAgent(persist_path="/tmp/inventory_demo.json", autosave=True)
    try:
        agent.add_item({"serial": "SN1001", "model": "Dell XPS 13", "make": "Dell", "tags": ["laptop"]})
        agent.add_item({"serial": "SN1002", "model": "Lenovo ThinkPad T14", "make": "Lenovo", "tags": ["laptop"]})
        agent.add_item({"serial": "SN2001", "model": "HP LaserJet 1020", "make": "HP", "tags": ["printer"]})
    except Exception:
        pass

    print("Inventory summary:", agent.report_summary())
    agent.allocate_device("SN1001", "alice@example.com", reason="New hire")
    print("After allocation:", agent.get_item("SN1001"))
    agent.release_device("SN1001")
    print("After release:", agent.get_item("SN1001"))
    agent.save()
