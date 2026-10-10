# Benthoven: materials and disclosures

> Items in **[brackets]** are for the team to confirm before uploading.
> Last updated: October 10, 2026.

Benthoven is an offline academic planner. It reads assignment announcements (pasted text or a photo/screenshot), extracts tasks and deadlines with a local language model, lets the student verify them, and builds a study schedule. This file lists everything that went into it.

## 1. Summary

| Question | Answer |
|---|---|
| Does the app call any cloud API or hosted AI service? | **No.** |
| Does anything need the internet at runtime? | **No.** Internet is only needed once, for setup downloads. |
| Where is user data stored? | A local SQLite file, `data/benthoven.db`. |
| What network addresses does the app contact? | Only `127.0.0.1` (its own page) and `localhost:11434` (Ollama). |
| Were third-party images, icons, fonts or UI kits bundled? | **No.** |
| Was AI used to build it? | **Yes.** Claude (Anthropic), ChatGPT (OpenAI) and Gemini (Google), see section 6. |

## 2. AI models

| Model | Made by | How it is used | License |
|---|---|---|---|
| Llama 3.2 3B Instruct (`llama3.2:3b`), default | Meta | Reads announcement text and proposes tasks as structured JSON (re-checked by code). Also powers the study assistant chat. | Llama 3.2 Community License |
| Llama 3.2 1B Instruct, optional | Meta | Lighter alternative for weaker computers. | Llama 3.2 Community License |
| Tesseract English OCR model (`eng`) | Tesseract project | Reads text from photos and screenshots. | Apache 2.0 |

Built with Llama.

In the study assistant chat the same model answers the student's questions, quizzes them and makes flashcards. It is told to say when it is unsure, and the panel warns that local AI can make mistakes.

In task extraction the model only *proposes* tasks. Code re-parses every date, checks that the quoted evidence exists in the source text, flags anything doubtful, and the student confirms each task. Deadlines and study times come from a deterministic scheduler written in plain Python, never from the model.

## 3. Programs installed on the computer (not bundled in the repository)

| Program | Version seen during testing | Purpose | License |
|---|---|---|---|
| Python | 3.11 or newer (tested on 3.12) | Runs the app | PSF License |
| Ollama | current release | Runs Llama models locally on `localhost:11434` | MIT |
| Tesseract OCR | 5.5.3 (Windows build by UB Mannheim) | Local OCR engine | Apache 2.0 |
| Leptonica | 1.87.0 (comes with Tesseract) | Image library used by Tesseract | BSD-style |
| Git and GitHub | n/a | Version control and hosting the source code | n/a |
| A web browser | any recent one | Displays the dashboard | n/a |

## 4. Python packages

Listed in `requirements.txt`:

| Package | Purpose | License |
|---|---|---|
| pytesseract 0.3.13 | Python wrapper that calls the Tesseract program | Apache 2.0 |
| Pillow 12.3.0 | Opens and prepares images for OCR | HPND |
| requests 2.34.2 | Talks to Ollama on localhost | Apache 2.0 |
| pytest 9.1.1 | Runs the automated tests (development only) | MIT |

Installed automatically as dependencies of the above: certifi, charset-normalizer, idna, urllib3 (from requests); colorama, iniconfig, packaging, pluggy, Pygments (from pytest).

**Python standard library only (no install):** `sqlite3` (database), `http.server` (local web server), `json`, `re`, `difflib`, `datetime`, `math`, `os`, `sys`, `pathlib`, `shutil`, `tempfile`, `time`, `typing`, `dataclasses`, `urllib.parse`, `webbrowser`. The tests also use `threading`, `urllib.request` and `urllib.error`.

No web framework (such as Gradio, Flask or FastAPI) and no data library (such as pandas) is used in the current version.

## 5. Code, design and content

| Item | Source |
|---|---|
| Application code (`app.py`, `benthoven/`), tests, `preflight.py` | Written for this project with AI assistance (section 6). **[confirm: no other existing code was reused]** |
| Date parsing, scheduler, priority ranking, `.ics` calendar export | Hand-written. No date-parsing or calendar library is used. |
| Web page (`static/index.html`) | Hand-written HTML, CSS and plain JavaScript. No JavaScript libraries, CDNs or external scripts. |
| Visual design | The layout (cover banner, task chart, task table with tabs) was modeled on a screenshot of a Notion-style "Task Manager" page that the team supplied. No Notion code, images or assets were copied. The cover and icon are drawn with CSS. |
| Fonts | None bundled. The page asks for Inter if it is installed and otherwise uses the computer's system fonts. |
| Icons and symbols | Unicode characters and emoji drawn by the operating system's fonts. |
| Images | None. |
| `sample_docs/` | Short sample announcements written for this project. **[confirm]** |
| Documentation (`README.md`, `SUBMISSION.md`, `DEMO_SCRIPT.md`, this file) | Written for this project with Claude's help. |

## 6. AI development tools

- **Claude (Anthropic)**, used in the claude.ai chat interface to review the code, fix bugs, write tests, rebuild the user interface, and draft documentation, including this file.
- **ChatGPT (OpenAI)** and **Gemini (Google)**, used as additional AI assistants during development. **[describe what each was used for, e.g. brainstorming, debugging, drafting text]**
- **[confirm: the team ran, tested and reviewed the result]**

Tools used only while developing and testing, and not part of the app: Playwright with Chromium (to take screenshots of the page and click through it), and a small script that runs the pytest tests without pytest installed.

## 7. Network behavior

- The app serves its page on `127.0.0.1` only. It cannot be reached from other computers.
- The page loads no external fonts, scripts, images or analytics.
- The only other connection is to Ollama on `localhost:11434`, used for task extraction and the study assistant chat.
- Requests from other websites to the local server are refused.
- Downloads happen only during setup: Python packages, Tesseract, Ollama, the model weights (about 2 GB), and cloning the repository.

## 8. Data stored locally

Uploaded or pasted announcement text, OCR output, extracted tasks, study sessions, the study-assistant chat history and settings are saved in `data/benthoven.db` on the user's computer. The `data/` folder (including `data/backups/`) is excluded from Git (`.gitignore`) so personal data is never committed. The study assistant sees only the student's chat messages plus a short list of open tasks (name, subject, due date, estimated minutes). It never sees OCR or announcement text. The chat history is saved in the same local database so it is still there after closing the app, and the student can delete it with **New chat**. The browser also remembers unsent drafts, the selected tab and whether the chat panel is open, using its `localStorage` on `127.0.0.1`. Each time the app starts and stops it copies the database to `data/backups/` (newest 5 kept). Nothing is sent anywhere unless the user presses **Export .ics**, which downloads a calendar file to their own computer.

## 9. How to verify

```powershell
python preflight.py          # checks packages, Ollama, Tesseract and runs the real pipeline on the samples
python -m pytest tests -q    # 20 automated tests
python app.py                # then open http://127.0.0.1:7860
```

## 10. Known limitations

- Small local models can misread dates, so every extracted task must be confirmed by the student. Relative dates such as "next Friday" are never trusted automatically.
- OCR quality depends on the photo. PDFs are not supported yet.
- Single user, single computer. English documents only.
