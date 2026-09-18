"""SQLite 会话记忆：会话、消息、路线图。第二阶段可平滑替换为 Redis/Postgres。"""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path) -> None:
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    goal TEXT,
                    nickname TEXT,
                    state TEXT DEFAULT '{}',
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    agent TEXT,
                    task_id TEXT,
                    content TEXT,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS roadmaps (
                    session_id TEXT PRIMARY KEY,
                    content TEXT,
                    created_at TEXT
                );
                """
            )
            self.conn.commit()

    # ---------- sessions ----------
    def create_session(self, goal: Optional[str] = None, nickname: Optional[str] = None) -> str:
        sid = uuid.uuid4().hex[:12]
        now = _now()
        with self._lock:
            self.conn.execute(
                "INSERT INTO sessions(session_id, goal, nickname, state, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?)",
                (sid, goal, nickname, "{}", now, now),
            )
            self.conn.commit()
        return sid

    def get_session(self, sid: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM sessions WHERE session_id=?", (sid,)).fetchone()
        return dict(row) if row else None

    def set_goal(self, sid: str, goal: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE sessions SET goal=?, updated_at=? WHERE session_id=?", (goal, _now(), sid)
            )
            self.conn.commit()

    def get_state(self, sid: str) -> dict[str, Any]:
        s = self.get_session(sid)
        return json.loads(s["state"] or "{}") if s else {}

    def update_state(self, sid: str, **kv) -> None:
        state = self.get_state(sid)
        state.update(kv)
        with self._lock:
            self.conn.execute(
                "UPDATE sessions SET state=?, updated_at=? WHERE session_id=?",
                (json.dumps(state, ensure_ascii=False), _now(), sid),
            )
            self.conn.commit()

    # ---------- messages ----------
    def add_message(self, sid, role, content, agent: Optional[str] = None, task_id: Optional[str] = None) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO messages(session_id, role, agent, task_id, content, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (sid, role, agent, task_id, content, _now()),
            )
            self.conn.commit()

    def list_messages(self, sid, agent: Optional[str] = None, limit: int = 20) -> list[dict]:
        sql = "SELECT * FROM messages WHERE session_id=?"
        args: list[Any] = [sid]
        if agent:
            sql += " AND agent=?"
            args.append(agent)
        sql += " ORDER BY id ASC"
        rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows][-limit:]

    # ---------- roadmap ----------
    def save_roadmap(self, sid: str, roadmap: dict[str, Any]) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO roadmaps(session_id, content, created_at) VALUES (?,?,?)",
                (sid, json.dumps(roadmap, ensure_ascii=False), _now()),
            )
            self.conn.commit()

    def get_roadmap(self, sid: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute("SELECT content FROM roadmaps WHERE session_id=?", (sid,)).fetchone()
        return json.loads(row["content"]) if row else None

    def set_task_status(self, sid: str, task_id: str, status: str) -> bool:
        roadmap = self.get_roadmap(sid)
        if not roadmap:
            return False
        hit = False
        for stage in roadmap.get("stages", []):
            for task in stage.get("tasks", []):
                if task.get("id") == task_id:
                    task["status"] = status
                    hit = True
        if hit:
            self.save_roadmap(sid, roadmap)
        return hit


store = Store(settings.data_dir / "xuniversity.db")
