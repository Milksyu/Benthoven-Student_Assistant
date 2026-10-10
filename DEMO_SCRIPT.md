# Demo video script (about 3 minutes)

Record the screen and your voice. Use real functionality only: no pre-written output.

**Before recording**
1. `python preflight.py` shows no FAIL lines and the "local inference works" line passes.
2. Delete `data/benthoven.db` for a clean start, then run `python app.py`.
3. Have 2 or 3 phone photos or screenshots of real or mock announcements ready (one with an unclear date), plus the files in `sample_docs/`. Close other windows.

**Script**
1. **0:00 Hook (15 s).** "Students get deadlines as photos and chat messages scattered everywhere. Benthoven turns them into a verified, realistic study plan, and nothing ever leaves this laptop."
2. **0:15 Offline proof (25 s).** Turn Wi-Fi off on camera. Point at the header chips: Local AI ✅ with the model name, OCR ✅, "Runs only on this computer".
3. **0:40 Capture + local AI (40 s).** Click **Capture**, select several photos at once, click **Extract tasks**. Show the message: "Local AI: llama3.2:3b · N s".
4. **1:20 Evidence-first (40 s).** Under **To verify**, show the source sentence and the warning on the ambiguous date. Fix the date, press **Confirm**, and watch the chart and table update.
5. **2:00 Plan (35 s).** Click **Plan my week**. Show the sessions grouped by day and explain why the big project starts before the small worksheet. Click **Export .ics**.
6. **2:35 Adapt + study (30 s).** Change a task's status in the table (Not started, then In progress) and show the chart change. Open the 💬 study assistant and click "What should I study first?": it answers from your real deadlines, locally.
7. **3:05 Close (10 s).** "Local AI means private by design, works offline, and costs nothing to use. Progress saves automatically. Code and disclosures are in the repo."

**Posting:** post the video on X or LinkedIn (public), copy its URL, and put it in `SUBMISSION.md` and the submission form.
