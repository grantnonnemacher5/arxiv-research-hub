import logging

import fitz  # PyMuPDF
import requests

from config import FULL_TEXT_MAX_CHARS

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_url: str, timeout: int = 30) -> str | None:
    try:
        response = requests.get(pdf_url, timeout=timeout)
        response.raise_for_status()
        doc = fitz.open(stream=response.content, filetype="pdf")
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        text = "\n".join(parts).strip()
        if not text:
            return None
        return text[:FULL_TEXT_MAX_CHARS]
    except Exception as exc:
        logger.warning("PDF extract failed for %s: %s", pdf_url, exc)
        return None
