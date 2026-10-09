# Benthoven: hackathon submission

> Items in **[brackets]** are for the team to fill in or confirm before submitting.

## The project
- **Project name:** Benthoven
- **Short description:** Benthoven is an offline academic planner. It reads photos or text of assignment announcements with local OCR and a local language model, shows every extracted deadline next to its source text for the student to verify, then builds a realistic study schedule and replans when the student falls behind. Documents and schedules never leave the computer.
- **Team members:** Alan Gabriell Asinas **[add other team members, or delete this note if solo]**
- **Public GitHub repository:** **[https://github.com/Milksyu/Benthoven-Student_Assistant](https://github.com/Milksyu/Benthoven-Student_Assistant)**

## The proof
- **Demo video:** **[X / LinkedIn video URL]** (script: `DEMO_SCRIPT.md`)
- **What runs locally:** everything at runtime.
  - OCR: Tesseract, run as a local program.
  - Language model: Llama 3.2 (3B by default) served by Ollama on `localhost:11434`.
  - Scheduler and priority engine: plain Python, deterministic.
  - Storage: SQLite file in `./data/`.
  - UI: Gradio, bound to `127.0.0.1` only, with all fonts and assets bundled.
- **What requires internet:** only one-time setup. Downloading Python packages, Tesseract, Ollama, the model weights (about 2 GB) and cloning the repo. At runtime nothing requires internet. We audited this: with the default settings the app opens **no connection to any non-loopback address**, and the browser requests only `127.0.0.1`. The single optional exception is a status indicator in Settings (off by default) that opens one empty TCP connection to `1.1.1.1:53` to show Online/Offline.

## Why does this product benefit from running AI locally?
1. **The input is private.** Assignment photos, grades, and a student's daily timetable are personal data, and many users are minors. Sending them to a cloud model to get a to-do list is a poor trade; locally, nothing leaves the device by design (verified by the network audit above).
2. **It works where students actually are.** Deadlines get checked on a bus, in a dorm with weak Wi-Fi, or during an outage. After setup, the full workflow works with the network disconnected.
3. **No cost, accounts or rate limits.** A student can scan a whole stack of handouts every week without an API key, a subscription or a quota.
4. **Trust is built into the design.** The local model only *proposes* tasks. Code re-parses every date, checks that the quoted evidence really exists in the OCR text, and flags anything doubtful; the student confirms. Deadlines and time slots come from a deterministic scheduler, never from the model.

What the local model does: reads messy, unstructured announcement text (any wording) and converts it into structured tasks, estimates effort when the document gives none (flagged as an AI estimate), and can rephrase the schedule summary (numbers must match or the rephrase is discarded). Without a local model the app drops to a regex fallback so it never crashes, but that fallback is clearly labelled in the UI.

## The disclosures
- **Models used:**
  - Llama 3.2 3B Instruct (Meta), via Ollama. Default.
  - Llama 3.2 1B Instruct (Meta), via Ollama. Optional for weaker laptops.
  - Tesseract's English LSTM OCR model (`eng`).
  - Built with Llama.
- **Technologies and frameworks:** Python 3.12, Gradio 6, pandas, pytesseract, Pillow, requests, SQLite (Python standard library), pytest; Tesseract OCR and Ollama as local programs.
- **APIs and cloud services:** none used at runtime. GitHub hosts the source code and X/LinkedIn hosts the demo video; neither is used by the app.
- **Existing code and assets:** **[confirm]** none. All code, tests and documents in this repository were written during the hackathon. No third-party images, icons or fonts are bundled (the interface uses system emoji). The files in `sample_docs/` were written for this project.
- **AI development tools:** Claude (Anthropic), used in the claude.ai chat interface to help design and write the code, tests and documentation. **[confirm: the team ran, tested and reviewed the result]**

## Verify our claims yourself
```bash
python preflight.py            # checks tools, runs the real pipeline on the sample documents
python -m pytest tests -q      # 20 tests: dates, extraction, evidence checks, scheduler, replanning
python app.py                  # open http://127.0.0.1:7860 ; Privacy tab -> "Run local AI self-test"
```

## Known limitations (honest list)
- Small local models can misread dates, which is why every task needs student confirmation. Relative dates such as "next Friday" are never trusted automatically.
- Image OCR quality depends on photo quality; blurry photos are flagged by a low-confidence warning. PDFs are not supported yet.
- Single-user, single-computer app; calendar sync is an optional `.ics` file export only.
- English-language documents only in this version.
