# Benthoven — Student Assistant

> **Turn assignment announcements into a realistic study plan.**
>
> Benthoven is a local-first academic planner for students. Add assignment announcements as text or images, review the tasks and deadlines it extracts, and generate a study schedule that can be updated when life gets in the way.

<p align="center">
  <strong>Capture → Extract → Verify → Plan → Adapt</strong>
</p>

## Contents

- [What Benthoven does](#what-benthoven-does)
- [Current MVP scope](#current-mvp-scope)
- [System requirements](#system-requirements)
- [What you need to install](#what-you-need-to-install)
- [Installation on Windows](#installation-on-windows)
- [Installation on macos](#installation-on-macos)
- [Installation on Linux](#installation-on-linux)
- [Start the app](#start-the-app)
- [First-time walkthrough](#first-time-walkthrough)
- [Required local AI with Ollama](#required-local-ai-with-ollama)
- [Run the tests](#run-the-tests)
- [Privacy and offline behavior](#privacy-and-offline-behavior)
- [Supported files](#supported-files)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Development notes](#development-notes)

---

## What Benthoven does

Students often receive deadlines in group chats, screenshots, learning platforms, or written announcements. Benthoven brings those tasks into one local dashboard and helps turn them into a workable plan.

1. **Capture** — upload announcement text or images, or enter a task manually.
2. **Extract** — detect possible task names, subjects, task types, estimated effort, and due dates.
3. **Verify** — review the extracted information and correct it before treating it as a real deadline.
4. **Plan** — create study sessions around your available hours, commitments, session length, breaks, and daily workload.
5. **Adapt** — record completed or missed sessions and regenerate the plan to see what needs to change.
6. **Export** — export scheduled sessions to an `.ics` calendar file for use with compatible calendar apps.

The guiding principle is **AI can suggest; the student confirms**. Extracted deadlines should always be checked before relying on them.

## Current MVP scope

| Capability | Current behavior |
|---|---|
| Assignment input | Text files, Markdown files, supported image formats, pasted text, and manual task entry |
| Image-to-text | Local Tesseract OCR, when installed |
| Task extraction | Required local Llama model through Ollama; output is validated before review |
| Deadline handling | Date parsing with ambiguity flags for review |
| Task review | Confirm, edit, and remove extracted tasks in the dashboard |
| Scheduling | Generates sessions using saved availability, commitments, workload limits, and task priorities |
| Progress tracking | Record progress and missed sessions, then regenerate the schedule |
| Persistence | Local SQLite database |
| Calendar | In-app calendar and `.ics` export |
| Interface | Local web dashboard powered by Gradio |

This is an MVP, not a guaranteed deadline-management service. It does not currently read PDFs directly, automatically sync school portals, or guarantee that every deadline will be extracted correctly.

## System requirements

### Recommended setup

- **Operating system:** Windows 11 is the easiest starting point for many users. macOS and mainstream Linux distributions are also supported by the Python app and its dependencies.
- **Python:** Python **3.11 or 3.12** is recommended for a straightforward setup. Use a 64-bit installation.
- **Memory:** 4 GB RAM is a practical baseline for the app without local AI. More memory is recommended if you also run a local language model.
- **Storage:** Allow at least 1 GB for the project, Python packages, and sample data. Optional AI models can require several additional gigabytes.
- **Browser:** A recent version of Chrome, Edge, Firefox, or Safari.
- **Internet:** Required for the initial downloads. The core app can run locally after installation; see [Privacy and offline behavior](#privacy-and-offline-behavior).

You do **not** need a GPU, Docker, a database server, or a paid API key to use the basic app.

## What you need to install

| Software | Required? | Why it is needed | Official / trusted source |
|---|---|---|---|
| Python 3.11 or 3.12 | Yes | Runs Benthoven and installs its Python packages | [python.org/downloads](https://www.python.org/downloads/) |
| Git | Only if cloning the repository | Downloads and updates the source code | [git-scm.com/downloads](https://git-scm.com/downloads) |
| Tesseract OCR | Only for image uploads | Converts text in screenshots/photos into text | [Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html) |
| Ollama | **Yes** | Runs the required Llama model locally; no hosted AI API is used | [ollama.com/download](https://ollama.com/download) |
| A modern web browser | Yes | Displays the local dashboard | Use your existing browser |

**Required install:** Python, the project dependencies, Ollama, and the configured local Llama model. Benthoven checks that Ollama and the model are available before starting. Tesseract is additionally required for image OCR; text pasted into the app does not require OCR.

---

## Installation on Windows

These instructions are for Windows 10/11 using **PowerShell**. Windows 11 is recommended. Install Python from the official website and, during setup, enable **Add Python to PATH** if the installer offers that option.

### 1. Download the project

**If you downloaded the ZIP file:**

1. Extract `Benthoven-StudentAssistant-main.zip` using File Explorer.
2. Move the extracted `Benthoven-StudentAssistant-main` folder somewhere convenient, such as `Documents` or `Projects`.
3. Open that folder in File Explorer.
4. Click the address bar, type `powershell`, and press Enter. PowerShell should open in the project folder.

**If you are using Git:** open PowerShell in the folder where you keep projects, then run the repository's clone command. Replace `<REPOSITORY-URL>` with the actual URL of your Git repository:

```powershell
git clone <REPOSITORY-URL>
cd Benthoven-StudentAssistant
```

If you do not have a Git repository URL, use the ZIP method instead.

### 2. Confirm Python is installed

Run:

```powershell
py --version
```

The result should show Python 3.11.x or 3.12.x. If `py` is not recognized, install Python from [python.org](https://www.python.org/downloads/) and reopen PowerShell. If you have multiple Python versions, `python --version` is another useful check.

### 3. Create a virtual environment

Run these commands from the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you installed Python 3.12 instead, use `py -3.12 -m venv .venv` in the first command.

If PowerShell blocks the activation script, you can activate it for the current terminal session with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

This changes the policy only for the current PowerShell process. Alternatively, you can skip activation and use `.venv\Scripts\python.exe` for each Python command.

### 4. Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Wait for pip to finish. If installation fails, read the first error message and check that the correct Python version is active.

### 5. Install Tesseract OCR (for screenshots and photos)

1. Open the [Tesseract Windows installation page](https://github.com/UB-Mannheim/tesseract/wiki).
2. Download and run the current 64-bit installer.
3. Keep English language data selected if your announcements are in English.
4. If the installer does not add Tesseract to PATH, add its installation directory—commonly `C:\Program Files\Tesseract-OCR`—to your Windows PATH.
5. Close and reopen PowerShell, then verify the installation:

```powershell
tesseract --version
```

If you only plan to paste text or use `.txt` / `.md` files, you can skip Tesseract for now.

### 6. Install Ollama and the required Llama model

1. Install Ollama from [ollama.com/download](https://ollama.com/download).
2. Open a new PowerShell terminal and download the configured model:

   ```powershell
   ollama pull llama3.2:3b
   ```
3. Confirm the model is present:

   ```powershell
   ollama list
   ```

Benthoven's default model is `llama3.2:3b`. Keep the model name consistent with the app's Settings if you change it. Ollama must be running locally before Benthoven starts.

### 7. Launch Benthoven

```powershell
python app.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860) in your browser. Keep the PowerShell window open while using the app. To stop the server, focus that window and press **Ctrl+C**.

---

## Installation on macOS

These instructions use Terminal and assume Python 3.11 or 3.12 is installed. You can download Python from [python.org](https://www.python.org/downloads/macos/) or use a package manager you already have.

### 1. Open the project folder

Extract the ZIP in Finder, then open Terminal and change to the extracted folder. For example, if it is in Downloads:

```bash
cd ~/Downloads/Benthoven-StudentAssistant-main
```

Adjust the path if you extracted it somewhere else.

### 2. Create and activate a virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

If you use Python 3.12, replace `python3.11` with `python3.12`.

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Install Tesseract (optional, but required for image OCR)

If Homebrew is installed:

```bash
brew install tesseract
```

Check that it works:

```bash
tesseract --version
```

If you do not use Homebrew, follow the [official Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html).

### 5. Install Ollama and the required Llama model

Install Ollama from [ollama.com/download](https://ollama.com/download), then run:

```bash
ollama pull llama3.2:3b
ollama list
```

Make sure the Ollama service is running before starting Benthoven.

### 6. Run the app

```bash
python app.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860). Keep Terminal open while the app is running. Press **Ctrl+C** in Terminal to stop it.

---

## Installation on Linux

The commands below are for Ubuntu or Debian-based distributions. Other distributions may use different package-manager commands.

### 1. Install Python and system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

Check your Python version:

```bash
python3 --version
```

Python 3.11 or 3.12 is recommended. If your distribution's default Python is older, install a supported version using the method recommended for that distribution.

### 2. Open the project folder

Extract the ZIP, then change to the extracted folder. For example:

```bash
cd ~/Downloads/Benthoven-StudentAssistant-main
```

### 3. Create the environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Install Tesseract (optional, but required for image OCR)

```bash
sudo apt install -y tesseract-ocr
tesseract --version
```

### 5. Install Ollama and the required Llama model

Install Ollama from [ollama.com/download](https://ollama.com/download), then run:

```bash
ollama pull llama3.2:3b
ollama list
```

Make sure the Ollama service is running before starting Benthoven.

### 6. Run the app

```bash
python app.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860) in your browser. Press **Ctrl+C** in the terminal to stop the app.

---

## Start the app

Before launching, ensure Ollama is running and `llama3.2:3b` appears in `ollama list`. The application exits with setup instructions if the required local service or model is missing.

Every time you want to use Benthoven again:

1. Open PowerShell (Windows) or Terminal (macOS/Linux).
2. Change directory to the project folder.
3. Activate the virtual environment.
4. Run `python app.py`.
5. Visit `http://127.0.0.1:7860` in your browser.

Activation commands:

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

If you see a message that the address or port is already in use, stop the other running Benthoven process first. The app reads the `PORT` environment variable if you need to choose a different port.

---

## First-time walkthrough

1. **Start the app** using the instructions above.
2. **Open Settings.** Review your weekday and weekend availability, focus window, session length, break length, daily study limit, and energy setting. Save your preferences.
3. **Capture an announcement.** Upload a supported text/image file or paste the announcement text. You can also add a task manually.
4. **Verify the extracted tasks.** Check the task title, subject, type, estimated effort, and especially the deadline. Relative phrases such as “next Friday” can depend on the date used for interpretation.
5. **Confirm only correct tasks.** Edit incorrect values and remove false detections. Do not assume OCR or AI is always correct.
6. **Generate a plan.** Review the timetable, priority explanations, and any warnings about conflicts or insufficient time.
7. **Track progress.** Mark study sessions complete or indicate that you could not do them. Regenerate the plan when your progress or availability changes.
8. **Export calendar sessions** if you want to import them into a calendar app that supports `.ics` files.

### Try the sample announcements

Use the files in `sample_docs/` to test task extraction without preparing your own files:

- `announcement_math.txt`
- `announcement_science.txt`
- `announcement_chat.txt`

For a predictable demo, use **Settings → Pretend today is** to set a date before the sample deadlines, then save and generate a plan. Restore the real date afterward.

---

## Required local AI with Ollama

Ollama and the configured Llama model are required for Benthoven. The app does not silently fall back to rule-based extraction or a cloud API when local AI is unavailable. Install Ollama and download the model before launching the app.

1. Install Ollama from [ollama.com/download](https://ollama.com/download).
2. Open a new terminal and download the default model:

   ```bash
   ollama pull llama3.2:3b
   ```

3. Make sure Ollama is running. On systems where it is not already running as a background service, start it with:

   ```bash
   ollama serve
   ```

   If Ollama is already running, do not start a second server.

4. The required model defaults to `llama3.2:3b`, and the local API address defaults to `http://localhost:11434`. If you change the model in Settings, pull that exact model first and restart Benthoven.
5. Test with a sample announcement and verify every suggested deadline before confirming it.

The model download requires internet access and uses disk space. Local model speed depends on your CPU, memory, and GPU. A smaller model may be slower or less accurate on complex announcements; the app's fallback does not remove the need to verify results.

---

## Run the tests

From the project root, with the virtual environment activated:

```bash
python -m pytest tests -q
```

To run a specific test file:

```bash
python -m pytest tests/test_core.py -v
```

If the tests fail, read the traceback and identify the first failing assertion or import error. Please include that output when reporting a bug.

---

## Privacy and offline behavior

Benthoven is designed to run locally:

- The dashboard binds to `127.0.0.1` by default, so it is intended for access from the same computer.
- Tasks, preferences, sessions, and captured text are stored in a local SQLite database. By default, the database is `data/benthoven.db` in the project directory.
- Tesseract OCR runs on the computer.
- The rule-based extraction path does not require a hosted AI service.
- Ollama sends model requests to the local Ollama service rather than a hosted model API. Ollama and its configured model are required for startup.

**Important:** “Local-first” does not automatically mean every operation is offline. You need internet to install dependencies and download models. The app also checks internet reachability for its privacy/status display. Do not upload sensitive school, personal, or other confidential information unless you understand and accept how your local computer and files are managed.

To run Benthoven offline, first install all software and download the configured Ollama model while connected to the internet. Then ensure Ollama is running and launch Benthoven; after setup, the AI requests stay on the local machine. Image capture additionally requires a working Tesseract installation.

### Back up or reset local data

- **Back up:** stop the app and copy `data/benthoven.db` to a safe location.
- **Restore:** stop the app and place your backed-up database at the same path.
- **Reset:** stop the app, back up the database if needed, and then delete `data/benthoven.db`. The app will create a new database on the next launch. This permanently removes the tasks, preferences, and progress stored in that database.

If you set the `BENTHOVEN_DB` environment variable, the database is stored at that custom path instead.

---

## Supported files

| Format | Supported? | Notes |
|---|---|---|
| `.txt` | Yes | Read as UTF-8 text |
| `.md` | Yes | Read as UTF-8 text |
| `.png`, `.jpg`, `.jpeg` | Yes | OCR requires Tesseract |
| `.bmp`, `.tif`, `.tiff`, `.webp` | Yes | OCR requires Tesseract |
| `.pdf` | Not currently | Copy/paste the text or convert the relevant page to an image first |
| `.docx`, `.pptx`, `.heic` | Not currently | Export or copy the announcement into a supported format |

Image OCR works best with sharp, well-lit images, readable text, and minimal skew. Review the extracted text and dates before confirming a task.

---

## Troubleshooting

### `python` or `py` is not recognized (Windows)

Install Python from [python.org](https://www.python.org/downloads/), enable PATH integration if offered, and reopen PowerShell. Check with `py --version` or `python --version`.

### `No module named ...`

Make sure the virtual environment is activated and install the dependencies again:

```bash
python -m pip install -r requirements.txt
```

### PowerShell says script execution is disabled

Run the temporary, current-terminal workaround in the Windows installation section, or use `.venv\Scripts\python.exe` directly without activating the environment.

### Image upload says Tesseract is not installed

Run `tesseract --version`. If the command is not found, install Tesseract and add its installation folder to PATH. Restart the terminal and launch Benthoven again. You can still paste text or use `.txt` / `.md` files without OCR.

### Ollama or the required model is unavailable

Check that Ollama is installed and running, then run `ollama list`. If the model is missing, run `ollama pull llama3.2:3b`. Confirm that `llama3.2:3b` appears in `ollama list`. Benthoven will not start without Ollama and the configured model; no rules-only or cloud fallback is used.

### The page does not open

- Confirm the terminal still shows the app running.
- Open `http://127.0.0.1:7860` exactly.
- If port 7860 is already occupied, stop the other process or set a different `PORT` before launching.
- If the browser reports that the connection was refused, check the terminal for the first error or traceback.

### Dates or tasks look wrong

OCR and extraction are suggestions, not authoritative records. Check the original announcement, edit the deadline and task details, and confirm the task only after reviewing it. For relative dates, set the correct “Pretend today is” date in Settings when testing.

### The schedule does not fit everything

Check the available study windows, existing commitments, estimated task duration, daily study limit, and deadlines. The scheduler cannot create time that is not available; review conflicts and warnings, adjust estimates or availability where appropriate, and regenerate the plan.

---

## Project structure

```text
Benthoven-StudentAssistant-main/
├── app.py                  # Gradio dashboard and app entry point
├── requirements.txt        # Python dependencies
├── benthoven/
│   ├── ocr.py              # Local image OCR through Tesseract
│   ├── dates.py            # Date/time parsing and ambiguity handling
│   ├── extractor.py        # Rule-based and optional Ollama extraction
│   ├── scheduler.py        # Task ranking, session planning, plan differences
│   ├── storage.py          # SQLite persistence and preferences
│   ├── narrator.py         # Optional local-AI summary rewriting
│   ├── ics.py              # Calendar (.ics) export
│   └── panels.py           # Dashboard header, tracker, calendar, and cards
├── sample_docs/            # Sample announcement text for demos
├── tests/                  # Automated tests
├── data/                   # Created locally for the SQLite database
└── .venv/                  # Created locally for Python dependencies
```

`data/` and `.venv/` are generated locally and may not appear in a fresh ZIP download.

## Known limitations

- Extracted task names, subjects, dates, and time estimates may be wrong; user review is essential.
- OCR quality depends on image clarity and the language data installed with Tesseract.
- PDF and office-document parsing are not implemented in the current MVP.
- Local AI performance varies by device and model; the rule-based fallback is less flexible with unusual wording.
- Scheduling results depend on the accuracy of task estimates, availability, commitments, and deadlines entered by the student.
- Calendar export creates an `.ics` file; it does not automatically sync changes with an external calendar.
- This is a local app, not a hosted multi-user service. Avoid exposing it to a public network without adding appropriate authentication and security controls.

## Development notes

- Keep the core workflow usable without Ollama.
- Treat extracted values as untrusted until the student verifies them.
- Prefer deterministic scheduling behavior that can be tested.
- Run `python -m pytest tests -q` after changes to extraction, dates, scheduling, or storage.
- Keep user data local by default and document any new network behavior.

## License

No license file is included in this project snapshot. Until a license is added, do not assume that the source is licensed for unrestricted redistribution or commercial reuse.
