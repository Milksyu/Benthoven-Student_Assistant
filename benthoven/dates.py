"""Deterministic date parsing for Benthoven.

The language model never normalizes dates. It only copies the date text it saw;
this module turns that text into a real date and decides whether a human must
review it ("no invented certainty").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2,
    "wed": 2, "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4,
    "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
_WEEKDAY_RE = "|".join(sorted(WEEKDAYS, key=len, reverse=True))


@dataclass
class DateResult:
    value: Optional[date]
    status: str  # "ok" | "review" | "none"
    note: str = ""
    matched: str = ""


def _safe_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _resolve_missing_year(m: int, d: int, today: date) -> DateResult:
    """Pick the next occurrence of month/day. Reliable only if it is soon."""
    cand = _safe_date(today.year, m, d)
    if cand is None:
        return DateResult(None, "review", "That day does not exist in the calendar.")
    if cand < today:
        # Possibly already passed (typo / old announcement) or next year's date.
        nxt = _safe_date(today.year + 1, m, d)
        return DateResult(
            nxt, "review",
            f"{cand:%b %d} has already passed this year; assumed next year. Please confirm.",
        )
    if (cand - today).days > 240:
        return DateResult(cand, "review", "Year was not written and the date is far away; please confirm.")
    return DateResult(cand, "ok", f"Year not written; assumed {cand.year}.")


def parse_due_date(text: str, today: date) -> DateResult:
    """Find the most reliable date in `text`. Explicit dates beat relative ones."""
    t = text.strip()
    low = t.lower()

    # 1) ISO 2026-10-15
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", low)
    if m:
        d = _safe_date(int(m[1]), int(m[2]), int(m[3]))
        if d:
            return DateResult(d, "ok", "", m[0])

    # 2) "October 15, 2026" / "Oct. 15th"
    m = re.search(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?\b", low)
    if m:
        mo, day = MONTHS[m[1]], int(m[2])
        if m[3]:
            d = _safe_date(int(m[3]), mo, day)
            return DateResult(d, "ok" if d else "review", "" if d else "Invalid date.", m[0])
        r = _resolve_missing_year(mo, day, today)
        r.matched = m[0]
        return r

    # 3) "15 October 2026"
    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RE})\.?(?:,?\s*(\d{{4}}))?\b", low)
    if m:
        day, mo = int(m[1]), MONTHS[m[2]]
        if m[3]:
            d = _safe_date(int(m[3]), mo, day)
            return DateResult(d, "ok" if d else "review", "" if d else "Invalid date.", m[0])
        r = _resolve_missing_year(mo, day, today)
        r.matched = m[0]
        return r

    # 4) numeric 10/15/2026, 15/10, 05/06/26
    m = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b", low)
    if m:
        a, b = int(m[1]), int(m[2])
        year = int(m[3]) if m[3] else None
        if year is not None and year < 100:
            year += 2000
        if a > 12 and b <= 12:
            mo, day, note, status = b, a, "", "ok"
        elif b > 12 and a <= 12:
            mo, day, note, status = a, b, "", "ok"
        elif a == b:
            mo, day, note, status = a, b, "", "ok"
        else:
            mo, day, status = a, b, "review"
            note = f"Ambiguous numeric date '{m[0]}' (month/day or day/month?). Assumed month/day."
        if year:
            d = _safe_date(year, mo, day)
            if d:
                return DateResult(d, status, note, m[0])
            return DateResult(None, "review", "Invalid date.", m[0])
        r = _resolve_missing_year(mo, day, today)
        if status == "review":
            r.status, r.note = "review", note
        r.matched = m[0]
        return r

    # 5) relative expressions: never silently trusted
    if re.search(r"\b(today|tonight)\b", low):
        return DateResult(today, "review", "Relative date 'today' depends on when the document was written.", "today")
    if re.search(r"\btomorrow\b", low):
        return DateResult(today + timedelta(days=1), "review",
                          "Relative date 'tomorrow' depends on when the document was written.", "tomorrow")
    m = re.search(rf"\b(next|this)?\s*({_WEEKDAY_RE})\b", low)
    if m:
        wd = WEEKDAYS[m[2]]
        delta = (wd - today.weekday()) % 7 or 7
        if m[1] == "next":
            delta += 7 if delta <= 7 - 0 and (wd > today.weekday()) else 0
        guess = today + timedelta(days=delta)
        return DateResult(guess, "review",
                          f"Relative weekday '{m[0].strip()}'. Best guess is {guess:%a %b %d}; please confirm.",
                          m[0].strip())

    return DateResult(None, "none", "No date found.")


_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I)


def parse_due_time(text: str) -> str:
    """Return HH:MM (24h). Defaults to end of day when no time is written."""
    m = _TIME_RE.search(text)
    if not m:
        return "23:59"
    h, minute, ap = int(m[1]), int(m[2] or 0), m[3].lower()
    if h == 12:
        h = 0
    if ap == "pm":
        h += 12
    if h > 23 or minute > 59:
        return "23:59"
    return f"{h:02d}:{minute:02d}"
