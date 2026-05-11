"""State manager — tracks which days have been published per account."""

import os
import json
from datetime import datetime
from typing import Optional

STATE_FILE = os.environ.get(
    "STATE_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state.json"),
)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {
        "version": 1,
        "last_publish": None,
        "publications": {},
    }


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def mark_published(state: dict, day: int, account: str, post_id: str, success: bool, error: Optional[str] = None) -> None:
    pubs = state.setdefault("publications", {})
    day_key = str(day)
    day_entry = pubs.setdefault(day_key, {})
    day_entry[account] = {
        "success": success,
        "post_id": post_id if success else None,
        "error": error,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if success:
        state["last_publish"] = datetime.utcnow().isoformat() + "Z"


def get_published_days(state: dict, account: str) -> set:
    pubs = state.get("publications", {})
    return {
        int(day_key)
        for day_key, accounts in pubs.items()
        if accounts.get(account, {}).get("success")
    }


def get_missing_days(state: dict, all_days: list, accounts: list) -> dict:
    return {
        acc: sorted(set(all_days) - get_published_days(state, acc))
        for acc in accounts
    }
