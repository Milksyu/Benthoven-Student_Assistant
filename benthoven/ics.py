"""Optional .ics export of planned study sessions (a deliberate, user-triggered export)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def sessions_to_ics(sessions: list[dict]) -> str:
    stamp = _fmt(datetime.now(timezone.utc)) + "Z"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Benthoven//Offline Planner//EN", "CALSCALE:GREGORIAN"]
    for s in sessions:
        start = datetime.fromisoformat(s["start"])
        end = start + timedelta(minutes=s["minutes"])
        lines += [
            "BEGIN:VEVENT", f"UID:benthoven-session-{s['id']}@local", f"DTSTAMP:{stamp}",
            f"DTSTART:{_fmt(start)}", f"DTEND:{_fmt(end)}",
            f"SUMMARY:{_esc(s['task_name'])} ({s['subject'] or 'Study'})",
            f"DESCRIPTION:{_esc(s['goal'])}", "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
