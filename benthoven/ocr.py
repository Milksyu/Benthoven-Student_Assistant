"""Local OCR (Stage 1). OCR text is kept separate from any AI interpretation."""
from __future__ import annotations

from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from typing import Optional

TEXT_EXT = {".txt", ".md"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def ocr_available() -> bool:
    """Return whether the local RapidOCR runtime is installed."""
    return find_spec("rapidocr") is not None and find_spec("onnxruntime") is not None


@lru_cache(maxsize=1)
def _get_ocr_engine():
    """Create one reusable CPU OCR engine; model files ship with RapidOCR."""
    try:
        from rapidocr import RapidOCR
        return RapidOCR()
    except Exception as exc:
        raise RuntimeError(
            "Local OCR could not start. Reinstall the Python dependencies with "
            "`python -m pip install -r requirements.txt` and try again."
        ) from exc


def read_document(path: str) -> tuple[str, Optional[float]]:
    """Return (text, mean OCR confidence). Confidence is None for plain-text files."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in TEXT_EXT:
        return p.read_text(encoding="utf-8", errors="replace"), None
    if ext in IMAGE_EXT:
        if not ocr_available():
            raise RuntimeError(
                "Local OCR dependencies are missing. Run "
                "`python -m pip install -r requirements.txt`; no separate OCR program is needed."
            )

        import numpy as np
        from PIL import Image, ImageOps

        try:
            with Image.open(p) as source:
                img = ImageOps.exif_transpose(source).convert("RGB")
                # Upscale small screenshots to improve detection of small text.
                if min(img.size) < 1000:
                    scale = 1000 / min(img.size)
                    img = img.resize((int(img.width * scale), int(img.height * scale)))
                # RapidOCR's ndarray interface follows OpenCV's BGR channel order.
                image_array = np.asarray(img)[:, :, ::-1].copy()
            result = _get_ocr_engine()(image_array)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Local OCR could not read this image: {exc}") from exc

        lines = [str(line).strip() for line in (getattr(result, "txts", None) or ()) if str(line).strip()]
        scores = list(getattr(result, "scores", None) or ())
        text = "\n".join(lines)
        confidences = []
        for line, score in zip((str(v).strip() for v in (getattr(result, "txts", None) or ())), scores):
            if line and score is not None:
                try:
                    confidences.append(max(0.0, min(1.0, float(score))) * 100)
                except (TypeError, ValueError):
                    pass
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return text, confidence
    raise ValueError(
        f"Unsupported file type '{ext}'. Use an image, .txt, or .md "
        "(PDF support is a future feature)."
    )
