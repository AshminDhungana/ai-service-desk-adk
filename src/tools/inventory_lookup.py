from __future__ import annotations

from typing import Dict, Any, List, Tuple
from pathlib import Path
import json
import threading
import re
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
    if any((_PROJECT_ROOT / name).exists() for name in ('.git', 'README.md', 'data')):
        break
    if _PROJECT_ROOT.parent == _PROJECT_ROOT:
        break
    _PROJECT_ROOT = _PROJECT_ROOT.parent

_DATA_DIR = _PROJECT_ROOT / "data"
_INVENTORY_PATH = _DATA_DIR / "inventory.json"

_LOCK = threading.RLock()


try:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    _DATA_DIR = Path.cwd() / "data"
    _INVENTORY_PATH = _DATA_DIR / "inventory.json"
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_inventory() -> List[Dict[str, Any]]:
    try:
        if not _INVENTORY_PATH.exists():
            return []
        with _INVENTORY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and 'inventory' in data and isinstance(data['inventory'], list):
                return data['inventory']
            logger.warning("Unexpected inventory.json format, returning empty list.")
            return []
    except Exception as e:
        logger.exception("Error reading inventory file: %s", e)
        return []


def _normalize_text(s: Any) -> str:
    if s is None:
        return ""
    return str(s).lower()


def _score_item(item: Dict[str, Any], terms: List[str]) -> int:
    """Simple scoring:
    +4 for SKU exact contains
    +3 for model exact contains
    +2 for brand/category contains
    +1 for description contains per term
    """
    score = 0
    sku = _normalize_text(item.get("sku", ""))
    model = _normalize_text(item.get("model", ""))
    brand = _normalize_text(item.get("brand", ""))
    category = _normalize_text(item.get("category", ""))
    description = _normalize_text(item.get("description", ""))

    joined = " ".join([sku, model, brand, category, description])

    for t in terms:
        if t in sku:
            score += 4
        if t in model:
            score += 3
        if t in brand or t in category:
            score += 2
        if t in description:
            score += 1
        tokens = re.split(r"\W+", joined)
        if t in tokens:
            score += 1
    return score


def inventory_lookup(query: str, max_results: int = 10) -> Dict[str, Any]:
    if query is None:
        return {"status": "error", "message": "query is required"}

    q = str(query).strip().lower()
    if not q:
        return {"status": "error", "message": "query is empty"}

    # split into terms
    terms = [t for t in re.split(r"\W+", q) if t]
    if not terms:
        return {"status": "error", "message": "no searchable terms found"}

    try:
        with _LOCK:
            items = _read_inventory()
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read inventory: {exc}"}

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for item in items:
        try:
            s = _score_item(item, terms)
        except Exception:
            s = 0
        if s > 0:
            scored.append((s, item))

    if not scored:
        for item in items:
            joined = " ".join(str(item.get(k, "")).lower() for k in ("sku", "model", "brand", "category", "description"))
            if any(t in joined for t in terms):
                scored.append((1, item))

    # sort by score desc then limit
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [item for (_, item) in scored][:max_results]

    return {"status": "success", "results": results, "count": len(results)}


# CLI demo
if __name__ == "__main__":
    if not _INVENTORY_PATH.exists():
        demo = [
            {"sku": "XPS13-9310", "model": "Dell XPS 13 9310", "brand": "Dell", "category": "laptop", "description": "Intel i7, 16GB RAM"},
            {"sku": "TP-T14", "model": "Lenovo ThinkPad T14", "brand": "Lenovo", "category": "laptop", "description": "Ryzen 7, 16GB RAM"},
            {"sku": "HP-LJ1020", "model": "HP LaserJet 1020", "brand": "HP", "category": "printer", "description": "Monochrome laser printer"}
        ]
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _INVENTORY_PATH.open("w", encoding="utf-8") as f:
            json.dump(demo, f, indent=2, ensure_ascii=False)
    print(inventory_lookup("dell xps"))
