# Benthoven — offline academic planner

Local-first planner: **capture → extract → verify → plan → adapt**. AI proposes, you confirm, a deterministic scheduler plans.

## Install (once, with internet)
```bash
# 1. Tesseract OCR
#    Windows: https://github.com/UB-Mannheim/tesseract/wiki  (tick "add to PATH")
#    macOS:   brew install tesseract      Ubuntu: sudo apt install tesseract-ocr
# 2. Ollama (runs the local AI): https://ollama.com
ollama pull llama3.2:3b          # or llama3.2:1b on weak laptops
# 3. Python deps
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python preflight.py  # optional: checks tools and runs the real pipeline on sample documents
python app.py        # open http://127.0.0.1:7860
python -m pytest tests -q
```
Without Ollama the app falls back to a regex extractor (clearly labelled in the UI) so it never crashes, but the local AI is the intended experience: check **Privacy → Run local AI self-test**.

## Hackathon submission
See `SUBMISSION.md` (checklist answers, disclosures, what runs locally, why local AI) and `DEMO_SCRIPT.md`.

Built with Llama (Llama 3.2 via Ollama).

## Demo flow
1. Capture → "Try with sample announcements" loads the bundled samples through the real pipeline. Settings: set "Pretend today is" to a date just before your sample deadlines (optional) and Save.
2. Disconnect Wi-Fi. Open **Privacy**, refresh, and run the local AI self-test. (Optional: Settings → live online/offline indicator.)
3. **Capture**: upload `sample_docs/*.txt` or photos of announcements. **Verify**: click a row to see highlighted evidence; fix the "next Friday" date; confirm.
4. **Plan**: generate. Read the ranking reasons and the weekly timetable.
5. **Progress**: mark a session "Couldn't do it" → see "What changed" and the revised plan.

## Dashboard
Header (next deadline, today's load, local-status chips) · left: progress tracker + actions (navigation and quick actions) · centre: main window · right: month calendar (deadlines and study sessions) + up-next card.

## Layout
| File | Role |
|---|---|
| `benthoven/ocr.py` | Tesseract OCR + confidence |
| `benthoven/dates.py` | deterministic date parsing, flags ambiguity |
| `benthoven/extractor.py` | rule engine + Ollama JSON extraction, evidence validation |
| `benthoven/scheduler.py` | priority score + least-laxity-first scheduling, conflicts, diffs |
| `benthoven/storage.py` | SQLite |
| `benthoven/narrator.py` | optional LLM rephrase (numbers must match or it is discarded) |
| `benthoven/ics.py` | .ics export |
| `benthoven/panels.py` | HTML for header, tracker, calendar, up-next |
| `app.py` | Gradio dashboard UI |
