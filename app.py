"""Benthoven: offline academic planner. Run with:  python app.py

Local-first: binds to 127.0.0.1 only, stores data in ./data/benthoven.db, calls only
localhost services (Tesseract binary, Ollama on localhost:11434).
"""
from __future__ import annotations

import html
import os
import socket
import tempfile
import time
from datetime import date, datetime

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")   # no telemetry

import gradio as gr
import pandas as pd

from benthoven import storage as db
from benthoven.dates import parse_due_date
from benthoven.extractor import extract_tasks, ollama_status
from benthoven.ics import sessions_to_ics
from benthoven.narrator import narrate
from benthoven.ocr import read_document, tesseract_available
from benthoven.panels import calendar_html, header_html, tracker_html, upnext_html
from benthoven.scheduler import diff_plans, schedule, summarize

TASK_TYPES = ["Assignment", "Quiz", "Exam", "Project", "Other"]
VERIFY_COLS = ["id", "confirm", "delete", "task_name", "subject", "due_date", "estimated_minutes",
               "task_type", "importance", "confidence", "needs attention"]
TASK_COLS = ["id", "delete", "task_name", "subject", "due_date", "estimated_minutes", "minutes_done",
             "importance", "priority_override", "depends_on", "status"]


# ------------------------------------------------------------------ helpers
def _now() -> datetime:
    prefs = db.get_prefs()
    n = datetime.now()
    ov = (prefs.get("today_override") or "").strip()
    if ov:
        try:
            d = date.fromisoformat(ov)
            return n.replace(year=d.year, month=d.month, day=d.day)
        except ValueError:
            pass
    return n


def _int(x, default=0) -> int:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() == "":
            return default
        return int(float(x))
    except (ValueError, TypeError):
        return default


def _str(x) -> str:
    return "" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x).strip()


def _resolve_date(text: str, today: date):
    """Accept ISO or natural dates, but only if they are unambiguous."""
    text = _str(text)
    try:
        return date.fromisoformat(text), ""
    except ValueError:
        pass
    r = parse_due_date(text, today)
    if r.value and r.status == "ok":
        return r.value, ""
    return None, r.note or "Could not read this date. Use YYYY-MM-DD."


# ------------------------------------------------------------ table builders
def verify_df() -> pd.DataFrame:
    rows = [[t["id"], False, False, t["task_name"], t["subject"], t["due_date"], t["estimated_minutes"],
             t["task_type"], t["importance"], t["confidence"], " | ".join(t["flags"])]
            for t in db.list_tasks(confirmed=False)]
    return pd.DataFrame(rows, columns=VERIFY_COLS)


def tasks_df() -> pd.DataFrame:
    rows = [[t["id"], False, t["task_name"], t["subject"], t["due_date"], t["estimated_minutes"], t["minutes_done"],
             t["importance"], t["priority_override"], t["depends_on"] or 0, t["status"]]
            for t in db.list_tasks(confirmed=True)]
    return pd.DataFrame(rows, columns=TASK_COLS)


def timetable_df() -> pd.DataFrame:
    rows = []
    for s in db.list_sessions("planned"):
        st = datetime.fromisoformat(s["start"])
        end = st.replace() + pd.Timedelta(minutes=s["minutes"])
        rows.append([f"{st:%Y-%m-%d}", f"{st:%a}", f"{st:%H:%M}", f"{end:%H:%M}", s["task_name"],
                     s["subject"], s["minutes"], s["goal"], s["id"]])
    return pd.DataFrame(rows, columns=["Date", "Day", "Start", "End", "Task", "Subject", "Minutes", "Goal", "Session"])


def ranking_df(ranking: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([[i + 1, r["task_name"], r["subject"], r["score"], r["reason"]] for i, r in enumerate(ranking)],
                        columns=["#", "Task", "Subject", "Priority", "Why it needs attention"])


def today_df(now: datetime) -> pd.DataFrame:
    sessions = [s for s in db.list_sessions("planned") if s["start"][:10] == now.date().isoformat()]
    return pd.DataFrame([[s["start"][11:16], s["minutes"], s["task_name"], s["goal"]] for s in sessions],
                        columns=["Start", "Minutes", "Task", "Goal"])


def commitments_df() -> pd.DataFrame:
    return pd.DataFrame([[c["date"], c["start"], c["end"], c["label"]] for c in db.list_commitments()],
                        columns=["date (YYYY-MM-DD)", "start (HH:MM)", "end (HH:MM)", "label"])


def session_choices() -> list[str]:
    out = []
    for s in db.list_sessions("planned"):
        st = datetime.fromisoformat(s["start"])
        out.append(f"#{s['id']} · {st:%a %b %d %H:%M} · {s['task_name']} ({s['minutes']} min)")
    return out


# -------------------------------------------------------------- capture tab
def do_extract(files, pasted):
    prefs, now = db.get_prefs(), _now()
    sources, notes = [], []
    for f in files or []:
        path = getattr(f, "name", f)
        try:
            text, conf = read_document(path)
            sources.append((os.path.basename(path), text, conf))
        except Exception as e:
            notes.append(f"**{os.path.basename(path)}**: could not read ({e})")
    if _str(pasted):
        sources.append(("pasted text", pasted, None))
    if not sources and not notes:
        return "Upload a file or paste some text first.", verify_df(), ""
    last_text = ""
    for name, text, conf in sources:
        existing = db.list_tasks()
        tasks, engine = extract_tasks(text, now.date(), prefs["engine"], prefs["ollama_model"], prefs["ollama_url"], conf, existing)
        doc_id = db.add_document(name, text, conf)
        db.add_pending_tasks(doc_id, tasks)
        ocr = f", OCR confidence {conf:.0f}%" if conf is not None else ""
        if tasks:
            review = sum(1 for t in tasks if t["needs_review"])
            notes.append(f"**{name}**: {len(tasks)} task(s) found by *{engine}*{ocr}. {review} need your attention. Go to **2. Verify**.")
        else:
            notes.append(f"**{name}**: no deadlines found{ocr}. Check the detected text below, or add the task manually.")
        last_text = text
    return "\n\n".join(notes), verify_df(), last_text


def add_manual(name, subject, due, minutes, ttype):
    if not _str(name):
        return "Enter a task name.", tasks_df()
    d, err = _resolve_date(due, _now().date())
    if not d:
        return f"Due date problem: {err}", tasks_df()
    db.add_manual_task(_str(name), _str(subject), d.isoformat(), max(_int(minutes, 60), 5), ttype)
    return f"Added **{name}** (due {d:%a %b %d}). It is already confirmed.", tasks_df()


# --------------------------------------------------------------- verify tab
def show_evidence(df: pd.DataFrame, evt: gr.SelectData):
    try:
        row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        tid = _int(df.iloc[row]["id"])
    except Exception:
        return "Select a row to see its evidence."
    t = next((x for x in db.list_tasks() if x["id"] == tid), None)
    if not t:
        return "Task not found."
    ocr, src = html.escape(t.get("ocr_text") or ""), html.escape(t.get("source_text") or "")
    if src and src in ocr:
        shown = ocr.replace(src, f"<mark>{src}</mark>", 1)
        note = ""
    else:
        shown = ocr or "(no document text stored)"
        note = f"\n\n> Evidence text: `{src}` (not found verbatim in the document text)." if src else ""
    flags = "".join(f"\n- {html.escape(f)}" for f in t["flags"]) or "\n- None"
    return (f"**{t['task_name']}**, from *{t.get('filename') or 'manual entry'}*, confidence **{t['confidence']}**\n\n"
            f"Flags:{flags}{note}\n\n<div style='white-space:pre-wrap;border:1px solid #8884;padding:8px;border-radius:6px'>{shown}</div>")


def save_verified(df: pd.DataFrame):
    if df is None or df.empty:
        return "Nothing to save.", verify_df(), tasks_df()
    today, saved, errors = _now().date(), 0, []
    for _, r in df.iterrows():
        tid = _int(r["id"])
        if bool(r["delete"]):
            db.delete_task(tid)
            continue
        d, err = _resolve_date(r["due_date"], today)
        fields = dict(task_name=_str(r["task_name"]), subject=_str(r["subject"]),
                      estimated_minutes=max(_int(r["estimated_minutes"], 60), 5), task_type=_str(r["task_type"]) or "Other",
                      importance=min(max(_int(r["importance"], 3), 1), 5))
        if d:
            fields["due_date"] = d.isoformat()
        if bool(r["confirm"]):
            if not d:
                errors.append(f"{_str(r['task_name'])}: {err}")
                db.update_task(tid, **fields)
                continue
            fields["confirmed"] = 1
            saved += 1
        db.update_task(tid, **fields)
    msg = f"Confirmed {saved} task(s)."
    if errors:
        msg += "\n\nNot confirmed (fix the date first):\n" + "\n".join(f"- {e}" for e in errors)
    return msg, verify_df(), tasks_df()


def save_tasks(df: pd.DataFrame):
    today, errors = _now().date(), []
    for _, r in df.iterrows():
        tid = _int(r["id"])
        if bool(r["delete"]):
            db.delete_task(tid)
            continue
        d, err = _resolve_date(r["due_date"], today)
        if not d:
            errors.append(f"{_str(r['task_name'])}: {err}")
            continue
        db.update_task(tid, task_name=_str(r["task_name"]), subject=_str(r["subject"]), due_date=d.isoformat(),
                       estimated_minutes=max(_int(r["estimated_minutes"], 60), 5), minutes_done=max(_int(r["minutes_done"]), 0),
                       importance=min(max(_int(r["importance"], 3), 1), 5),
                       priority_override=min(max(_int(r["priority_override"]), 0), 5),
                       depends_on=_int(r["depends_on"]) or None, status=_str(r["status"]) or "open")
    return ("Saved." if not errors else "Saved, except:\n" + "\n".join(f"- {e}" for e in errors)), tasks_df()


# ----------------------------------------------------------------- plan tab
def _render_plan(plan: dict, now: datetime, diff: list[str] | None, use_ai: bool):
    names = {t["id"]: t["task_name"] for t in db.list_tasks()}
    prefs = db.get_prefs()
    text = summarize(plan, names, now)
    if use_ai:
        text = narrate(text, prefs["ollama_model"], prefs["ollama_url"])
    conflicts = ""
    for c in plan["conflicts"]:
        conflicts += f"### ⚠️ {c['message']}\nRealistic options:\n" + "\n".join(f"- {o}" for o in c["options"]) + "\n\n"
    changes = ("**What changed:**\n" + "\n".join(f"- {d}" for d in diff)) if diff else ""
    return text, conflicts, changes, ranking_df(plan["ranking"]), timetable_df(), today_df(now), gr.update(choices=session_choices(), value=None)


def make_plan(use_ai: bool = False, prefix: str = ""):
    prefs, now = db.get_prefs(), _now()
    now_iso = now.isoformat(timespec="minutes")
    missed = db.mark_past_planned_unfinished(now_iso)
    tasks = db.list_tasks(confirmed=True, open_only=True)
    done_today = sum(s["minutes_done"] for s in db.list_sessions() if s["start"][:10] == now.date().isoformat()
                     and s["status"] in ("completed", "partial"))
    old_future = [s for s in db.list_sessions("planned") if s["start"] >= now_iso]
    plan = schedule(tasks, prefs, db.list_commitments(), now, done_today)
    db.replace_future_sessions(plan["sessions"], now_iso)
    names = {t["id"]: t["task_name"] for t in tasks}
    diff = diff_plans(old_future, plan["sessions"], names) if old_future else None
    if missed:
        diff = ([f"{missed} earlier session(s) passed without being marked and were counted as unfinished."] + (diff or []))
    out = list(_render_plan(plan, now, diff, use_ai))
    if prefix:
        out[0] = prefix + "\n\n" + out[0]
    return tuple(out)


def export_ics():
    sessions = db.list_sessions("planned")
    if not sessions:
        return None
    path = os.path.join(tempfile.mkdtemp(), "benthoven_schedule.ics")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(sessions_to_ics(sessions))
    return path


# ------------------------------------------------------------- progress tab
def update_progress(choice, status, minutes_done, extra, finished, use_ai):
    if not choice:
        return (("Pick a session first.",) + (gr.update(),) * 6)
    sid = int(choice.split("·")[0].strip().lstrip("#"))
    s = next(x for x in db.list_sessions() if x["id"] == sid)
    task = next(t for t in db.list_tasks() if t["id"] == s["task_id"])
    if status.startswith("Completed"):
        st, done = "completed", s["minutes"]
    elif status.startswith("Partly"):
        st, done = "partial", min(max(_int(minutes_done), 0), s["minutes"])
    else:
        st, done = "unfinished", 0
    db.update_session(sid, st, done)
    est = task["estimated_minutes"] + max(_int(extra), 0)
    total_done = task["minutes_done"] + done
    new_status = "done" if (finished or total_done >= est) else "open"
    db.update_task(task["id"], minutes_done=total_done, estimated_minutes=est, status=new_status)
    note = {"completed": "Nice work. ", "partial": "Good progress. ", "unfinished": "That's okay, plans change. "}[st]
    prefix = f"{note}Here is the updated plan for **{task['task_name']}** and everything else."
    return make_plan(use_ai, prefix)


# ------------------------------------------------------------- settings tab
PREF_FIELDS = ["weekday_start", "weekday_end", "weekend_start", "weekend_end", "focus_start", "focus_end",
               "session_minutes", "break_minutes", "max_daily_minutes", "energy", "engine", "ollama_model", "today_override"]


def load_prefs():
    p = db.get_prefs()
    return [p[k] for k in PREF_FIELDS]


def save_settings(*vals):
    *pref_vals, comm = vals
    new = dict(zip(PREF_FIELDS, pref_vals))
    for k in ("session_minutes", "break_minutes", "max_daily_minutes"):
        new[k] = max(_int(new[k], db.DEFAULT_PREFS[k]), 5)
    for k in ("weekday_start", "weekday_end", "weekend_start", "weekend_end", "focus_start", "focus_end"):
        try:
            datetime.strptime(_str(new[k]), "%H:%M")
            new[k] = _str(new[k])
        except ValueError:
            return f"'{new[k]}' is not a valid HH:MM time for {k}.", commitments_df()
    db.save_prefs(new)
    rows, bad = [], []
    for _, r in comm.iterrows():
        vals = [_str(v) for v in r.tolist()]
        if not any(vals):
            continue
        try:
            date.fromisoformat(vals[0]); datetime.strptime(vals[1], "%H:%M"); datetime.strptime(vals[2], "%H:%M")
            rows.append(dict(date=vals[0], start=vals[1], end=vals[2], label=vals[3]))
        except ValueError:
            bad.append(", ".join(vals))
    db.replace_commitments(rows)
    msg = "Settings saved. Regenerate your plan to apply them."
    if bad:
        msg += "\n\nSkipped invalid commitment row(s):\n" + "\n".join(f"- {b}" for b in bad)
    return msg, commitments_df()


# -------------------------------------------------------------- privacy tab
def internet_reachable() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=1).close()
        return True
    except OSError:
        return False


def privacy_status() -> str:
    p = db.get_prefs()
    ol = ollama_status(p["ollama_url"], p["ollama_model"])
    ok = lambda b: "✅" if b else "⚠️"
    net = internet_reachable()
    return f"""
| Component | Status |
|---|---|
| Tesseract OCR (local binary) | {ok(tesseract_available())} {'installed' if tesseract_available() else 'not found: images cannot be read, but pasted text still works'} |
| Ollama server (localhost) | {ok(ol['running'])} {'running' if ol['running'] else 'not running: using the rule-based extractor'} |
| Model `{p['ollama_model']}` | {ok(bool(ol['model_ready']))} {'ready' if ol['model_ready'] else 'not pulled yet (run: ollama pull ' + p['ollama_model'] + ')'} |
| Scheduling engine | ✅ plain Python, fully local |
| Data location | `{db.db_path()}` |
| Internet right now | {'🌐 reachable (Benthoven does not need it)' if net else '✈️ not reachable: offline mode, everything still works'} |

**What stays on this computer:** uploaded documents, OCR text, extracted tasks, schedules, and settings.
Benthoven only talks to `localhost`. Nothing is sent anywhere unless you press **Export .ics**.

For the offline demo: install everything and pull the model first, then disconnect Wi-Fi and refresh this panel.
"""


# ---------------------------------------------------------- dashboard panels
_status_cache: dict = {"t": 0.0, "v": None}


def _status() -> dict:
    """Cheap, cached local-status probe for the header chips (refreshed every 20 s)."""
    if time.time() - _status_cache["t"] > 20 or _status_cache["v"] is None:
        p = db.get_prefs()
        ol = ollama_status(p["ollama_url"], p["ollama_model"])
        _status_cache.update(t=time.time(), v={"ocr": tesseract_available(),
                                               "ai": bool(ol["running"] and ol["model_ready"]),
                                               "net": internet_reachable()})
    return _status_cache["v"]


def refresh_panels(month_offset: int = 0):
    now = _now()
    tasks = db.list_tasks(confirmed=True)
    sessions = db.list_sessions()
    pending = len(db.list_tasks(confirmed=False))
    return (header_html(now, tasks, sessions, pending, _status()),
            tracker_html(now, tasks, sessions),
            calendar_html(now, int(month_offset or 0), tasks, sessions),
            upnext_html(now, tasks, sessions))


CSS = """
.gradio-container{max-width:1500px !important}
.bv-header{display:flex;flex-wrap:wrap;align-items:center;gap:14px;padding:12px 18px;border-radius:14px;
  background:linear-gradient(135deg,#3b2a6d,#5b3fa8);color:#fff}
.bv-brand{display:flex;align-items:center;gap:10px}.bv-logo{font-size:30px}
.bv-title{font-size:22px;font-weight:700;letter-spacing:.5px}.bv-sub{font-size:12px;opacity:.8}
.bv-chips{display:flex;flex-wrap:wrap;gap:8px;flex:1}.bv-chips.right{justify-content:flex-end;flex:0 1 auto}
.bv-header,.bv-header *{color:#fff !important}
.bv-chip{background:rgba(255,255,255,.16);padding:5px 11px;border-radius:999px;font-size:12.5px;white-space:nowrap}
.bv-chip.good{background:rgba(80,200,120,.30)}.bv-chip.warn{background:rgba(255,190,60,.38)}.bv-chip.bad{background:rgba(255,90,90,.45)}
.bv-card{border:1px solid var(--border-color-primary,#8884);border-radius:14px;padding:14px;
  background:var(--background-fill-secondary,#f6f6f9);color:var(--body-text-color,#222)}
.bv-card-title{font-weight:700;margin-bottom:8px;font-size:14px;text-transform:uppercase;letter-spacing:.6px;opacity:.75}
.bv-big{font-size:34px;font-weight:700}.bv-big small{font-size:12px;font-weight:400;opacity:.7;margin-left:6px}
.bv-bar{height:7px;border-radius:99px;background:var(--border-color-primary,#8884);overflow:hidden}
.bv-bar.big{height:10px;margin:6px 0 10px}.bv-bar div{height:100%;background:linear-gradient(90deg,#7c5cff,#46c28e)}
.bv-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:6px 0 12px;text-align:center}
.bv-stats b{display:block;font-size:17px}.bv-stats span{font-size:11px;opacity:.7}.bv-stats .bad b{color:#e5484d}
.bv-row{margin:7px 0}.bv-rowtop{display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:3px;gap:8px}
.bv-cal{width:100%;border-collapse:collapse;text-align:center;table-layout:fixed}
.bv-cal,.bv-cal th,.bv-cal td{border:none !important}
.bv-cal th{font-size:11px;opacity:.6;padding:3px 0}.bv-cal td{height:38px;font-size:12.5px;vertical-align:top;padding-top:3px;border-radius:8px}
.bv-cal td.other{opacity:.35}.bv-cal td.today span{background:#5b3fa8;color:#fff;border-radius:99px;padding:1px 6px}
.bv-cal td div{display:flex;justify-content:center;gap:3px;margin-top:2px;min-height:7px}
.bv-cal i,.bv-legend i{display:inline-block;width:7px;height:7px;border-radius:99px}
i.due{background:#e5484d}i.study{background:#4c8dff}.bv-legend{font-size:11.5px;opacity:.75;margin-top:6px}
.bv-next{padding:10px;border-radius:10px;background:rgba(91,63,168,.14);margin-bottom:8px}
.bv-next-time{font-size:12px;opacity:.75}.bv-next-task{font-weight:700;font-size:16px;margin:2px 0}
.bv-next-task small{font-weight:400;opacity:.7}.bv-next-goal{font-size:12.5px;opacity:.85}
.bv-mini{font-size:12.5px;padding:4px 0}.bv-sep{margin:10px 0 4px;font-size:11px;text-transform:uppercase;opacity:.6;letter-spacing:.6px}
.bv-dot{display:inline-block;width:8px;height:8px;border-radius:99px;background:#46c28e;margin-right:6px}
.bv-dot.warn{background:#f5a524}.bv-dot.bad{background:#e5484d}.bv-muted{opacity:.65}.bv-empty{font-size:13px;opacity:.7;padding:6px 0}
.bv-actions-title{font-weight:700;font-size:14px;text-transform:uppercase;letter-spacing:.6px;opacity:.75;margin:2px 0 6px}
.bv-main{border:1px solid var(--border-color-primary,#8884);border-radius:14px;padding:16px;min-height:640px}
.bv-calnav{flex-wrap:nowrap !important;gap:6px}.bv-calnav button{min-width:0 !important}
.bv-nav button{justify-content:flex-start !important;text-align:left}
"""

VIEWS = ["capture", "verify", "tasks", "plan", "progress", "settings", "privacy"]
NAV = {"capture": "📥 Capture", "verify": "✅ Verify", "tasks": "📋 My tasks", "plan": "🗓️ Plan",
       "progress": "📈 Progress", "settings": "⚙️ Settings", "privacy": "🔒 Privacy"}


# ---------------------------------------------------------------------- UI
def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Benthoven") as demo:
        cal_offset = gr.State(0)
        header = gr.HTML()

        with gr.Row(equal_height=False):
            # ---------------- left column: tracker + actions
            with gr.Column(scale=3, min_width=240):
                tracker = gr.HTML()
                with gr.Group(elem_classes="bv-nav"):
                    gr.HTML('<div class="bv-actions-title" style="padding:10px 12px 0">Actions</div>')
                    nav_btns = {v: gr.Button(NAV[v], variant="primary" if v == "capture" else "secondary") for v in VIEWS}
                    gr.HTML('<div class="bv-actions-title" style="padding:10px 12px 0">Quick actions</div>')
                    replan_btn = gr.Button("⚡ Replan now")
                    ics_quick = gr.Button("📅 Export .ics")

            # ---------------- centre: main window
            with gr.Column(scale=8, min_width=480, elem_classes="bv-main"):
                # 1 Capture
                with gr.Column(visible=True) as v_capture:
                    gr.Markdown("### Capture\nAdd assignment photos, screenshots, text files, or paste an announcement.")
                    files = gr.File(label="Assignment photos, screenshots, or .txt/.md files", file_count="multiple",
                                    file_types=[".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".txt", ".md"])
                    pasted = gr.Textbox(label="...or paste announcement text", lines=5)
                    extract_btn = gr.Button("Extract tasks", variant="primary")
                    extract_msg = gr.Markdown()
                    with gr.Accordion("Text detected in the document (OCR output, kept separate from AI results)", open=False):
                        ocr_box = gr.Textbox(lines=8, interactive=False, show_label=False)
                    with gr.Accordion("Add a task manually", open=False):
                        with gr.Row():
                            m_name = gr.Textbox(label="Task name")
                            m_subject = gr.Textbox(label="Subject")
                            m_due = gr.Textbox(label="Due date (YYYY-MM-DD)")
                        with gr.Row():
                            m_min = gr.Number(label="Estimated minutes", value=60, precision=0)
                            m_type = gr.Dropdown(TASK_TYPES, value="Assignment", label="Type")
                        m_btn = gr.Button("Add task")
                        m_msg = gr.Markdown()

                # 2 Verify
                with gr.Column(visible=False) as v_verify:
                    gr.Markdown("### Verify\nCheck each AI-proposed task. **Click a row** to see the evidence from the original document. "
                                "Tick **confirm** to add it to your planner. Nothing enters the schedule until you confirm.")
                    v_df = gr.Dataframe(value=verify_df, headers=VERIFY_COLS, interactive=True, wrap=True, show_search=False,
                                        column_widths=[50, 85, 80, 200, 150, 110, 90, 100, 90, 90, 320],
                                        datatype=["number", "bool", "bool", "str", "str", "str", "number", "str", "number", "number", "str"])
                    evidence = gr.Markdown("Select a row to see its evidence.")
                    v_btn = gr.Button("Save changes / confirm ticked tasks", variant="primary")
                    v_msg = gr.Markdown()

                # 3 My tasks
                with gr.Column(visible=False) as v_tasks:
                    gr.Markdown("### My tasks\nConfirmed tasks. Set **priority_override** (1-5) to override the engine, or **depends_on** (a task id) to order work.")
                    t_df = gr.Dataframe(value=tasks_df, headers=TASK_COLS, interactive=True, wrap=True, show_search=False,
                                        column_widths=[50, 80, 220, 150, 110, 90, 90, 90, 110, 100, 80],
                                        datatype=["number", "bool", "str", "str", "str", "number", "number", "number", "number", "number", "str"])
                    t_btn = gr.Button("Save task changes")
                    t_msg = gr.Markdown()

                # 4 Plan
                with gr.Column(visible=False) as v_plan:
                    gr.Markdown("### Plan")
                    with gr.Row():
                        plan_btn = gr.Button("Generate / refresh plan", variant="primary")
                        use_ai = gr.Checkbox(label="Explain in friendlier words with local AI (optional)", value=False)
                    summary = gr.Markdown()
                    conflicts = gr.Markdown()
                    changes = gr.Markdown()
                    gr.Markdown("#### Today")
                    today_t = gr.Dataframe(interactive=False, wrap=True, show_search=False)
                    gr.Markdown("#### Priority ranking")
                    rank_t = gr.Dataframe(interactive=False, wrap=True, show_search=False)
                    gr.Markdown("#### Weekly timetable")
                    time_t = gr.Dataframe(value=timetable_df, interactive=False, wrap=True, show_search=False)
                    ics_file = gr.File(label="Calendar file (.ics)", interactive=False)

                # 5 Progress
                with gr.Column(visible=False) as v_progress:
                    gr.Markdown("### Progress\nMark a session, and Benthoven replans the rest. Deadlines never change; only the schedule does.")
                    s_pick = gr.Dropdown(choices=session_choices(), label="Session", interactive=True)
                    s_status = gr.Radio(["Completed", "Partly done", "Couldn't do it"], value="Completed", label="How did it go?")
                    with gr.Row():
                        s_min = gr.Number(label="Minutes actually done (if partly)", value=0, precision=0)
                        s_extra = gr.Number(label="Extra minutes the task still needs", value=0, precision=0)
                        s_fin = gr.Checkbox(label="This task is fully finished")
                    s_btn = gr.Button("Update and replan", variant="primary")
                    s_msg = gr.Markdown()

                # 6 Settings
                with gr.Column(visible=False) as v_settings:
                    gr.Markdown("### Settings")
                    with gr.Row():
                        wk_s, wk_e = gr.Textbox(label="Weekday study from"), gr.Textbox(label="Weekday study until (sleep boundary)")
                        we_s, we_e = gr.Textbox(label="Weekend study from"), gr.Textbox(label="Weekend study until")
                    with gr.Row():
                        f_s, f_e = gr.Textbox(label="High-focus window from"), gr.Textbox(label="High-focus window until")
                        energy = gr.Dropdown(["low", "normal", "high"], label="Energy today")
                    with gr.Row():
                        sess = gr.Number(label="Session length (min)", precision=0)
                        brk = gr.Number(label="Break (min)", precision=0)
                        cap = gr.Number(label="Max study per day (min)", precision=0)
                    with gr.Row():
                        engine = gr.Dropdown(["auto", "ollama", "rules"], label="Extraction engine")
                        model = gr.Textbox(label="Ollama model")
                        override = gr.Textbox(label="Pretend today is (YYYY-MM-DD, for demos; blank = real date)")
                    gr.Markdown("**Fixed commitments** (classes, clubs, family time). Study sessions are never placed over them.")
                    comm_df = gr.Dataframe(value=commitments_df, headers=["date (YYYY-MM-DD)", "start (HH:MM)", "end (HH:MM)", "label"],
                                           interactive=True, row_count=(3, "dynamic"), show_search=False)
                    st_btn = gr.Button("Save settings", variant="primary")
                    st_msg = gr.Markdown()

                # 7 Privacy
                with gr.Column(visible=False) as v_privacy:
                    gr.Markdown("### Privacy & offline status")
                    p_md = gr.Markdown(privacy_status)
                    p_btn = gr.Button("Refresh status")

            # ---------------- right column: calendar + up next
            with gr.Column(scale=4, min_width=280):
                calendar_p = gr.HTML()
                with gr.Row(elem_classes="bv-calnav"):
                    cal_prev = gr.Button("◀", size="sm")
                    cal_today = gr.Button("Today", size="sm")
                    cal_next = gr.Button("▶", size="sm")
                upnext = gr.HTML()

        # ------------------------------------------------------------ wiring
        views = [v_capture, v_verify, v_tasks, v_plan, v_progress, v_settings, v_privacy]
        panels = [header, tracker, calendar_p, upnext]
        nav_list = [nav_btns[v] for v in VIEWS]

        def switch(name: str):
            return ([gr.update(visible=(v == name)) for v in VIEWS]
                    + [gr.update(variant="primary" if v == name else "secondary") for v in VIEWS])

        for name, btn in nav_btns.items():
            btn.click(lambda n=name: switch(n), None, views + nav_list)

        def after(evt):
            """Refresh the side panels after any action that changes data."""
            return evt.then(refresh_panels, [cal_offset], panels)

        after(extract_btn.click(do_extract, [files, pasted], [extract_msg, v_df, ocr_box]))
        after(m_btn.click(add_manual, [m_name, m_subject, m_due, m_min, m_type], [m_msg, t_df]))
        v_df.select(show_evidence, [v_df], [evidence])
        after(v_btn.click(save_verified, [v_df], [v_msg, v_df, t_df]))
        after(t_btn.click(save_tasks, [t_df], [t_msg, t_df]))
        plan_outputs = [summary, conflicts, changes, rank_t, time_t, today_t, s_pick]
        after(plan_btn.click(make_plan, [use_ai], plan_outputs))
        after(replan_btn.click(make_plan, [use_ai], plan_outputs).then(lambda: switch("plan"), None, views + nav_list))
        ics_quick.click(export_ics, None, [ics_file]).then(lambda: switch("plan"), None, views + nav_list)
        after(s_btn.click(update_progress, [s_pick, s_status, s_min, s_extra, s_fin, use_ai], plan_outputs))
        pref_comps = [wk_s, wk_e, we_s, we_e, f_s, f_e, sess, brk, cap, energy, engine, model, override]
        after(st_btn.click(save_settings, pref_comps + [comm_df], [st_msg, comm_df]))
        p_btn.click(privacy_status, None, [p_md])

        def move_cal(offset, step):
            new = 0 if step == 0 else offset + step
            return (new,) + refresh_panels(new)

        cal_outs = [cal_offset] + panels
        cal_prev.click(lambda o: move_cal(o, -1), [cal_offset], cal_outs)
        cal_next.click(lambda o: move_cal(o, 1), [cal_offset], cal_outs)
        cal_today.click(lambda o: move_cal(o, 0), [cal_offset], cal_outs)

        demo.load(load_prefs, None, pref_comps)
        demo.load(lambda: (verify_df(), tasks_df(), commitments_df(), gr.update(choices=session_choices())), None,
                  [v_df, t_df, comm_df, s_pick])
        demo.load(refresh_panels, [cal_offset], panels)
    return demo


if __name__ == "__main__":
    build_ui().launch(server_name="127.0.0.1", server_port=int(os.environ.get("PORT", 7860)),
                      inbrowser=False, css=CSS)
