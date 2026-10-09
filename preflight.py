"""Run before a demo:  python preflight.py

Checks everything Benthoven needs and exercises the real pipeline on the sample
announcements. Exits with code 1 if something required is broken.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["BENTHOVEN_DB"] = str(Path(tempfile.mkdtemp()) / "preflight.db")   # never touches your real data

failed = False


def line(ok: bool | None, msg: str, required: bool = True) -> None:
    global failed
    icon = "PASS" if ok else ("WARN" if ok is None or not required else "FAIL")
    if not ok and required:
        failed = True
    print(f"[{icon}] {msg}")


print(f"Python {sys.version.split()[0]}")
for mod in ("gradio", "pandas", "pytesseract", "PIL", "requests"):
    try:
        __import__(mod)
        line(True, f"package '{mod}' installed")
    except ImportError:
        line(False, f"package '{mod}' missing -> pip install -r requirements.txt")

from benthoven import storage as db
from benthoven.extractor import extract_tasks, ollama_selftest, ollama_status
from benthoven.ocr import tesseract_available
from benthoven.scheduler import schedule

line(tesseract_available(), "Tesseract OCR found (needed for photos)", required=False)
prefs = db.get_prefs()
st = ollama_status(prefs["ollama_url"], prefs["ollama_model"])
line(st["running"], "Ollama server running on localhost")
line(bool(st["model_ready"]), f"model '{prefs['ollama_model']}' installed")
if st["running"] and st["model_ready"]:
    r = ollama_selftest(prefs["ollama_url"], prefs["ollama_model"])
    line(r["ok"], f"local inference works ({r.get('seconds', '?')} s)" if r["ok"] else r["error"])
else:
    print("      -> Benthoven needs local AI: install Ollama, then run: ollama pull " + prefs["ollama_model"])

today = date(2026, 10, 9)
tasks_found = []
for f in sorted((ROOT / "sample_docs").glob("*.txt")):
    try:
        tasks, engine = extract_tasks(f.read_text(encoding="utf-8"), today, prefs["ollama_model"], prefs["ollama_url"])
    except RuntimeError as exc:
        line(False, f"{f.name}: {exc}")
        break
    tasks_found += tasks
    print(f"      {f.name}: {len(tasks)} task(s) via {engine}")
if not failed:
    line(len(tasks_found) >= 4, f"extraction found {len(tasks_found)} tasks from the samples")

if tasks_found:
    from datetime import datetime
    rows = [dict(id=i + 1, task_name=t["task_name"], subject=t["subject"], due_date=t["due_date"], due_time="23:59",
                 estimated_minutes=t["estimated_minutes"], minutes_done=0, importance=t["importance"],
                 priority_override=0, depends_on=None, task_type=t["task_type"]) for i, t in enumerate(tasks_found) if t["due_date"]]
    plan = schedule(rows, prefs, [], datetime(2026, 10, 9, 15, 0))
    line(bool(plan["sessions"]), f"scheduler produced {len(plan['sessions'])} study sessions")

print("\nRESULT:", "NOT READY (fix FAIL items)" if failed else "ready (check any WARN items before judging)")
sys.exit(1 if failed else 0)
