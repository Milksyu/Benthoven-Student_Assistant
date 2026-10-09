# Benthoven: hackathon submission

> Items in **[brackets]** are for the team to fill in or confirm before submitting.

## The project
- **Project name:** Benthoven
- **Short description:** Benthoven is an offline academic planner. It reads photos or text of assignment announcements with local OCR and a local language model, shows every extracted deadline next to its source text for the student to verify, then builds a realistic study schedule and replans when the student falls behind. Documents and schedules never leave the computer.
- **Team members:** Alan Gabriell Asinas **[add other team members, or delete this note if solo]**
- **Public GitHub repository:** **[https://github.com/Milksyu/Benthoven-Student_Assistant](https://github.com/Milksyu/Benthoven-Student_Assistant)**

## The proof
- **Demo video:** **[X / LinkedIn video URL]** (script: `DEMO_SCRIPT.md`)
- **What runs locally:** image OCR, AI inference, scheduling, and storage run on the same computer.
  - OCR: RapidOCR through ONNX Runtime, installed as Python dependencies; no separate OCR executable is needed.
  - Language model: Llama 3.2 (3B by default) served by Ollama on `localhost:11434`.
  - Scheduler and priority engine: plain Python, deterministic.
  - Storage: SQLite file in `./data/`.
  - UI: Gradio, bound to `127.0.0.1` only, with all fonts and assets bundled.
- **What requires internet:** initial setup requires downloading Python packages, Ollama, the configured model, and the repository. Once set up, OCR and model inference run locally. The dashboard's header also checks internet reachability by opening a brief TCP connection to `1.1.1.1:53`; it does not send assignment content in that connection.

## Why does this product benefit from running AI locally?
1. **The input is private.** Assignment photos, grades, and a student's daily timetable are personal data, and many users are minors. Sending them to a cloud model to get a to-do list is a poor trade; locally, nothing leaves the device by design (verified by the network audit above).
2. **It works where students actually are.** Deadlines get checked on a bus, in a dorm with weak Wi-Fi, or during an outage. After setup, the full workflow works with the network disconnected.
3. **No cost, accounts or rate limits.** A student can scan a whole stack of handouts every week without an API key, a subscription or a quota.
4. **Trust is built into the design.** The local model only *proposes* tasks. Code re-parses every date, checks that the quoted evidence really exists in the OCR text, and flags anything doubtful; the student confirms. Deadlines and time slots come from a deterministic scheduler, never from the model.

What the local model does: reads messy, unstructured announcement text and converts it into structured tasks, estimates effort when the document gives none (flagged as an AI estimate), and can rephrase the schedule summary (numbers must match or the rephrase is discarded). Ollama and the configured model are required; Benthoven checks that they are available at startup and does not silently switch to regex-only extraction or a cloud model.

## The disclosures
- **Models used:**
  - Llama 3.2 3B Instruct (Meta), via Ollama. Default.
  - Llama 3.2 1B Instruct (Meta), via Ollama. Optional for weaker laptops.
  - RapidOCR recognition and detection models bundled with the RapidOCR Python package.
  - Built with Llama.
- **Technologies and frameworks:** Python 3.11 and 3.14 (tested in CI), Gradio 6, pandas, RapidOCR, ONNX Runtime, Pillow, requests, SQLite (Python standard library), pytest; Ollama for local model inference.
- **APIs and cloud services:** none used at runtime. GitHub hosts the source code and X/LinkedIn hosts the demo video; neither is used by the app.
- **Existing code and assets:** **[confirm]** none. All code, tests and documents in this repository were written during the hackathon. No third-party images, icons or fonts are bundled (the interface uses system emoji). The files in `sample_docs/` were written for this project.
- **AI development tools:** Claude (Anthropic), used in the claude.ai chat interface to help design and write the code, tests and documentation. **[confirm: the team ran, tested and reviewed the result]**

## Verify our claims yourself
```bash
python preflight.py            # checks dependencies and runs the sample pipeline
python -m pytest tests -q      # automated tests for OCR output, dates, extraction, scheduler, and UI
python app.py                  # open http://127.0.0.1:7860 ; Privacy tab -> "Run local AI self-test"
```

## Known limitations (honest list)
- Small local models can misread dates, which is why every task needs student confirmation. Relative dates such as "next Friday" are never trusted automatically.
- Image OCR quality depends on photo quality; blurry photos are flagged by a low-confidence warning. PDFs are not supported yet.
- Single-user, single-computer app; calendar sync is an optional `.ics` file export only.
- English-language documents only in this version.
