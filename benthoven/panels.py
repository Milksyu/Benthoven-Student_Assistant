"""HTML for the dashboard panels. Pure functions: data in, HTML string out (easy to test)."""
from __future__ import annotations

import calendar
import html
import math
import zlib
from datetime import date, datetime, timedelta

from .scheduler import due_dt

e = html.escape


def _when(delta: timedelta) -> str:
    mins = int(delta.total_seconds() // 60)
    if mins < 0:
        return "overdue"
    if mins < 60:
        return f"in {mins} min"
    if mins < 24 * 60:
        return f"in {mins // 60} h"
    d = mins // (24 * 60)
    return f"in {d} day{'s' if d != 1 else ''}"


def _open(tasks: list[dict]) -> list[dict]:
    return [t for t in tasks if t["status"] == "open" and t.get("due_date")]


def _chip(text: str, kind: str = "") -> str:
    return f'<span class="bv-chip {kind}">{text}</span>'


def task_state(t: dict) -> str:
    """Notion-style board state: todo / progress / done / archived."""
    if t["status"] == "archived":
        return "archived"
    if t["status"] == "done":
        return "done"
    return "progress" if int(t.get("minutes_done") or 0) > 0 else "todo"


STATE_LABEL = {"todo": "Not started", "progress": "In progress", "done": "Done", "archived": "Archived"}
SUBJECT_COLORS = ["red", "blue", "yellow", "green", "purple", "orange", "pink", "brown"]


def _fmt_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{d:%B} {d.day}, {d.year}"


# ------------------------------------------------------------------ header
def header_html(now: datetime, tasks: list[dict], sessions: list[dict], pending: int, status: dict) -> str:
    open_t = sorted(_open(tasks), key=due_dt)
    if open_t:
        nxt = open_t[0]
        delta = due_dt(nxt) - now
        kind = "bad" if delta.total_seconds() < 0 else "warn" if delta < timedelta(days=2) else "good"
        deadline = _chip(f"\u23f0 Next deadline: <b>{e(nxt['task_name'])}</b> \u00b7 {_when(delta)}", kind)
    else:
        deadline = _chip("\u23f0 No open deadlines", "good")

    today = [s for s in sessions if s["status"] == "planned" and s["start"][:10] == now.date().isoformat()]
    mins = sum(s["minutes"] for s in today)
    load = _chip(f"\U0001f4da Today: {len(today)} session{'s' if len(today) != 1 else ''}, {mins // 60}h {mins % 60:02d}m", "")
    verify = _chip(f"\U0001f4dd {pending} to verify", "warn") if pending else ""
    chips = [
        _chip("OCR \u2705" if status["ocr"] else "OCR \u26a0\ufe0f not installed", "good" if status["ocr"] else "warn"),
        _chip("Local AI \u2705" if status["ai"] else "Local AI \u26a0\ufe0f not ready", "good" if status["ai"] else "warn"),
        _chip("\u2708\ufe0f Offline" if not status["net"] else "\U0001f310 Online (not needed)", "good" if not status["net"] else ""),
    ]
    return f"""
<div class="bv-cover"><span class="bv-seal"></span></div>
<div class="bv-icon" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
<div class="bv-title">Task Manager</div>
<div class="bv-sub">Benthoven Student Assistant \u00b7 {now:%A, %B} {now.day}, {now.year}</div>
<div class="bv-chips">{deadline}{load}{verify}{''.join(chips)}</div>
<hr class="bv-hr">"""


# ----------------------------------------------------------------- tracker
def _donut(counts: list[tuple[str, int, str]], total: int) -> str:
    """SVG ring: one arc per (label, count, colour). A faint ring is drawn when empty."""
    r, c = 44, 2 * math.pi * 44
    arcs = ""
    if total:
        used = [x for x in counts if x[1]]
        gap = 3 if len(used) > 1 else 0
        offset = 0.0
        for _, n, colour in used:
            seg = c * n / total
            arcs += (f'<circle cx="60" cy="60" r="{r}" fill="none" stroke="{colour}" stroke-width="14" '
                     f'stroke-dasharray="{max(seg - gap, 0.5):.2f} {c:.2f}" stroke-dashoffset="{-offset:.2f}" '
                     f'transform="rotate(-90 60 60)"/>')
            offset += seg
    else:
        arcs = f'<circle cx="60" cy="60" r="{r}" fill="none" stroke="#e3e2e0" stroke-width="14"/>'
    return f'<svg viewBox="0 0 120 120" class="bv-donut-svg" role="img" aria-label="{total} tasks">{arcs}</svg>'


def tracker_html(now: datetime, tasks: list[dict], sessions: list[dict]) -> str:
    live = [t for t in tasks if t["status"] != "archived"]
    states = [task_state(t) for t in live]
    counts = [("Not started", states.count("todo"), "#e3e2e0"),
              ("In progress", states.count("progress"), "#2f9be9"),
              ("Done", states.count("done"), "#5fbf8f")]
    legend = "".join(f'<li><i style="background:{col}"></i>{lab}</li>' for lab, _, col in counts)

    foot = '<div class="bv-chart-foot">Confirm some tasks to see them here.</div>'
    if live:
        total_min = sum(int(t["estimated_minutes"]) for t in live) or 1
        done_min = sum(int(t["estimated_minutes"]) if t["status"] == "done"
                       else min(int(t["minutes_done"]), int(t["estimated_minutes"])) for t in live)
        overdue = sum(1 for t in _open(live) if due_dt(t) < now)
        week_ago = (now - timedelta(days=7)).isoformat(timespec="minutes")
        week = sum(s["minutes_done"] for s in sessions
                   if s["status"] in ("completed", "partial") and s["start"] >= week_ago)
        foot = (f'<div class="bv-chart-foot"><b>{round(100 * done_min / total_min)}%</b> of planned work done<br>'
                f'<span class="{"bad" if overdue else ""}">{overdue} overdue</span> \u00b7 {week // 60}h{week % 60:02d} last 7 d</div>')
    return f"""
<div class="bv-chart">
  <div class="bv-chart-head">\u25d4 Chart</div>
  <div class="bv-chart-body">
    <div class="bv-donut">{_donut(counts, len(live))}<div class="bv-donut-num"><b>{len(live)}</b><span>Total</span></div></div>
    <ul class="bv-legend-list">{legend}</ul>
    {foot}
  </div>
</div>"""


# ------------------------------------------------------------- task table
def tasks_table_html(tasks: list[dict], view: str, now: datetime) -> str:
    """view: 'all' (everything not archived), 'completed' (done), 'archive' (archived)."""
    keep = {"all": lambda t: task_state(t) != "archived",
            "completed": lambda t: task_state(t) == "done",
            "archive": lambda t: task_state(t) == "archived"}[view]
    rows = ""
    for t in sorted((t for t in tasks if keep(t)), key=lambda t: (t.get("due_date") or "9999", t["id"])):
        state = task_state(t)
        subj = (t.get("subject") or "").strip()
        colour = SUBJECT_COLORS[zlib.crc32(subj.lower().encode()) % len(SUBJECT_COLORS)]
        pill = f'<span class="bv-pill {colour}" title="{e(subj)}">{e(subj)}</span>' if subj else '<span class="bv-muted">\u2014</span>'
        late = state in ("todo", "progress") and bool(t.get("due_date")) and due_dt(t) < now
        est = max(int(t["estimated_minutes"]), 1)
        done = est if state == "done" else min(int(t.get("minutes_done") or 0), est)
        pct = round(100 * done / est)
        rows += (
            f'<tr><td class="name">{e(t["task_name"])}</td><td>{pill}</td>'
            f'<td><span class="bv-status {state}"><i></i>{STATE_LABEL[state]}</span></td>'
            f'<td class="due{" late" if late else ""}">{_fmt_date(t.get("due_date", ""))}</td>'
            f'<td class="prog"><div class="bv-bar"><div style="width:{pct}%"></div></div>'
            f'<span>{done}/{est} min</span></td></tr>')
    if not rows:
        msg = {"all": "No tasks yet. Capture an announcement or add a task manually.",
               "completed": "Nothing completed yet.",
               "archive": "Nothing archived. Set a task's status to <b>archived</b> in My tasks."}[view]
        rows = f'<tr><td colspan="5" class="bv-empty">{msg}</td></tr>'
    return f"""
<div class="bv-tbl-wrap"><table class="bv-tbl">
  <thead><tr><th>\u25a4 Task Name</th><th>\u25ce Subject</th><th>\u2611 Status</th><th>\u25a6 Deadline</th><th>\u270e Progress</th></tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


# ---------------------------------------------------------------- calendar
def calendar_html(now: datetime, month_offset: int, tasks: list[dict], sessions: list[dict]) -> str:
    y, m = now.year, now.month + month_offset
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    dues: dict[date, list[str]] = {}
    for t in _open(tasks):
        dues.setdefault(date.fromisoformat(t["due_date"]), []).append(t["task_name"])
    study: dict[date, int] = {}
    for s in sessions:
        if s["status"] in ("planned", "completed", "partial"):
            d = date.fromisoformat(s["start"][:10])
            study[d] = study.get(d, 0) + s["minutes"]
    cal = calendar.Calendar(firstweekday=6)
    head = "".join(f"<th>{d}</th>" for d in ["S", "M", "T", "W", "T", "F", "S"])
    rows = ""
    for week in cal.monthdatescalendar(y, m):
        rows += "<tr>"
        for d in week:
            cls = ["other"] if d.month != m else []
            if d == now.date():
                cls.append("today")
            tip = []
            dots = ""
            if d in dues:
                dots += '<i class="due"></i>'
                tip += [f"Due: {n}" for n in dues[d]]
            if d in study:
                dots += '<i class="study"></i>'
                tip.append(f"{study[d]} min planned study")
            rows += f'<td class="{" ".join(cls)}" title="{e(chr(10).join(tip))}"><span>{d.day}</span><div>{dots}</div></td>'
        rows += "</tr>"
    return f"""
<div class="bv-card">
  <div class="bv-card-title">Calendar · {calendar.month_name[m]} {y}</div>
  <table class="bv-cal"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>
  <div class="bv-legend"><i class="due"></i> deadline <i class="study"></i> study session</div>
</div>"""


# ----------------------------------------------------------------- up next
def upnext_html(now: datetime, tasks: list[dict], sessions: list[dict]) -> str:
    now_iso = now.isoformat(timespec="minutes")
    upcoming = [s for s in sessions if s["status"] == "planned" and s["start"] >= now_iso][:3]
    body = ""
    if upcoming:
        first = upcoming[0]
        st = datetime.fromisoformat(first["start"])
        body += (f'<div class="bv-next"><div class="bv-next-time">{st:%a %H:%M} · {_when(st - now)}</div>'
                 f'<div class="bv-next-task">{e(first["task_name"])} <small>{first["minutes"]} min</small></div>'
                 f'<div class="bv-next-goal">{e(first["goal"])}</div></div>')
        for s in upcoming[1:]:
            st = datetime.fromisoformat(s["start"])
            body += f'<div class="bv-mini">{st:%a %H:%M} · {e(s["task_name"])} ({s["minutes"]} min)</div>'
    else:
        body += '<div class="bv-empty">No upcoming sessions. Generate a plan to fill your week.</div>'
    soon = sorted(_open(tasks), key=due_dt)[:3]
    if soon:
        body += '<div class="bv-sep">Due soon</div>'
        for t in soon:
            delta = due_dt(t) - now
            kind = "bad" if delta.total_seconds() < 0 else "warn" if delta < timedelta(days=2) else ""
            body += (f'<div class="bv-mini"><span class="bv-dot {kind}"></span>{e(t["task_name"])} '
                     f'<span class="bv-muted">· {due_dt(t):%b %d} · {_when(delta)}</span></div>')
    return f'<div class="bv-card"><div class="bv-card-title">Up next</div>{body}</div>'
