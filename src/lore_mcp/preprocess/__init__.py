"""Preprocessing pipeline for RAG-ready markdown. See docs/preprocessing.md."""

import logging
from pathlib import Path

import yaml

from lore_mcp.manifest import (
    extract_source_metadata,
    parse_manifest,
    resolve_source_fields,
)
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
    docs_base_dir: str,
    orig_subdir: str = ".",
    prep_subdir: str = ".",
    manifest_out: str | None = None,
) -> list[dict]:
    """Preprocess sources listed in a manifest. Returns reports.

    Applies field cascade (resolve_source_fields), reads orig files,
    cleans them, writes to prep dir, extracts metadata, and produces
    an enriched manifest copy.
    """
    manifest = parse_manifest(manifest_path)
    base = Path(docs_base_dir)
    orig_dir = base / orig_subdir
    prep_dir = base / prep_subdir
    prep_dir.mkdir(parents=True, exist_ok=True)

    enriched_sources = []
    reports = []

    for source in manifest["sources"]:
        try:
            resolved = resolve_source_fields(source)
        except ValueError as e:
            reports.append({
                "file": source.get("orig", source.get("url", "?")),
                "status": "error",
                "message": str(e),
                "input_len": 0,
                "output_len": 0,
            })
            continue

        orig_name = resolved["orig"]
        target_path = Path(resolved["path"])

        if not resolved.get("url") or resolved.get("orig") != Path(resolved["url"]).name if resolved.get("url") else False:
            pass
        if resolved.get("url") and not (orig_dir / orig_name).exists():
            reports.append({
                "file": resolved["path"],
                "status": "url",
                "message": f"URL fetch not implemented — fetch manually: {resolved['url']}",
                "input_len": 0,
                "output_len": 0,
            })
            enriched_sources.append(resolved)
            continue

        src_path = orig_dir / orig_name
        if not src_path.exists():
            reports.append({
                "file": resolved["path"],
                "status": "missing",
                "message": f"Original file not found: {orig_name}",
                "input_len": 0,
                "output_len": 0,
            })
            enriched_sources.append(resolved)
            continue

        text = src_path.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_text(text)

        extracted = extract_source_metadata(cleaned, str(target_path))
        for key in ("title", "author", "url", "date", "license"):
            if key not in resolved or resolved[key] is None:
                if extracted.get(key):
                    resolved[key] = extracted[key]

        file_out = prep_dir / target_path.parent
        file_out.mkdir(parents=True, exist_ok=True)
        (file_out / target_path.name).write_text(cleaned, encoding="utf-8")

        enriched_sources.append(resolved)
        reports.append({
            "file": resolved["path"],
            "status": "ok",
            "input_len": len(text),
            "output_len": len(cleaned),
        })

    if manifest_out is None:
        mp = Path(manifest_path)
        manifest_out = str(mp.parent / f"{mp.stem}-prep{mp.suffix}")

    enriched = {
        "collection": manifest.get("collection", ""),
        "level": manifest.get("level", ""),
        "sources": enriched_sources,
    }
    Path(manifest_out).write_text(
        yaml.dump(enriched, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    return reports
