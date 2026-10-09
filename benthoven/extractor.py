"""Structured task extraction (Stage 2).

Two engines share one output format:
  * ollama - required local LLM that proposes tasks as JSON; its output is then
             re-validated by code (dates re-parsed, evidence checked against OCR text).
Rule-based extraction is intentionally not a fallback: local AI is a project requirement.

AI proposes; code validates; the student confirms.
"""
from __future__ import annotations

import difflib
import json
import re
from datetime import date
from typing import Optional

import requests

from .dates import parse_due_date, parse_due_time

SUBJECTS = [
    "General Mathematics", "Mathematics", "Math", "Calculus", "Statistics", "Physics", "Chemistry",
    "Biology", "Science", "English", "Filipino", "History", "Economics", "Programming",
    "Computer Science", "Research", "Practical Research", "Literature", "Philosophy", "Psychology",
]
TYPE_PATTERNS = [
    ("Exam", r"\b(exam|midterm|finals?|periodical)\b"),
    ("Quiz", r"\bquiz(?:zes)?\b|\blong test\b|\bunit test\b|\btest\b"),
    ("Project", r"\b(project|thesis|capstone|portfolio|presentation|report|paper)\b"),
    ("Assignment", r"\b(assignment|problem set|homework|worksheet|activity|essay|lab|reading)\b"),
]
DEFAULT_MINUTES = {"Exam": 180, "Quiz": 90, "Project": 300, "Assignment": 60, "Other": 60}
TRIGGERS = re.compile(
    r"\b(due|deadline|submit|submission|pass|passing|on or before|until|quiz|exam|test|"
    r"midterm|bring|presentation|defense)\b", re.I)
TASK_NAME_RE = re.compile(
    r"\b((?:Problem Set|Quiz|Long Test|Exam|Midterm Exam|Project|Assignment|Homework|Worksheet|"
    r"Activity|Lab Report|Essay|Reading|Presentation|Research Paper)"
    r"(?:\s*(?:#|No\.?|Number)\s*\w+|\s+\d+[A-Za-z]?)?)\b",
    re.I)
BARE_TYPES = {"quiz", "exam", "midterm exam", "long test", "essay", "project", "assignment", "homework",
              "worksheet", "activity", "reading", "presentation", "lab report", "research paper"}
LABELS = {
    "subject": re.compile(r"^\s*(subject|course|class)\s*[:\-]\s*(.+)$", re.I),
    "task": re.compile(r"^\s*(requirement|task|assignment|activity|title|project)\s*[:\-]\s*(.+)$", re.I),
    "due": re.compile(r"^\s*(due(?:\s*date)?|deadline|submission(?:\s*date)?|date)\s*[:\-]\s*(.+)$", re.I),
    "minutes": re.compile(r"^\s*(estimated(?:\s*work)?\s*time|est\.?\s*time|duration)\s*[:\-]\s*(.+)$", re.I),
    "weight": re.compile(r"^\s*(weight|grade weight|points)\s*[:\-]\s*(.+)$", re.I),
}


# ----------------------------------------------------------------- helpers
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def guess_type(text: str) -> str:
    for name, pat in TYPE_PATTERNS:
        if re.search(pat, text, re.I):
            return name
    return "Other"


def guess_subject(text: str) -> str:
    low = text.lower()
    for s in sorted(SUBJECTS, key=len, reverse=True):
        if s.lower() in low:
            return s
    return ""


def parse_minutes(text: str) -> Optional[int]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h)\b", text, re.I)
    if m:
        return int(float(m[1]) * 60)
    m = re.search(r"(\d+)\s*(minutes?|mins?|m)\b", text, re.I)
    if m:
        return int(m[1])
    m = re.fullmatch(r"\s*(\d+)\s*", text)
    return int(m[1]) if m else None


def parse_weight(text: str) -> Optional[int]:
    """Map a grade weight (e.g. 20%) to an importance score 1-5."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not m:
        return None
    w = float(m[1])
    return 5 if w >= 30 else 4 if w >= 20 else 3 if w >= 10 else 2 if w >= 5 else 1


def _clean_name(sentence: str, subject: str = "") -> tuple[str, bool]:
    """Return (name, used_heuristic_fallback)."""
    m = TASK_NAME_RE.search(sentence)
    if m:
        name = re.sub(r"\s+", " ", m[1]).strip().title()
        if subject and name.lower() in BARE_TYPES:
            name = f"{subject} {name}"
        return name, False
    words = re.sub(r"[^\w\s#]", "", sentence).split()
    return " ".join(words[:6]).title() or "Untitled task", True


def _sentences(block: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n", block)
    return [p.strip() for p in parts if p.strip()]


def _finalize(rec: dict, today: date, ocr_conf: Optional[float], dup_pool: list[dict]) -> dict:
    """Common validation applied to every proposed task, whatever engine made it."""
    flags: list[str] = list(rec.get("flags", []))
    conf = rec.get("confidence", 0.9)
    d = parse_due_date(rec.pop("due_text", "") or rec.get("source_text", ""), today)
    rec["due_date"] = d.value.isoformat() if d.value else ""
    if d.status != "ok":
        flags.append(d.note or "Due date needs review.")
        conf = min(conf, 0.5 if d.status == "review" else 0.3)
    elif d.note:
        flags.append(d.note)
    if not rec.get("subject"):
        flags.append("Subject not found.")
        conf -= 0.15
    if ocr_conf is not None and ocr_conf < 70:
        flags.append(f"Low OCR confidence ({ocr_conf:.0f}%). Check against the image.")
        conf -= 0.2
    rec["due_time"] = parse_due_time(rec.get("source_text", ""))
    if not rec.get("estimated_minutes"):
        rec["estimated_minutes"] = DEFAULT_MINUTES.get(rec.get("task_type", "Other"), 60)
        flags.append("Estimated time is a default; adjust it.")
    for other in dup_pool:
        same = difflib.SequenceMatcher(None, _norm(rec["task_name"]), _norm(other["task_name"])).ratio()
        if same > 0.85 and other.get("due_date") == rec["due_date"]:
            flags.append(f"Possible duplicate of '{other['task_name']}'.")
            conf -= 0.1
            break
    rec["confidence"] = round(max(0.05, min(conf, 0.99)), 2)
    rec["flags"] = flags
    rec["needs_review"] = bool(flags) and (rec["confidence"] < 0.75 or d.status != "ok")
    return rec


# ------------------------------------------------------------ rule engine
def _scan(text: str) -> tuple[list[dict], list[str]]:
    """Group 'Label: value' lines into records; everything else is free prose.

    Line-oriented on purpose: OCR often inserts blank lines between lines of the same card.
    """
    records: list[dict] = []
    prose: list[str] = []
    cur: dict = {}
    carry_subject = ""

    def flush():
        nonlocal cur
        if cur.get("task") and cur.get("due"):
            records.append(cur)
        cur = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        hit = None
        for key, rx in LABELS.items():
            m = rx.match(line)
            if m:
                hit = (key, m[2].strip())
                break
        if not hit:
            prose.append(line)
            continue
        key, val = hit
        if key == "subject":
            if cur.get("task") or cur.get("due"):
                flush()
            carry_subject = val
            cur["subject"] = val
        elif key == "task":
            if cur.get("task"):
                flush()
                cur["subject"] = carry_subject
            cur["task"] = val
        else:
            cur[key] = val
            if key == "due":
                cur["due_line"] = line
    flush()
    for r in records:
        r.setdefault("subject", carry_subject)
    return records, prose


def extract_with_rules(text: str, today: date, ocr_conf: Optional[float] = None,
                       existing: Optional[list[dict]] = None) -> list[dict]:
    tasks: list[dict] = []
    records, prose = _scan(text)
    for lab in records:
        rec = {
            "task_name": lab["task"], "subject": lab.get("subject", ""),
            "task_type": guess_type(lab["task"]), "due_text": lab["due"],
            "estimated_minutes": parse_minutes(lab.get("minutes", "")),
            "importance": parse_weight(lab.get("weight", "")) or 3,
            "source_text": lab["due_line"], "confidence": 0.9, "flags": [],
        }
        tasks.append(_finalize(rec, today, ocr_conf, (existing or []) + tasks))

    carry_subject = records[-1].get("subject", "") if records else ""
    for sent in _sentences("\n".join(prose)):
        if not TRIGGERS.search(sent) or parse_due_date(sent, today).status == "none":
            continue
        subject = guess_subject(sent) or carry_subject
        name, fallback = _clean_name(sent, subject)
        rec = {
            "task_name": name, "subject": subject, "task_type": guess_type(sent), "due_text": sent,
            "estimated_minutes": parse_minutes(sent) if re.search(r"\b(minutes?|mins?|hours?|hrs?)\b", sent, re.I) else None,
            "importance": 3, "source_text": sent, "confidence": 0.7 if fallback else 0.85,
            "flags": ["Task name was guessed from the sentence."] if fallback else [],
        }
        tasks.append(_finalize(rec, today, ocr_conf, (existing or []) + tasks))
    return tasks


# ---------------------------------------------------------- Ollama engine
SCHEMA = {
    "type": "object",
    "properties": {"tasks": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "task_name": {"type": "string"}, "subject": {"type": "string"},
            "due_date_text": {"type": "string"}, "estimated_minutes": {"type": "integer"},
            "task_type": {"type": "string", "enum": ["Assignment", "Quiz", "Exam", "Project", "Other"]},
            "source_text": {"type": "string"},
        },
        "required": ["task_name", "subject", "due_date_text", "task_type", "source_text"],
    }}},
    "required": ["tasks"],
}


def ollama_status(url: str = "http://localhost:11434", model: str = "") -> dict:
    """Is the local Ollama server up, and is the chosen model pulled?"""
    try:
        r = requests.get(f"{url}/api/tags", timeout=2)
        names = [m["name"] for m in r.json().get("models", [])]
        return {"running": True, "models": names, "model_ready": any(n.startswith(model) for n in names) if model else None}
    except Exception:
        return {"running": False, "models": [], "model_ready": False}


def extract_with_ollama(text: str, today: date, model: str, url: str,
                        ocr_conf: Optional[float] = None, existing: Optional[list[dict]] = None) -> list[dict]:
    prompt = (
        "You extract academic requirements from OCR text of a school announcement.\n"
        "Rules: copy values from the text only. Never invent or convert dates: put the date exactly as "
        "written in due_date_text (empty string if none). source_text must be an exact sentence/line "
        "copied from the text. Skip anything that is not an assignment, quiz, exam, or project.\n"
        f"Today is {today.isoformat()} (for context only).\n\nTEXT:\n{text}"
    )
    r = requests.post(
        f"{url}/api/chat",
        json={"model": model, "stream": False, "format": SCHEMA, "options": {"temperature": 0},
              "messages": [{"role": "user", "content": prompt}]},
        timeout=180,
    )
    r.raise_for_status()
    proposed = json.loads(r.json()["message"]["content"]).get("tasks", [])

    norm_text = _norm(text)
    out: list[dict] = []
    for p in proposed:
        flags: list[str] = []
        conf = 0.85
        src = (p.get("source_text") or "").strip()
        # Evidence check: the quoted source must really exist in the OCR text.
        if src and _norm(src) in norm_text:
            pass
        else:
            best = max(_sentences(text) or [""], key=lambda s: difflib.SequenceMatcher(None, _norm(s), _norm(src)).ratio())
            ratio = difflib.SequenceMatcher(None, _norm(best), _norm(src)).ratio()
            if ratio >= 0.6:
                src = best
                flags.append("Evidence was re-anchored to the closest line in the document.")
                conf -= 0.1
            else:
                flags.append("AI evidence not found in the document. Verify against the image.")
                conf = 0.35
                src = best if best else src
        due_text = p.get("due_date_text", "")
        if due_text and _norm(due_text) not in norm_text:
            flags.append("Date text from AI does not appear verbatim in the document.")
            conf = min(conf, 0.4)
        rec = {
            "task_name": p.get("task_name", "Untitled task"), "subject": p.get("subject", ""),
            "task_type": p.get("task_type", "Other"), "due_text": due_text or src,
            "estimated_minutes": p.get("estimated_minutes") or parse_minutes(src),
            "importance": 3, "source_text": src, "confidence": conf, "flags": flags,
        }
        out.append(_finalize(rec, today, ocr_conf, (existing or []) + out))
    return out


def extract_tasks(text: str, today: date, engine: str = "auto", model: str = "llama3.2:3b",
                  url: str = "http://localhost:11434", ocr_conf: Optional[float] = None,
                  existing: Optional[list[dict]] = None) -> tuple[list[dict], str]:
    """Extract tasks with the required local model; never silently use a rules fallback."""
    st = ollama_status(url, model)
    if not st["running"]:
        raise RuntimeError("Ollama is not running. Start Ollama and try again.")
    if not st["model_ready"]:
        raise RuntimeError(f"Required model '{model}' is missing. Run: ollama pull {model}")
    try:
        return extract_with_ollama(text, today, model, url, ocr_conf, existing), f"Local LLM ({model})"
    except Exception as exc:
        raise RuntimeError(f"Local model request failed ({type(exc).__name__}). Check Ollama and try again.") from exc
