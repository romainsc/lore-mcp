"""Preprocessing pipeline for RAG-ready markdown. See docs/preprocessing.md."""

import logging
from pathlib import Path

from lore_mcp.preprocess.clean import clean_text

logger = logging.getLogger(__name__)

__all__ = ["clean_text", "preprocess_file", "preprocess_dir"]


def preprocess_file(source_path: str, output_dir: str) -> dict:
    """Preprocess a single markdown file. Returns a report dict."""
    src = Path(source_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    text = src.read_text(encoding="utf-8", errors="replace")
    cleaned = clean_text(text)

    output_file = out / src.name
    output_file.write_text(cleaned, encoding="utf-8")

    return {
        "file": src.name,
        "status": "ok",
        "input_len": len(text),
        "output_len": len(cleaned),
    }


def preprocess_dir(source_dir: str, output_dir: str) -> list[dict]:
    """Preprocess all markdown files in a directory tree. Returns reports."""
    src = Path(source_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    reports = []
    for md_file in sorted(src.rglob("*.md")):
        rel = md_file.relative_to(src)
        file_out = out / rel.parent
        file_out.mkdir(parents=True, exist_ok=True)

        text = md_file.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_text(text)

        (file_out / md_file.name).write_text(cleaned, encoding="utf-8")

        reports.append({
            "file": str(rel),
            "status": "ok",
            "input_len": len(text),
            "output_len": len(cleaned),
        })

    return reports
