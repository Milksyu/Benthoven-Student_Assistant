"""Benthoven: offline academic planner. Run with:  python app.py

Local-first: serves on 127.0.0.1 only, stores data in ./data/benthoven.db, and talks only to
localhost services (Tesseract binary, Ollama on localhost:11434).
"""
from __future__ import annotations

import os
import webbrowser

from benthoven import storage as db
from benthoven.extractor import ollama_status
from benthoven.web import serve


def check_local_ai_or_exit() -> None:
    """Fail fast when the required local Ollama service/model is unavailable."""
    prefs = db.get_prefs()
    status = ollama_status(prefs["ollama_url"], prefs["ollama_model"])
    if not status["running"]:
        raise SystemExit("\nBenthoven requires Ollama running locally.\n1. Install Ollama from https://ollama.com/download\n"
                         f"2. Start Ollama, then run: ollama pull {prefs['ollama_model']}\n3. Run Benthoven again: python app.py\n")
    if not status["model_ready"]:
        raise SystemExit(f"\nBenthoven requires the local model '{prefs['ollama_model']}'.\n"
                         f"Run: ollama pull {prefs['ollama_model']}\nThen run Benthoven again: python app.py\n")


if __name__ == "__main__":
    check_local_ai_or_exit()
    port = int(os.environ.get("PORT", 7860))
    webbrowser.open(f"http://127.0.0.1:{port}")
    serve(port)
