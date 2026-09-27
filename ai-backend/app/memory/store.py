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
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    kind TEXT,
                    key TEXT,
                    content TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(session_id, kind, key)
                );
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    agent TEXT,
                    content TEXT,
                    up_to_id INTEGER,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT,
                    ref_key TEXT,
                    model TEXT,
                    vector TEXT,
                    dim INTEGER,
                    created_at TEXT,
                    UNIQUE(scope, ref_key, model)
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

    # ---------- long-term memories ----------
    def remember(
        self, sid: Optional[str], kind: str, key: str, content: str
    ) -> None:
        """写入/更新一条记忆（按 session+kind+key 唯一）。sid=None 表示全局记忆。"""
        now = _now()
        with self._lock:
            self.conn.execute(
                "INSERT INTO memories(session_id, kind, key, content, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?)"
                " ON CONFLICT(session_id, kind, key) DO UPDATE SET content=excluded.content,"
                " updated_at=excluded.updated_at",
                (sid, kind, key, content, now, now),
            )
            self.conn.commit()

    def recall(
        self,
        sid: Optional[str] = None,
        kind: Optional[str] = None,
        key: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """读取记忆。默认同时返回该会话记忆与全局记忆（全局在前）。"""
        clauses, args = [], []
        if sid is not None:
            clauses.append("(session_id=? OR session_id IS NULL)")
            args.append(sid)
        if kind:
            clauses.append("kind=?")
            args.append(kind)
        if key:
            clauses.append("key=?")
            args.append(key)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM memories{where} ORDER BY session_id IS NULL DESC, id ASC", args
        ).fetchall()
        return [dict(r) for r in rows]

    def forget(self, sid: Optional[str], kind: str, key: str) -> bool:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM memories WHERE session_id IS ? AND kind=? AND key=?",
                (sid, kind, key),
            )
            self.conn.commit()
            return cur.rowcount > 0

    # ---------- conversation summaries ----------
    def save_summary(self, sid: str, agent: str, content: str, up_to_id: int) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO summaries(session_id, agent, content, up_to_id, created_at)"
                " VALUES (?,?,?,?,?)",
                (sid, agent, content, up_to_id, _now()),
            )
            self.conn.commit()

    def get_summary(self, sid: str, agent: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM summaries WHERE session_id=? AND agent=? ORDER BY id DESC LIMIT 1",
            (sid, agent),
        ).fetchone()
        return dict(row) if row else None

    # ---------- embedding cache（向量 RAG） ----------
    def get_cached_embeddings(
        self, scope: str, ref_keys: list[str], model: str
    ) -> dict[str, list[float]]:
        if not ref_keys:
            return {}
        placeholders = ",".join("?" * len(ref_keys))
        rows = self.conn.execute(
            f"SELECT ref_key, vector, dim FROM embedding_cache"
            f" WHERE scope=? AND model=? AND ref_key IN ({placeholders})",
            [scope, model, *ref_keys],
        ).fetchall()
        out = {}
        for row in rows:
            try:
                out[row["ref_key"]] = json.loads(row["vector"])
            except ValueError:
                continue
        return out

    def put_cached_embeddings(
        self, scope: str, model: str, vectors: dict[str, list[float]]
    ) -> None:
        now = _now()
        with self._lock:
            for ref_key, vector in vectors.items():
                self.conn.execute(
                    "INSERT OR REPLACE INTO embedding_cache"
                    "(scope, ref_key, model, vector, dim, created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    [scope, ref_key, model, json.dumps(vector, ensure_ascii=False), len(vector), now],
                )
            self.conn.commit()


store = Store(settings.data_dir / "xuniversity.db")
