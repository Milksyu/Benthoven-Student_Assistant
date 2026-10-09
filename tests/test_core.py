import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["BENTHOVEN_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")

from benthoven.dates import parse_due_date, parse_due_time
from benthoven.extractor import extract_with_rules
from benthoven.ics import sessions_to_ics
from benthoven.scheduler import schedule, diff_plans, due_dt
from benthoven.storage import DEFAULT_PREFS

TODAY = date(2026, 10, 9)  # a Friday
NOW = datetime(2026, 10, 9, 15, 0)


def test_dates_explicit_and_ambiguous():
    assert parse_due_date("Due date: October 15", TODAY).value == date(2026, 10, 15)
    assert parse_due_date("Due date: October 15", TODAY).status == "ok"
    assert parse_due_date("2026-10-15", TODAY).status == "ok"
    assert parse_due_date("due 05/06/2026", TODAY).status == "review"
    assert parse_due_date("10/16", TODAY).value == date(2026, 10, 16)
    assert parse_due_date("due on the 13/10", TODAY).value == date(2026, 10, 13)


def test_relative_dates_need_review():
    r = parse_due_date("submit next Friday", TODAY)
    assert r.status == "review" and r.value is not None
    assert parse_due_date("tomorrow", TODAY).status == "review"
    assert parse_due_date("no date here", TODAY).status == "none"


def test_past_date_flagged():
    assert parse_due_date("October 5", TODAY).status == "review"


def test_due_time():
    assert parse_due_time("by 5:30 PM") == "17:30"
    assert parse_due_time("12 am") == "00:00"
    assert parse_due_time("nothing") == "23:59"


def test_extract_labeled_blocks():
    text = (ROOT / "sample_docs/announcement_science.txt").read_text()
    tasks = extract_with_rules(text, TODAY)
    assert len(tasks) == 2
    paper = tasks[0]
    assert paper["estimated_minutes"] == 480 and paper["importance"] == 5
    assert paper["due_date"] == "2026-10-19"
    assert tasks[1]["subject"] == "Physics"


def test_extract_sentences_flags_relative_date():
    text = (ROOT / "sample_docs/announcement_chat.txt").read_text()
    tasks = extract_with_rules(text, TODAY)
    quiz = next(t for t in tasks if "Quiz" in t["task_name"])
    assert quiz["due_date"] == "2026-10-14" and quiz["subject"] == "Chemistry"
    essay = next(t for t in tasks if "Essay" in t["task_name"])
    assert essay["needs_review"] and essay["due_date"]


def mk(i, name, due, est, **kw):
    t = dict(id=i, task_name=name, subject="X", due_date=due, due_time="23:59", estimated_minutes=est,
             minutes_done=0, importance=3, priority_override=0, depends_on=None, task_type="Assignment")
    t.update(kw)
    return t


def test_big_project_starts_before_small_worksheet():
    tasks = [mk(1, "Worksheet", "2026-10-10", 30), mk(2, "Big Project", "2026-10-13", 600, task_type="Project")]
    plan = schedule(tasks, dict(DEFAULT_PREFS), [], NOW)
    first = {}
    for s in plan["sessions"]:
        first.setdefault(s["task_id"], s["start"])
    # the project starts today, long before it is due (not left until after the worksheet)
    assert first[2][:10] == "2026-10-09"
    assert sum(s["minutes"] for s in plan["sessions"] if s["task_id"] == 2) == 600
    # and the project outranks the worksheet in the explained priority list
    assert plan["ranking"][0]["task_id"] == 2
    ws = [s for s in plan["sessions"] if s["task_id"] == 1]
    assert sum(s["minutes"] for s in ws) == 30
    assert all(datetime.fromisoformat(s["start"]) <= due_dt(tasks[0]) for s in ws)
    assert not plan["conflicts"]


def test_sessions_respect_windows_commitments_and_cap():
    prefs = dict(DEFAULT_PREFS)
    commitments = [dict(date="2026-10-12", start="16:00", end="19:00", label="Club")]
    plan = schedule([mk(1, "A", "2026-10-14", 300)], prefs, commitments, NOW)
    by_day = {}
    for s in plan["sessions"]:
        st = datetime.fromisoformat(s["start"])
        end = st + timedelta(minutes=s["minutes"])
        by_day[st.date()] = by_day.get(st.date(), 0) + s["minutes"]
        assert end.time() <= datetime(2026, 1, 1, 21, 0).time()
        if st.date() == date(2026, 10, 12):
            assert st.hour >= 19
    assert max(by_day.values()) <= prefs["max_daily_minutes"]
    assert not plan["conflicts"]


def test_conflict_flagged_when_impossible():
    plan = schedule([mk(1, "Impossible", "2026-10-10", 900)], dict(DEFAULT_PREFS), [], NOW)
    assert plan["conflicts"] and plan["conflicts"][0]["deficit_minutes"] > 0
    assert len(plan["conflicts"][0]["options"]) >= 3


def test_dependency_order():
    tasks = [mk(1, "Outline", "2026-10-12", 60), mk(2, "Essay", "2026-10-13", 60, depends_on=1)]
    plan = schedule(tasks, dict(DEFAULT_PREFS), [], NOW)
    end1 = max(datetime.fromisoformat(s["start"]) + timedelta(minutes=s["minutes"]) for s in plan["sessions"] if s["task_id"] == 1)
    start2 = min(datetime.fromisoformat(s["start"]) for s in plan["sessions"] if s["task_id"] == 2)
    assert start2 >= end1


def test_reschedule_after_missed_session_keeps_deadlines():
    tasks = [mk(1, "Project", "2026-10-14", 240)]
    first = schedule(tasks, dict(DEFAULT_PREFS), [], NOW)
    later = schedule(tasks, dict(DEFAULT_PREFS), [], NOW + timedelta(hours=2))
    assert sum(s["minutes"] for s in later["sessions"]) == 240
    assert diff_plans(first["sessions"], later["sessions"], {1: "Project"})


def test_priority_override_and_overdue():
    tasks = [mk(1, "Late", "2026-10-08", 60), mk(2, "Later", "2026-10-30", 60, priority_override=5)]
    plan = schedule(tasks, dict(DEFAULT_PREFS), [], NOW)
    assert any(r["overdue"] for r in plan["ranking"])
    assert next(r for r in plan["ranking"] if r["task_id"] == 2)["score"] == 100.0


def test_ics():
    ics = sessions_to_ics([dict(id=1, task_name="A, B", subject="S", goal="Go", start="2026-10-09T16:00", minutes=45)])
    assert "BEGIN:VEVENT" in ics and "DTSTART:20261009T160000" in ics and "DTEND:20261009T164500" in ics


def test_ics_escapes_newlines_and_subject_fields():
    ics = sessions_to_ics([dict(
        id=2, task_name="Math\r\nBEGIN:VEVENT", subject="Science, Lab;\rInjected:yes",
        goal="Read\\notes\r\nEND:VEVENT", start="2026-10-09T16:00", minutes=45
    )])
    assert "SUMMARY:Math\\nBEGIN:VEVENT (Science\\, Lab\\;\\nInjected:yes)" in ics
    assert "DESCRIPTION:Read\\\\notes\\nEND:VEVENT" in ics
    assert "\r\nBEGIN:VEVENT\r\n" in ics


def test_llm_output_is_revalidated(monkeypatch):
    """A hallucinated LLM answer must be flagged, not trusted."""
    import json
    from benthoven import extractor

    doc = "Subject: Physics\nQuiz on Friday, October 16, 2026 about motion."
    fake = {"tasks": [
        {"task_name": "Physics Quiz", "subject": "Physics", "due_date_text": "October 16, 2026", "task_type": "Quiz",
         "source_text": "Quiz on Friday, October 16, 2026 about motion."},
        {"task_name": "Ghost Exam", "subject": "Physics", "due_date_text": "October 30", "task_type": "Exam",
         "source_text": "Final exam happens on October 30 in the gym."},   # not in the document
    ]}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": json.dumps(fake)}}

    monkeypatch.setattr(extractor.requests, "post", lambda *a, **k: R())
    tasks = extractor.extract_with_ollama(doc, TODAY, "m", "http://x")
    good, ghost = tasks
    assert good["due_date"] == "2026-10-16"
    assert good["confidence"] >= 0.75
    assert ghost["needs_review"] and ghost["confidence"] <= 0.4
    assert any("not found" in f or "does not appear" in f for f in ghost["flags"])


def test_panels_render():
    from benthoven.panels import calendar_html, header_html, tracker_html, upnext_html
    t = mk(1, "Problem <Set> 4", "2026-10-15", 90, status="open", confirmed=1)
    sessions = [dict(id=1, task_id=1, task_name="Problem <Set> 4", start="2026-10-09T16:00", minutes=45,
                     goal="Start it", status="planned", minutes_done=0)]
    status = dict(ocr=True, ai=False, net=False)
    h = header_html(NOW, [t], sessions, 2, status)
    assert "Benthoven" in h and "2 to verify" in h and "&lt;Set&gt;" in h and "Offline" in h
    assert "0%" in tracker_html(NOW, [t], sessions)
    cal = calendar_html(NOW, 0, [t], sessions)
    assert "October 2026" in cal and 'class="due"' in cal
    assert "November 2026" in calendar_html(NOW, 1, [t], sessions)
    assert "Start it" in upnext_html(NOW, [t], sessions)
    assert "Chart" in tracker_html(NOW, [], [])
    assert "Total tasks" in tracker_html(NOW, [t], sessions)
    assert "bv-donut" in tracker_html(NOW, [t], sessions)


def test_image_ocr_uses_local_rapidocr(tmp_path, monkeypatch):
    """Images use the in-process OCR engine and return human-readable confidence."""
    from types import SimpleNamespace
    from PIL import Image
    from benthoven import ocr

    image_path = tmp_path / "announcement.png"
    Image.new("RGB", (320, 180), color="white").save(image_path)

    class FakeEngine:
        def __call__(self, image):
            assert image.ndim == 3
            assert image.shape[2] == 3
            return SimpleNamespace(
                txts=("Physics quiz on Friday", "Due October 16"),
                scores=(0.9, 0.7),
            )

    monkeypatch.setattr(ocr, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr, "_get_ocr_engine", lambda: FakeEngine())

    text, confidence = ocr.read_document(str(image_path))

    assert text == "Physics quiz on Friday\nDue October 16"
    assert confidence == 80.0


def test_build_ui_constructs_dashboard():
    """Keep the refreshed Gradio layout covered by a lightweight construction test."""
    import app as app_module

    demo = app_module.build_ui()
    assert demo is not None
    assert app_module.TASK_HEADERS[2] == "Task name"
    assert ".bv-cover" in app_module.CSS


def test_save_tasks_handles_missing_remove_column(monkeypatch):
    """Older Gradio table payloads can omit the optional Remove checkbox."""
    import pandas as pd
    import app as app_module

    updates = []
    deletes = []
    monkeypatch.setattr(app_module, "_now", lambda: NOW)
    monkeypatch.setattr(app_module.db, "update_task", lambda task_id, **fields: updates.append((task_id, fields)))
    monkeypatch.setattr(app_module.db, "delete_task", lambda task_id: deletes.append(task_id))
    monkeypatch.setattr(app_module, "tasks_df", lambda: pd.DataFrame(columns=app_module.TASK_COLS))

    df = pd.DataFrame([{
        "ID": 7,
        "Task name": "Algebra worksheet",
        "Subject": "Math",
        "Deadline": "2026-10-16",
        "Est. minutes": 45,
        "Minutes done": 0,
        "Importance": 3,
        "Priority override": 0,
        "Depends on ID": 0,
        "Status": "open",
    }])
    message, _ = app_module.save_tasks(df)

    assert message == "Saved."
    assert len(updates) == 1
    assert updates[0][0] == 7
    assert updates[0][1]["task_name"] == "Algebra worksheet"
    assert updates[0][1]["due_date"] == "2026-10-16"
    assert deletes == []


def test_save_tasks_treats_string_false_as_unchecked(monkeypatch):
    """A text value such as 'False' must not become truthy and delete a task."""
    import pandas as pd
    import app as app_module

    updates = []
    deletes = []
    monkeypatch.setattr(app_module, "_now", lambda: NOW)
    monkeypatch.setattr(app_module.db, "update_task", lambda task_id, **fields: updates.append((task_id, fields)))
    monkeypatch.setattr(app_module.db, "delete_task", lambda task_id: deletes.append(task_id))
    monkeypatch.setattr(app_module, "tasks_df", lambda: pd.DataFrame(columns=app_module.TASK_COLS))

    df = pd.DataFrame([{
        "ID": 8,
        "Remove": "False",
        "Task name": "Chemistry quiz",
        "Subject": "Chemistry",
        "Deadline": "2026-10-17",
        "Est. minutes": 30,
        "Minutes done": 0,
        "Importance": 3,
        "Priority override": 0,
        "Depends on ID": 0,
        "Status": "open",
    }])
    message, _ = app_module.save_tasks(df)

    assert message == "Saved."
    assert len(updates) == 1
    assert deletes == []
