"""SQLite persistence. Everything stays in one local file (default: ./data/benthoven.db)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DEFAULT_PREFS: dict[str, Any] = {
    "weekday_start": "16:00", "weekday_end": "21:00",
    "weekend_start": "09:00", "weekend_end": "15:00",
    "focus_start": "19:00", "focus_end": "21:00",
    "session_minutes": 45, "break_minutes": 10, "max_daily_minutes": 240,
    "energy": "normal", "engine": "ollama",
    "ollama_model": "llama3.2:3b", "ollama_url": "http://localhost:11434",
    "today_override": "",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY, filename TEXT, ocr_text TEXT, ocr_confidence REAL, created_at TEXT);
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY, doc_id INTEGER, task_name TEXT, subject TEXT, due_date TEXT,
  due_time TEXT DEFAULT '23:59', estimated_minutes INTEGER DEFAULT 60, task_type TEXT DEFAULT 'Other',
  importance INTEGER DEFAULT 3, source_text TEXT, confidence REAL, flags TEXT DEFAULT '[]',
  confirmed INTEGER DEFAULT 0, minutes_done INTEGER DEFAULT 0, status TEXT DEFAULT 'open',
  priority_override INTEGER DEFAULT 0, depends_on INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, task_id INTEGER, start TEXT, minutes INTEGER, goal TEXT,
  status TEXT DEFAULT 'planned', minutes_done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS commitments(
  id INTEGER PRIMARY KEY, date TEXT, start TEXT, end TEXT, label TEXT);
CREATE TABLE IF NOT EXISTS prefs(key TEXT PRIMARY KEY, value TEXT);
"""


def db_path() -> Path:
    return Path(os.environ.get("BENTHOVEN_DB", Path(__file__).resolve().parent.parent / "data" / "benthoven.db"))


def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------- prefs
def get_prefs() -> dict[str, Any]:
    with connect() as con:
        saved = {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT * FROM prefs")}
    return {**DEFAULT_PREFS, **saved}


def save_prefs(new: dict[str, Any]) -> None:
    with connect() as con:
        for k, v in new.items():
            if k in DEFAULT_PREFS:
                con.execute("INSERT OR REPLACE INTO prefs VALUES(?,?)", (k, json.dumps(v)))


# ------------------------------------------------------------ documents
def add_document(filename: str, text: str, conf: Optional[float]) -> int:
    with connect() as con:
        cur = con.execute("INSERT INTO documents(filename, ocr_text, ocr_confidence, created_at) VALUES(?,?,?,?)",
                          (filename, text, conf, datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


# ---------------------------------------------------------------- tasks
def add_pending_tasks(doc_id: int, tasks: list[dict]) -> None:
    with connect() as con:
        for t in tasks:
            con.execute(
                "INSERT INTO tasks(doc_id,task_name,subject,due_date,due_time,estimated_minutes,task_type,importance,"
                "source_text,confidence,flags,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (doc_id, t["task_name"], t.get("subject", ""), t["due_date"], t.get("due_time", "23:59"),
                 t["estimated_minutes"], t.get("task_type", "Other"), t.get("importance", 3), t.get("source_text", ""),
                 t["confidence"], json.dumps(t.get("flags", [])), datetime.now().isoformat(timespec="seconds")))


def add_manual_task(name: str, subject: str, due_date: str, minutes: int, task_type: str) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO tasks(task_name,subject,due_date,estimated_minutes,task_type,source_text,confidence,confirmed,created_at)"
            " VALUES(?,?,?,?,?,?,?,1,?)",
            (name, subject, due_date, minutes, task_type, "(entered manually)", 1.0, datetime.now().isoformat(timespec="seconds")))


def list_tasks(confirmed: Optional[bool] = None, open_only: bool = False) -> list[dict]:
    q, args = "SELECT t.*, d.ocr_text, d.filename FROM tasks t LEFT JOIN documents d ON d.id=t.doc_id WHERE 1=1", []
    if confirmed is not None:
        q += " AND t.confirmed=?"
        args.append(int(confirmed))
    if open_only:
        q += " AND t.status='open'"
    q += " ORDER BY t.due_date, t.id"
    with connect() as con:
        out = _rows(con.execute(q, args))
    for r in out:
        r["flags"] = json.loads(r["flags"] or "[]")
    return out


def update_task(task_id: int, **fields: Any) -> None:
    allowed = {"task_name", "subject", "due_date", "due_time", "estimated_minutes", "task_type", "importance",
               "confirmed", "minutes_done", "status", "priority_override", "depends_on"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    with connect() as con:
        con.execute(f"UPDATE tasks SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), task_id))


def delete_task(task_id: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM sessions WHERE task_id=?", (task_id,))
        con.execute("DELETE FROM tasks WHERE id=?", (task_id,))


# ---------------------------------------------------------- commitments
def list_commitments() -> list[dict]:
    with connect() as con:
        return _rows(con.execute("SELECT * FROM commitments ORDER BY date, start"))


def replace_commitments(rows: list[dict]) -> None:
    with connect() as con:
        con.execute("DELETE FROM commitments")
        for r in rows:
            con.execute("INSERT INTO commitments(date,start,end,label) VALUES(?,?,?,?)",
                        (r["date"], r["start"], r["end"], r.get("label", "")))


# ------------------------------------------------------------- sessions
def list_sessions(status: Optional[str] = None) -> list[dict]:
    q = ("SELECT s.*, t.task_name, t.subject, t.due_date FROM sessions s JOIN tasks t ON t.id=s.task_id")
    args: list = []
    if status:
        q += " WHERE s.status=?"
        args.append(status)
    q += " ORDER BY s.start"
    with connect() as con:
        return _rows(con.execute(q, args))


def replace_future_sessions(new_sessions: list[dict], now_iso: str) -> None:
    """Drop not-yet-started planned sessions and insert the new plan. History is kept."""
    with connect() as con:
        con.execute("DELETE FROM sessions WHERE status='planned' AND start>=?", (now_iso,))
        for s in new_sessions:
            con.execute("INSERT INTO sessions(task_id,start,minutes,goal) VALUES(?,?,?,?)",
                        (s["task_id"], s["start"], s["minutes"], s["goal"]))


def mark_past_planned_unfinished(now_iso: str) -> int:
    with connect() as con:
        cur = con.execute("UPDATE sessions SET status='unfinished' WHERE status='planned' AND "
                          "datetime(start, '+' || minutes || ' minutes') < datetime(?)", (now_iso,))
        return cur.rowcount


def update_session(session_id: int, status: str, minutes_done: int) -> None:
    with connect() as con:
        con.execute("UPDATE sessions SET status=?, minutes_done=? WHERE id=?", (status, minutes_done, session_id))
