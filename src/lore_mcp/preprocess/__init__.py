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
    orig_dir: str,
    output_dir: str,
) -> list[dict]:
    """Preprocess sources listed in a manifest. Returns reports.

    Each manifest source must have an 'orig' field (filename in orig_dir)
    or a 'url' field (to fetch). Sources with neither get an error report.
    Output files are written to output_dir using the source 'path' field.
    """
    manifest = parse_manifest(manifest_path)
    orig = Path(orig_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    reports = []
    for source in manifest["sources"]:
        target_path = Path(source["path"])
        orig_name = source.get("orig")
        url = source.get("url")

        if not orig_name and not url:
            reports.append({
                "file": source["path"],
                "status": "error",
                "message": "No orig field and no url — cannot locate source",
                "input_len": 0,
                "output_len": 0,
            })
            continue

        if not orig_name and url:
            reports.append({
                "file": source["path"],
                "status": "url",
                "message": f"URL fetch not implemented — fetch manually: {url}",
                "input_len": 0,
                "output_len": 0,
            })
            continue

        src_path = orig / orig_name
        if not src_path.exists():
            reports.append({
                "file": source["path"],
                "status": "missing",
                "message": f"Original file not found: {orig_name}",
                "input_len": 0,
                "output_len": 0,
            })
            continue

        text = src_path.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_text(text)

        file_out = out / target_path.parent
        file_out.mkdir(parents=True, exist_ok=True)
        (file_out / target_path.name).write_text(cleaned, encoding="utf-8")

        reports.append({
            "file": source["path"],
            "status": "ok",
            "input_len": len(text),
            "output_len": len(cleaned),
        })

    return reports
