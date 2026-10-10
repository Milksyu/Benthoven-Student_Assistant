"""Local web server (standard library only): serves static/index.html and a small JSON API.

Binds to 127.0.0.1, stores data in SQLite, talks only to localhost services (Ollama, Tesseract).
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from . import storage as db
from .extractor import extract_tasks, ollama_status
from .ics import sessions_to_ics
from .ocr import read_document, tesseract_available
from .scheduler import schedule

PAGE = Path(__file__).resolve().parent.parent / "static" / "index.html"


def _clean(tasks: list[dict]) -> list[dict]:
    return [{k: v for k, v in t.items() if k != "ocr_text"} for t in tasks]


def state() -> dict:
    return {"today": datetime.now().date().isoformat(), "tasks": _clean(db.list_tasks(confirmed=True)),
            "pending": _clean(db.list_tasks(confirmed=False)), "sessions": db.list_sessions("planned")}


def status() -> dict:
    p = db.get_prefs()
    ol = ollama_status(p["ollama_url"], p["ollama_model"])
    return {"ai": bool(ol["running"] and ol["model_ready"]), "model": p["ollama_model"], "ocr": tesseract_available()}


def extract(q: dict, body: bytes) -> dict:
    p, name = db.get_prefs(), q.get("name", ["pasted text"])[0]
    if "file" in q:
        fd, path = tempfile.mkstemp(suffix=Path(name).suffix)
        os.write(fd, body)
        os.close(fd)
        try:
            text, conf = read_document(path)
        finally:
            os.remove(path)
    else:
        text, conf = body.decode("utf-8", "replace"), None
    tasks, label = extract_tasks(text, datetime.now().date(), p["ollama_model"], p["ollama_url"], conf, db.list_tasks())
    db.add_pending_tasks(db.add_document(name, text, conf), tasks)
    return {"found": len(tasks), "engine": label}


def add_task(d: dict) -> dict:
    name, due = (d.get("name") or "").strip(), (d.get("due") or "").strip()
    if not name or not due:
        raise ValueError("A task needs a name and a due date.")
    datetime.strptime(due, "%Y-%m-%d")
    db.add_manual_task(name, (d.get("subject") or "").strip(), due, max(int(d.get("minutes") or 60), 5), "Assignment")
    return {}


def task_action(tid: int, d: dict) -> dict:
    t = next((x for x in db.list_tasks() if x["id"] == tid), None)
    if not t:
        raise ValueError("Task not found.")
    a, est = d.get("action"), max(int(t["estimated_minutes"]), 1)
    if a == "delete":
        db.delete_task(tid)
    elif a == "confirm":
        if not t["due_date"]:
            raise ValueError("Set a due date before confirming.")
        db.update_task(tid, confirmed=1)
    elif a == "edit":
        if d.get("due_date"):
            datetime.strptime(d["due_date"], "%Y-%m-%d")
        db.update_task(tid, **{k: d[k] for k in ("task_name", "subject", "due_date") if k in d})
    elif a == "status":
        s = d.get("state")
        if s == "todo":
            db.update_task(tid, status="open", minutes_done=0)
        elif s == "progress":
            md = t["minutes_done"] if 0 < t["minutes_done"] < est else max(est // 2, 1)
            db.update_task(tid, status="open", minutes_done=md)
        elif s == "done":
            db.update_task(tid, status="done", minutes_done=est)
        elif s == "archived":
            db.update_task(tid, status="archived")
        else:
            raise ValueError("Unknown status.")
    else:
        raise ValueError("Unknown action.")
    return {}


SYSTEM = (
    "You are Benthoven's study assistant, running privately on the student's own computer. Help the student learn: "
    "explain ideas step by step in simple language with short examples, quiz them one question at a time and wait for "
    "their answer, make flashcards or summaries from notes they paste, and help them decide what to study first. "
    "Keep answers concise. If you are not sure about a fact, say so instead of guessing. Do not write graded "
    "assignments for the student; guide them to do the work themselves. Reply in the language the student writes in.\n\n"
)


def chat_context(now: datetime, tasks: list[dict]) -> str:
    """Compact, local-only picture of the student's workload for the assistant (no document text)."""
    open_t = sorted((t for t in tasks if t["status"] == "open" and t["due_date"]), key=lambda t: t["due_date"])[:15]
    head = f"Today is {now:%A, %B} {now.day}, {now.year}.\n"
    if not open_t:
        return head + "The student has no open tasks yet."
    rows = "\n".join(f"- {t['task_name']} ({t['subject'] or 'no subject'}), due {t['due_date']}, "
                      f"about {t['estimated_minutes']} min, {t['minutes_done']} min done" for t in open_t)
    return head + "The student's open tasks, soonest first:\n" + rows


def chat_messages(d: dict) -> list[dict]:
    """Validate the browser's chat history and prepend the system prompt."""
    msgs = []
    for m in (d.get("messages") or [])[-12:]:
        role, content = m.get("role"), str(m.get("content", ""))[:6000]
        if role in ("user", "assistant") and content.strip():
            msgs.append({"role": role, "content": content})
    if not msgs or msgs[-1]["role"] != "user":
        raise ValueError("Type a message first.")
    context = chat_context(datetime.now(), db.list_tasks(confirmed=True))
    return [{"role": "system", "content": SYSTEM + context}] + msgs


def plan() -> dict:
    p, now = db.get_prefs(), datetime.now()
    iso = now.isoformat(timespec="minutes")
    db.mark_past_planned_unfinished(iso)
    done_today = sum(s["minutes_done"] for s in db.list_sessions() if s["start"][:10] == iso[:10]
                     and s["status"] in ("completed", "partial"))
    res = schedule(db.list_tasks(confirmed=True, open_only=True), p, db.list_commitments(), now, done_today)
    db.replace_future_sessions(res["sessions"], iso)
    return {"conflicts": [c["message"] for c in res["conflicts"]], "sessions": db.list_sessions("planned")}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    def _send(self, code: int, body, ctype: str = "application/json", headers: dict | None = None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/":
                return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/state":
                return self._send(200, state())
            if path == "/api/status":
                return self._send(200, status())
            if path == "/api/ics":
                sessions = db.list_sessions("planned")
                if not sessions:
                    return self._send(404, {"error": "Generate a plan first."})
                return self._send(200, sessions_to_ics(sessions).encode(), "text/calendar",
                                  {"Content-Disposition": 'attachment; filename="benthoven_schedule.ics"'})
            self._send(404, {"error": "Not found."})
        except Exception as exc:
            self._send(500, {"error": str(exc)})

    def _chat(self, data: dict):
        """Stream the local model's reply as plain text. Errors before streaming become JSON 400s."""
        p, msgs = db.get_prefs(), chat_messages(data)
        ol = ollama_status(p["ollama_url"], p["ollama_model"])
        if not ol["running"]:
            raise RuntimeError("Ollama is not running. Start Ollama and try again.")
        if not ol["model_ready"]:
            raise RuntimeError(f"Model '{p['ollama_model']}' is missing. Run: ollama pull {p['ollama_model']}")
        r = requests.post(f"{p['ollama_url']}/api/chat", stream=True, timeout=(5, 300),
                          json={"model": p["ollama_model"], "messages": msgs, "stream": True, "options": {"temperature": 0.4}})
        r.raise_for_status()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()                    # HTTP/1.0: the stream ends when the connection closes
        try:
            for line in r.iter_lines():
                piece = json.loads(line).get("message", {}).get("content", "") if line else ""
                if piece:
                    self.wfile.write(piece.encode())
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):   # the student pressed Stop
            pass
        except (requests.RequestException, ValueError):
            self.wfile.write("\n\n[The local AI stopped unexpectedly. Please try again.]".encode())
        finally:
            r.close()

    def do_POST(self):
        u = urlparse(self.path)
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):   # block other websites
            return self._send(403, {"error": "Cross-site request refused."})
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            data = json.loads(body or b"{}") if u.path != "/api/extract" else None
            if u.path == "/api/extract":
                return self._send(200, extract(parse_qs(u.query), body))
            if u.path == "/api/task":
                return self._send(200, add_task(data))
            if u.path.startswith("/api/task/"):
                return self._send(200, task_action(int(u.path.rsplit("/", 1)[1]), data))
            if u.path == "/api/plan":
                return self._send(200, plan())
            if u.path == "/api/chat":
                return self._chat(data)
            self._send(404, {"error": "Not found."})
        except (RuntimeError, ValueError, OSError, requests.RequestException) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})


def serve(port: int = 7860) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Benthoven is running at http://127.0.0.1:{port}  (press Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
