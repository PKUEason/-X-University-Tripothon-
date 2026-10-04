"""Persist handoffs between spaces; these are plans, not proof of execution."""
import json
from app.memory.store import store


def read_artifact(sid, key):
    rows = store.recall(sid, kind="note", key=key)
    rows = [r for r in rows if r.get("session_id") == sid]
    if not rows:
        return None
    try:
        return json.loads(rows[-1]["content"])
    except (ValueError, TypeError):
        return None


def save_artifact(sid, key, value):
    store.remember(sid, "note", key, json.dumps(value, ensure_ascii=False))


def context(sid):
    return json.dumps({key: read_artifact(sid, key) for key in
        ("library_result", "professor_result", "lab_result")}, ensure_ascii=False)[:14000]
