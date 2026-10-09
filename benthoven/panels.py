"""HTML for the dashboard panels. Pure functions: data in, HTML string out (easy to test)."""
from __future__ import annotations

import calendar
import html
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


# ------------------------------------------------------------------ header
def header_html(now: datetime, tasks: list[dict], sessions: list[dict], pending: int, status: dict) -> str:
    open_t = sorted(_open(tasks), key=due_dt)
    if open_t:
        nxt = open_t[0]
        delta = due_dt(nxt) - now
        kind = "bad" if delta.total_seconds() < 0 else "warn" if delta < timedelta(days=2) else "good"
        deadline = _chip(f"⏰ Next deadline: <b>{e(nxt['task_name'])}</b> · {_when(delta)}", kind)
    else:
        deadline = _chip("⏰ No open deadlines", "good")

    today = [s for s in sessions if s["status"] == "planned" and s["start"][:10] == now.date().isoformat()]
    mins = sum(s["minutes"] for s in today)
    load = _chip(f"📚 Today: {len(today)} session{'s' if len(today) != 1 else ''}, {mins // 60}h {mins % 60:02d}m", "")
    verify = _chip(f"📝 {pending} to verify", "warn") if pending else ""
    chips = [
        _chip("Local OCR ✅" if status["ocr"] else "Local OCR ⚠️ install requirements", "good" if status["ocr"] else "warn"),
        _chip("Local AI ✅" if status["ai"] else "Local AI ⚠️ unavailable", "good" if status["ai"] else "warn"),
        _chip("✈️ Offline" if not status["net"] else "🌐 Online (not needed)", "good" if not status["net"] else ""),
    ]
    return f"""
<div class="bv-header">
  <div class="bv-brand"><span class="bv-logo">🎼</span><div><div class="bv-title">Benthoven</div>
  <div class="bv-sub">{now:%A, %B %d, %Y}</div></div></div>
  <div class="bv-chips">{deadline}{load}{verify}</div>
  <div class="bv-chips right">{''.join(chips)}</div>
</div>"""


# ----------------------------------------------------------------- tracker
def tracker_html(now: datetime, tasks: list[dict], sessions: list[dict]) -> str:
    """Render the compact status chart and study progress for the dashboard sidebar."""
    total = len(tasks)
    done_count = sum(1 for t in tasks if t["status"] == "done")
    in_progress_count = sum(
        1 for t in tasks if t["status"] != "done" and int(t.get("minutes_done", 0) or 0) > 0
    )
    not_started_count = max(total - done_count - in_progress_count, 0)

    done_pct = 100 * done_count / total if total else 0
    progress_end = 100 * (done_count + in_progress_count) / total if total else 0
    ring = (
        f"conic-gradient(#63b692 0 {done_pct:.2f}%, "
        f"#3298df {done_pct:.2f}% {progress_end:.2f}%, "
        f"#dedfdd {progress_end:.2f}% 100%)"
        if total else "conic-gradient(#dedfdd 0 100%)"
    )

    estimate = sum(max(int(t.get("estimated_minutes", 0) or 0), 0) for t in tasks) or 1
    done_minutes = sum(
        max(int(t.get("estimated_minutes", 0) or 0), 0) if t["status"] == "done"
        else min(max(int(t.get("minutes_done", 0) or 0), 0), max(int(t.get("estimated_minutes", 0) or 0), 0))
        for t in tasks
    )
    pct = min(100, round(100 * done_minutes / estimate))
    open_t = _open(tasks)
    overdue = [t for t in open_t if due_dt(t) < now]
    week_ago = (now - timedelta(days=7)).isoformat(timespec="minutes")
    week = sum(s["minutes_done"] for s in sessions if s["status"] in ("completed", "partial") and s["start"] >= week_ago)

    bars = ""
    for t in sorted(open_t, key=due_dt)[:3]:
        est = max(int(t["estimated_minutes"]), 1)
        p = min(100, round(100 * int(t["minutes_done"]) / est))
        bars += (
            f'<div class="bv-row"><div class="bv-rowtop"><span>{e(t["task_name"])}</span><span>{p}%</span></div>'
            f'<div class="bv-bar"><div style="width:{p}%"></div></div></div>'
        )

    return f"""
<div class="bv-card">
  <div class="bv-card-title">Chart</div>
  <div class="bv-donut-wrap"><div class="bv-donut" style="background:{ring}">
    <div class="bv-donut-center"><strong>{total}</strong><span>Total tasks</span></div>
  </div></div>
  <div class="bv-chart-legend">
    <span><i class="bv-legend-dot" style="background:#dedfdd"></i>Not started <b>{not_started_count}</b></span>
    <span><i class="bv-legend-dot" style="background:#3298df"></i>In progress <b>{in_progress_count}</b></span>
    <span><i class="bv-legend-dot" style="background:#63b692"></i>Done <b>{done_count}</b></span>
  </div>
  <div class="bv-card-title">Study progress</div>
  <div class="bv-big">{pct}%<small> of estimated work</small></div>
  <div class="bv-bar big"><div style="width:{pct}%"></div></div>
  <div class="bv-stats">
    <div><b>{len(open_t)}</b><span>open</span></div>
    <div><b>{done_count}</b><span>done</span></div>
    <div class="{'bad' if overdue else ''}"><b>{len(overdue)}</b><span>overdue</span></div>
    <div><b>{week // 60}h{week % 60:02d}</b><span>last 7 d</span></div>
  </div>
  {bars}
</div>"""

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
