"""Deterministic planning engine (Stages 3-5).

No language model is involved here: deadlines, durations and time slots come from
explicit rules so results are predictable and testable.

Scheduling strategy: *least laxity first* (LLF). Laxity = free study time that
remains before a task's deadline minus the work still needed. A big project due in
four days has little laxity, so it is started before a tiny worksheet due tomorrow,
while the worksheet's time is still protected.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

MIN_BLOCK = 15          # smallest useful study chunk (minutes)
MAX_HORIZON_DAYS = 90
ENERGY_FACTOR = {"low": 0.7, "normal": 1.0, "high": 1.15}


@dataclass
class Block:
    start: datetime
    minutes: int
    focus: bool

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.minutes)


def _t(s: str) -> time:
    h, m = s.split(":")[:2]
    return time(int(h), int(m))


def remaining(t: dict) -> int:
    return max(int(t["estimated_minutes"]) - int(t.get("minutes_done") or 0), 0)


def due_dt(t: dict) -> datetime:
    return datetime.combine(date.fromisoformat(t["due_date"]), _t(t.get("due_time") or "23:59"))


def round_up(dt: datetime, step: int = 15) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    extra = (-dt.minute) % step
    return dt + timedelta(minutes=extra)


def _subtract(intervals: list[tuple[datetime, datetime]], busy: list[tuple[datetime, datetime]]):
    out = intervals
    for bs, be in busy:
        nxt = []
        for s, e in out:
            if be <= s or bs >= e:
                nxt.append((s, e))
                continue
            if bs > s:
                nxt.append((s, bs))
            if be < e:
                nxt.append((be, e))
        out = nxt
    return out


# ------------------------------------------------------------------ blocks
def build_blocks(now: datetime, horizon_end: date, prefs: dict, commitments: list[dict],
                 done_today_minutes: int = 0) -> list[Block]:
    """Turn availability windows (minus commitments) into study blocks with breaks."""
    session, brk = int(prefs["session_minutes"]), int(prefs["break_minutes"])
    blocks: list[Block] = []
    day = now.date()
    start_floor = round_up(now)
    while day <= horizon_end:
        weekend = day.weekday() >= 5
        ws, we = _t(prefs["weekend_start" if weekend else "weekday_start"]), _t(prefs["weekend_end" if weekend else "weekday_end"])
        w_start = datetime.combine(day, ws)
        w_end = datetime.combine(day, we)
        if day == now.date():
            w_start = max(w_start, start_floor)
        busy = [(datetime.combine(day, _t(c["start"])), datetime.combine(day, _t(c["end"])))
                for c in commitments if c["date"] == day.isoformat()]
        cap = int(prefs["max_daily_minutes"])
        if day == now.date():
            cap = int(cap * ENERGY_FACTOR.get(prefs.get("energy", "normal"), 1.0)) - done_today_minutes
        used = 0
        if w_end > w_start:
            for s, e in _subtract([(w_start, w_end)], busy):
                cur = s
                while used < cap:
                    length = min(session, int((e - cur).total_seconds() // 60), cap - used)
                    if length < MIN_BLOCK:
                        break
                    focus = _t(prefs["focus_start"]) <= cur.time() < _t(prefs["focus_end"])
                    blocks.append(Block(cur, length, focus))
                    used += length
                    cur = cur + timedelta(minutes=length + brk)
        day += timedelta(days=1)
    return sorted(blocks, key=lambda b: b.start)


# ---------------------------------------------------------------- priority
def _avail_before(blocks: list[Block], deadline: datetime, after: datetime) -> int:
    return sum(b.minutes for b in blocks if b.start >= after and b.end <= deadline)


def rank_tasks(tasks: list[dict], blocks: list[Block], now: datetime) -> list[dict]:
    """Priority score 0-100 plus a plain-language reason for every task."""
    blockers = {t["depends_on"] for t in tasks if t.get("depends_on")}
    ranked = []
    for t in tasks:
        rem = remaining(t)
        dl = due_dt(t)
        avail = _avail_before(blocks, dl, now)
        overdue = dl <= now
        pressure = 1.5 if overdue else min(rem / max(avail, 1), 1.5)
        days_left = max((dl - now).total_seconds() / 86400, 0)
        urgency = 1 / (1 + days_left)
        score = (45 * pressure / 1.5 + 25 * urgency + 15 * min(rem / 240, 1) + 15 * (int(t.get("importance") or 3) / 5)
                 + (5 if t["id"] in blockers else 0))
        score = min(round(score, 1), 100.0)
        reasons = []
        if overdue:
            reasons.append("deadline has passed")
        else:
            d = days_left
            reasons.append("due today" if d < 1 else f"due in {math.ceil(d)} day{'s' if math.ceil(d) != 1 else ''} ({dl:%a %b %d})")
            if avail:
                reasons.append(f"needs {rem} min of your {avail} free min before then ({rem * 100 // avail}%)")
            else:
                reasons.append(f"needs {rem} min but no free study time is left before the deadline")
        if int(t.get("importance") or 3) >= 4:
            reasons.append("high grade weight")
        if t["id"] in blockers:
            reasons.append("other tasks depend on it")
        if int(t.get("priority_override") or 0) > 0:
            score = int(t["priority_override"]) * 20.0
            reasons = [f"you set priority {t['priority_override']}/5"] + reasons
        ranked.append({"task_id": t["id"], "task_name": t["task_name"], "subject": t.get("subject", ""),
                       "score": score, "reason": "; ".join(reasons), "remaining": rem, "available": avail,
                       "overdue": overdue})
    return sorted(ranked, key=lambda r: -r["score"])


# --------------------------------------------------------------- scheduler
def _goal(task: dict, idx: int, total: int) -> str:
    n = task["task_name"]
    exam = task.get("task_type") in ("Exam", "Quiz")
    if total == 1:
        return f"Review everything for {n} and do a self-test." if exam else f"Complete {n}."
    if idx == 0:
        return f"Review notes and key topics for {n}." if exam else f"Start {n}: read instructions, plan, do the first part."
    if idx == total - 1:
        return f"Final review and self-test for {n}." if exam else f"Finish {n} and double-check before submitting."
    return f"Practice questions for {n}." if exam else f"Continue {n}."


def schedule(tasks: list[dict], prefs: dict, commitments: list[dict], now: datetime,
             done_today_minutes: int = 0) -> dict:
    """Return {'sessions', 'ranking', 'conflicts', 'blocks_total'} for the open, confirmed tasks."""
    tasks = [t for t in tasks if t.get("due_date") and remaining(t) > 0]
    if not tasks:
        return {"sessions": [], "ranking": [], "conflicts": [], "blocks_total": 0}
    horizon_end = min(max(max(due_dt(t).date() for t in tasks), now.date() + timedelta(days=7)),
                      now.date() + timedelta(days=MAX_HORIZON_DAYS))
    blocks = build_blocks(now, horizon_end, prefs, commitments, done_today_minutes)
    ranking = rank_tasks(tasks, blocks, now)
    score = {r["task_id"]: r["score"] for r in ranking}
    rem = {t["id"]: remaining(t) for t in tasks}
    by_id = {t["id"]: t for t in tasks}
    finished_at: dict[int, datetime] = {}
    placed: list[dict] = []

    def deps_ok(t: dict, at: datetime) -> bool:
        dep = t.get("depends_on")
        if not dep or dep not in by_id:      # dependency already completed (or unknown) -> no block
            return True
        return dep in finished_at and finished_at[dep] <= at

    for i, b in enumerate(blocks):
        cur, left = b.start, b.minutes
        while left >= 1:
            cands = [t for t in tasks if rem[t["id"]] > 0 and deps_ok(t, cur)]
            if not cands:
                break
            future = blocks[i + 1:]

            def laxity(t: dict) -> float:
                dl = due_dt(t)
                here = max(0, min(left, int((dl - cur).total_seconds() // 60)))
                later = sum(x.minutes for x in future if x.end <= dl)
                return here + later - rem[t["id"]]

            def key(t: dict):
                lax = laxity(t)
                if b.focus and rem[t["id"]] >= 90:   # keep demanding work for high-focus hours
                    lax -= 60
                return (lax, -score[t["id"]], t["id"])

            t = min(cands, key=key)
            chunk = min(left, rem[t["id"]], int(prefs["session_minutes"]))
            if chunk < MIN_BLOCK and rem[t["id"]] > chunk:
                break
            placed.append({"task_id": t["id"], "start": cur.isoformat(timespec="minutes"), "minutes": chunk})
            rem[t["id"]] -= chunk
            cur += timedelta(minutes=chunk)
            left -= chunk
            if rem[t["id"]] == 0:
                finished_at[t["id"]] = cur
            if left < MIN_BLOCK:
                break

    # goals
    per_task: dict[int, list[dict]] = {}
    for s in placed:
        per_task.setdefault(s["task_id"], []).append(s)
    for tid, lst in per_task.items():
        for idx, s in enumerate(lst):
            s["goal"] = _goal(by_id[tid], idx, len(lst))

    conflicts = _find_conflicts(tasks, placed, rem, ranking)
    return {"sessions": sorted(placed, key=lambda s: s["start"]), "ranking": ranking,
            "conflicts": conflicts, "blocks_total": len(blocks)}


def _find_conflicts(tasks: list[dict], placed: list[dict], rem: dict, ranking: list[dict]) -> list[dict]:
    out = []
    score = {r["task_id"]: r["score"] for r in ranking}
    for t in tasks:
        dl = due_dt(t)
        late = sum(s["minutes"] for s in placed if s["task_id"] == t["id"]
                   and datetime.fromisoformat(s["start"]) + timedelta(minutes=s["minutes"]) > dl)
        deficit = rem[t["id"]] + late
        if deficit <= 0:
            continue
        others = sorted((o for o in tasks if o["id"] != t["id"] and due_dt(o) > dl), key=lambda o: score[o["id"]])[:2]
        options = [
            f"Add about {math.ceil(deficit / 6) / 10:g} h of extra study time before {dl:%a %b %d} "
            f"(widen a study window, shorten breaks, or raise the daily limit in Settings).",
            f"Check the estimate ({t['estimated_minutes']} min) or reduce the scope of {t['task_name']}.",
        ]
        if others:
            options.append("Postpone lower-priority work that is due later: " + ", ".join(o["task_name"] for o in others) + ".")
        options.append("Ask your teacher about an extension or a clearer scope, or ask a classmate or tutor for help with the hardest part.")
        out.append({"task_id": t["id"], "task_name": t["task_name"], "deficit_minutes": deficit,
                    "message": f"{t['task_name']} is short by about {deficit} min of study time before its deadline ({dl:%a %b %d, %H:%M}).",
                    "options": options})
    return out


# -------------------------------------------------------------- reporting
def diff_plans(old: list[dict], new: list[dict], names: dict[int, str]) -> list[str]:
    """Describe what changed so the student sees a calm explanation, not a wall of overdue items."""
    def group(lst):
        g: dict[int, set] = {}
        for s in lst:
            g.setdefault(s["task_id"], set()).add((s["start"], s["minutes"]))
        return g
    o, n = group(old), group(new)
    lines = []
    for tid in sorted(set(o) | set(n)):
        removed, added = o.get(tid, set()) - n.get(tid, set()), n.get(tid, set()) - o.get(tid, set())
        if removed or added:
            lines.append(f"{names.get(tid, tid)}: {len(removed)} session(s) removed, {len(added)} new session(s) added.")
    return lines or ["No changes were needed to the remaining plan."]


def summarize(plan: dict, names: dict[int, str], now: datetime) -> str:
    """Plain deterministic summary (can optionally be rephrased by the local LLM)."""
    parts = []
    if plan["ranking"]:
        top = plan["ranking"][0]
        parts.append(f"Focus first on {top['task_name']}: {top['reason']}.")
    todays = [s for s in plan["sessions"] if s["start"][:10] == now.date().isoformat()]
    if todays:
        total = sum(s["minutes"] for s in todays)
        parts.append(f"Today you have {len(todays)} session(s), {total} min in total.")
    else:
        parts.append("Nothing is scheduled for the rest of today.")
    if plan["conflicts"]:
        parts.append(f"Heads up: {len(plan['conflicts'])} task(s) do not fully fit in your available time. See the options below.")
    else:
        parts.append("Everything fits inside your available time without cutting into sleep or rest.")
    return " ".join(parts)
