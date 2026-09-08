"""Preprocessing pipeline for RAG-ready markdown. See docs/preprocessing.md."""

import logging
from pathlib import Path

from lore_mcp.manifest import parse_manifest
from lore_mcp.preprocess.clean import clean_text

logger = logging.getLogger(__name__)

__all__ = ["clean_text", "preprocess_file", "preprocess_sources"]


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


def preprocess_sources(
    manifest_path: str,
    docs_dir: str,
    output_dir: str,
) -> list[dict]:
    """Preprocess sources listed in a manifest. Returns reports."""
    manifest = parse_manifest(manifest_path)
    docs = Path(docs_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    reports = []
    for source in manifest["sources"]:
        src_path = docs / source["path"]
        if not src_path.exists():
            reports.append({
                "file": source["path"],
                "status": "missing",
                "input_len": 0,
                "output_len": 0,
            })
            continue

        rel = Path(source["path"])
        file_out = out / rel.parent
        file_out.mkdir(parents=True, exist_ok=True)

        text = src_path.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_text(text)

        (file_out / rel.name).write_text(cleaned, encoding="utf-8")

        reports.append({
            "file": source["path"],
            "status": "ok",
            "input_len": len(text),
            "output_len": len(cleaned),
        })

    return reports
