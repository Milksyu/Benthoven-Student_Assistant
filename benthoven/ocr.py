"""Local OCR (Stage 1). OCR text is kept separate from any AI interpretation."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

TEXT_EXT = {".txt", ".md"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


_WINDOWS_DEFAULTS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
)


def find_tesseract() -> str | None:
    """PATH first, then the TESSERACT_CMD variable, then the usual Windows install folders."""
    found = shutil.which("tesseract")
    if found:
        return found
    for cand in (os.environ.get("TESSERACT_CMD", ""), *_WINDOWS_DEFAULTS):
        if cand and os.path.isfile(cand):
            return cand
    return None


def tesseract_available() -> bool:
    return find_tesseract() is not None


def read_document(path: str) -> tuple[str, Optional[float]]:
    """Return (text, mean_ocr_confidence). Confidence is None for plain-text files."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in TEXT_EXT:
        return p.read_text(encoding="utf-8", errors="replace"), None
    if ext in IMAGE_EXT:
        if not tesseract_available():
            raise RuntimeError("Tesseract is not installed. Install it (see README) or paste the text instead.")
        import pytesseract
        from PIL import Image, ImageOps

        pytesseract.pytesseract.tesseract_cmd = find_tesseract()

        img = Image.open(p)
        img = ImageOps.exif_transpose(img).convert("L")
        if min(img.size) < 1000:  # upscale small screenshots; Tesseract likes ~300 DPI text
            scale = 1000 / min(img.size)
            img = img.resize((int(img.width * scale), int(img.height * scale)))
        img = ImageOps.autocontrast(img)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 6")
        words, confs = [], []
        for w, c in zip(data["text"], data["conf"]):
            if w.strip():
                words.append(w)
                if float(c) >= 0:
                    confs.append(float(c))
        text = pytesseract.image_to_string(img, config="--psm 6")
        return text, (sum(confs) / len(confs) if confs else 0.0)
    raise ValueError(f"Unsupported file type '{ext}'. Use an image, .txt, or .md (PDF support is a future feature).")
