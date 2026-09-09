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
from lore_mcp.preprocess.dedup import find_exact_duplicates
from lore_mcp.preprocess.parse import FormatNotSupported, parse_to_markdown
from lore_mcp.preprocess.pii import detect_pii
from lore_mcp.preprocess.tables import protect_tables
from lore_mcp.preprocess.validate import quality_gate

logger = logging.getLogger(__name__)

__all__ = ["clean_text", "preprocess_file", "preprocess_sources"]


def _fetch_url(url: str, dest: Path) -> dict:
    """Download a URL to a local file."""
    import urllib.request
    import urllib.error

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lore-mcp/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return {"ok": True}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "error": str(e)}


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
    force: bool = False,
) -> list[dict]:
    """Preprocess sources listed in a manifest. Returns reports.

    Pipeline: resolve → parse → clean → extract metadata →
    dedup → validate → write.
    """
    manifest = parse_manifest(manifest_path)
    base = Path(docs_base_dir)
    orig_dir = base / orig_subdir
    prep_dir = base / prep_subdir
    prep_dir.mkdir(parents=True, exist_ok=True)

    enriched_sources = []
    reports = []
    parsed_contents = {}

    # Pass 1: resolve, parse, clean, extract metadata
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

        if resolved.get("url") and not (orig_dir / orig_name).exists():
            fetched = _fetch_url(resolved["url"], orig_dir / orig_name)
            if not fetched["ok"]:
                reports.append({
                    "file": resolved["path"],
                    "status": "error",
                    "message": f"Fetch failed: {fetched['error']}",
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

        try:
            text = parse_to_markdown(str(src_path))
        except (FormatNotSupported, ImportError) as e:
            reports.append({
                "file": resolved["path"],
                "status": "error",
                "message": str(e),
                "input_len": 0,
                "output_len": 0,
            })
            enriched_sources.append(resolved)
            continue

        input_len = len(text)
        cleaned = clean_text(text)
        cleaned = protect_tables(cleaned)

        pii_findings = detect_pii(cleaned)

        extracted = extract_source_metadata(cleaned, str(target_path))
        for key in ("title", "author", "url", "date", "license"):
            if key not in resolved or resolved[key] is None:
                if extracted.get(key):
                    resolved[key] = extracted[key]

        parsed_contents[resolved["path"]] = {
            "resolved": resolved,
            "cleaned": cleaned,
            "input_len": input_len,
            "target_path": target_path,
            "pii": pii_findings,
        }

    # Pass 2: dedup (exact hash on cleaned content)
    if parsed_contents:
        content_map = {p: d["cleaned"] for p, d in parsed_contents.items()}
        dedup_report = find_exact_duplicates(content_map)
        skip_set = set(dedup_report.to_skip)
    else:
        skip_set = set()

    # Pass 3: validate + write
    for path_key, data in parsed_contents.items():
        resolved = data["resolved"]
        cleaned = data["cleaned"]
        target_path = data["target_path"]

        if path_key in skip_set:
            reports.append({
                "file": resolved["path"],
                "status": "duplicate",
                "message": "Exact duplicate — skipped",
                "input_len": data["input_len"],
                "output_len": 0,
            })
            enriched_sources.append(resolved)
            continue

        # Quality gate
        file_out = prep_dir / target_path.parent
        file_out.mkdir(parents=True, exist_ok=True)
        out_file = file_out / target_path.name
        out_file.write_text(cleaned, encoding="utf-8")

        qg = quality_gate(str(out_file), force=force)

        if not qg["passed"]:
            out_file.unlink()
            reports.append({
                "file": resolved["path"],
                "status": "poor",
                "message": f"Quality gate failed: {qg['verdict']} "
                           f"(density={qg['text_density']}, use --force to override)",
                "input_len": data["input_len"],
                "output_len": len(cleaned),
            })
            enriched_sources.append(resolved)
            continue

        enriched_sources.append(resolved)
        report = {
            "file": resolved["path"],
            "status": "ok",
            "input_len": data["input_len"],
            "output_len": len(cleaned),
            "quality": qg["verdict"],
        }
        if data.get("pii"):
            report["pii"] = data["pii"]
        reports.append(report)

    # Write enriched manifest
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
