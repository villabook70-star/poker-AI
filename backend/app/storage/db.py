"""SQLite persistence (stdlib ``sqlite3``): opponent profiles, imported sessions and hands."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Dict, List, Optional

from ..analysis.profiles import OpponentProfile

DEFAULT_PATH = os.environ.get("POKERMIND_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "pokermind.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    name TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    source TEXT,
    created_at REAL NOT NULL,
    hands INTEGER DEFAULT 0,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS hands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    hand_id TEXT,
    history TEXT NOT NULL,
    analysis TEXT
);
"""


class Database:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(SCHEMA)

    # profiles -----------------------------------------------------------
    def save_profile(self, prof: OpponentProfile) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT OR REPLACE INTO profiles(name, data, updated_at) VALUES (?, ?, ?)",
                               (prof.name, json.dumps(prof.to_storage()), time.time()))

    def get_profile(self, name: str) -> Optional[OpponentProfile]:
        row = self._conn.execute("SELECT data FROM profiles WHERE name = ?", (name,)).fetchone()
        return OpponentProfile.from_dict(json.loads(row["data"])) if row else None

    def list_profiles(self) -> List[OpponentProfile]:
        rows = self._conn.execute("SELECT data FROM profiles ORDER BY name").fetchall()
        return [OpponentProfile.from_dict(json.loads(r["data"])) for r in rows]

    def all_profiles(self) -> Dict[str, OpponentProfile]:
        return {p.name: p for p in self.list_profiles()}

    def delete_profile(self, name: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM profiles WHERE name = ?", (name,))
            return cur.rowcount > 0

    # sessions / hands ----------------------------------------------------
    def create_session(self, name: str, source: str, hands: List[dict], analyses: List[dict], summary: dict) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("INSERT INTO sessions(name, source, created_at, hands, summary) VALUES (?, ?, ?, ?, ?)",
                                     (name, source, time.time(), len(hands), json.dumps(summary)))
            sid = cur.lastrowid
            self._conn.executemany("INSERT INTO hands(session_id, hand_id, history, analysis) VALUES (?, ?, ?, ?)",
                                   [(sid, h.get("hand_id"), json.dumps(h), json.dumps(a)) for h, a in zip(hands, analyses)])
            return int(sid)

    def list_sessions(self) -> List[dict]:
        rows = self._conn.execute("SELECT id, name, source, created_at, hands, summary FROM sessions ORDER BY id DESC").fetchall()
        return [{"id": r["id"], "name": r["name"], "source": r["source"], "created_at": r["created_at"],
                 "hands": r["hands"], "summary": json.loads(r["summary"] or "{}")} for r in rows]

    def get_session(self, sid: int) -> Optional[dict]:
        row = self._conn.execute("SELECT id, name, source, created_at, hands, summary FROM sessions WHERE id = ?", (sid,)).fetchone()
        if not row:
            return None
        hands = self._conn.execute("SELECT id, hand_id, history, analysis FROM hands WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
        return {"id": row["id"], "name": row["name"], "source": row["source"], "created_at": row["created_at"],
                "summary": json.loads(row["summary"] or "{}"),
                "hands": [{"id": h["id"], "hand_id": h["hand_id"], "history": json.loads(h["history"]),
                           "analysis": json.loads(h["analysis"] or "{}")} for h in hands]}

    def delete_session(self, sid: int) -> bool:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM hands WHERE session_id = ?", (sid,))
            cur = self._conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
            return cur.rowcount > 0
