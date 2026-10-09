"""Optional: let the local LLM rephrase the planner's summary in friendlier words.

The LLM may NOT change facts. Every number in its answer must already appear in the
deterministic summary; otherwise we discard it and show the original text.
"""
from __future__ import annotations

import re

import requests


def _numbers(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


def narrate(summary: str, model: str, url: str) -> str:
    try:
        r = requests.post(
            f"{url}/api/chat",
            json={"model": model, "stream": False, "options": {"temperature": 0.2},
                  "messages": [{"role": "user", "content":
                                "Rewrite this study-plan summary for a student in 2-3 warm, calm sentences. "
                                "Keep every number, date and task name exactly as written. Add nothing new.\n\n" + summary}]},
            timeout=60)
        out = r.json()["message"]["content"].strip()
        return out if out and _numbers(out) <= _numbers(summary) else summary
    except Exception:
        return summary
