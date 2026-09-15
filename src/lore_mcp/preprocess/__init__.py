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
from lore_mcp.preprocess.dedup import find_exact_duplicates, find_near_duplicates
from lore_mcp.preprocess.parse import (
    FormatNotSupported,
    IMAGE_EXTENSIONS,
    caption_image,
    caption_inline_images,
    classify_parse_result,
    parse_to_markdown,
    unload_docling,
)
from lore_mcp.preprocess.enrich import enrich_context, enrich_meta, enrich_qa
from lore_mcp.preprocess.pii import detect_pii
from lore_mcp.preprocess.service import start_service, stop_service
from lore_mcp.preprocess.validate import quality_gate

logger = logging.getLogger(__name__)

__all__ = ["clean_text", "preprocess_file", "preprocess_sources"]


def _load_urls_file(path: Path) -> list[dict]:
    """Read urls.txt and return manifest source entries."""
    sources = []
    for line in path.read_text(encoding="utf-8").splitlines():
        url = line.strip()
        if url and not url.startswith("#"):
            sources.append({"url": url})
    return sources


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
    orig_dir: str = "",
    prep_dir: str = "",
    manifest_out: str | None = None,
    force: bool = False,
    enrich: list[str] | None = None,
    llm_entry: dict | None = None,
    vlm_entry: dict | None = None,
    output_level: str = "default",
) -> list[dict]:
    """Preprocess sources listed in a manifest. Returns reports.

    Pipeline phases:
    1. Parse ALL sources (Docling/trafilatura/markitdown, no LLM)
    2. Caption images via VLM (start/stop IS)
    3. Clean + Enrich via LLM (start/stop IS)
    4. Dedup + Validate + Write (no model)
    """
    manifest = parse_manifest(manifest_path)
    base = Path(docs_base_dir)

    _orig_dir = Path(orig_dir) if orig_dir else base
    _prep_dir = Path(prep_dir) if prep_dir else base
    if not _orig_dir.is_absolute():
        _orig_dir = base / _orig_dir
    if not _prep_dir.is_absolute():
        _prep_dir = base / _prep_dir
    _prep_dir.mkdir(parents=True, exist_ok=True)

    urls_file = base / "urls.txt"
    if urls_file.exists():
        url_sources = _load_urls_file(urls_file)
        manifest["sources"].extend(url_sources)
        logger.info("Loaded %d URLs from %s", len(url_sources), urls_file)

    reports = []
    quiet = output_level == "quiet"
    total = len(manifest["sources"])

    # ── Phase 1: Resolve + Parse (no LLM/VLM) ──────────────────
    parsed = {}
    if not quiet:
        print("  Phase 1: Parse")
    for src_idx, source in enumerate(manifest["sources"], 1):
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
        orig_was_explicit = "orig" in source

        if not quiet:
            print(f"    [{src_idx}/{total}] {orig_name}", end="", flush=True)

        if not (_orig_dir / orig_name).exists():
            if orig_was_explicit:
                if not quiet:
                    print(" → MISSING")
                reports.append({
                    "file": resolved["path"],
                    "status": "missing",
                    "message": f"Original file not found: {orig_name}",
                    "input_len": 0,
                    "output_len": 0,
                })
                parsed[resolved["path"]] = {"resolved": resolved, "text": None}
                continue
            elif resolved.get("url"):
                fetched = _fetch_url(resolved["url"], _orig_dir / orig_name)
                if not fetched["ok"]:
                    reports.append({
                        "file": resolved["path"],
                        "status": "error",
                        "message": f"Fetch failed: {fetched['error']}",
                        "input_len": 0,
                        "output_len": 0,
                    })
                    parsed[resolved["path"]] = {"resolved": resolved, "text": None}
                    continue

        src_path = _orig_dir / orig_name
        if not src_path.exists():
            reports.append({
                "file": resolved["path"],
                "status": "missing",
                "message": f"Original file not found: {orig_name}",
                "input_len": 0,
                "output_len": 0,
            })
            parsed[resolved["path"]] = {"resolved": resolved, "text": None}
            continue

        try:
            if not quiet:
                print(" → parse", end="", flush=True)
            text = parse_to_markdown(str(src_path))
        except (FormatNotSupported, ImportError, Exception) as e:
            reports.append({
                "file": resolved["path"],
                "status": "error",
                "message": str(e),
                "input_len": 0,
                "output_len": 0,
            })
            parsed[resolved["path"]] = {"resolved": resolved, "text": None}
            continue

        if not quiet:
            print(" → ok")

        parsed[resolved["path"]] = {
            "resolved": resolved,
            "text": text,
            "src_path": src_path,
            "target_path": target_path,
        }

    unload_docling()

    # ── Phase 2: Caption images via VLM ─────────────────────────
    vlm_url = (vlm_entry or {}).get("api_url", "")
    vlm_model = (vlm_entry or {}).get("model", "")
    vlm_key = (vlm_entry or {}).get("api_key", "")

    needs_vlm = vlm_url and any(
        d.get("text") is not None and (
            d["src_path"].suffix.lower() in IMAGE_EXTENSIONS
            or "data:image/" in (d.get("text") or "")
        )
        for d in parsed.values()
        if d.get("src_path")
    )

    if needs_vlm:
        if not quiet:
            print("  Phase 2: Caption (VLM)")
        if vlm_entry:
            start_service(vlm_entry)
        try:
            for path_key, data in parsed.items():
                if data.get("text") is None:
                    continue

                resolved = data["resolved"]
                src_path = data["src_path"]
                source_desc = resolved.get("description", "")
                source_context = f"{resolved.get('title', '')} — {manifest.get('collection', '')}"

                # Standalone images with empty parse result
                if src_path.suffix.lower() in IMAGE_EXTENSIONS:
                    quality = classify_parse_result(data["text"], src_path.suffix)
                    if quality == "empty":
                        if not quiet:
                            print(f"    {src_path.name} → caption", flush=True)
                        caption = caption_image(
                            src_path, vlm_url, vlm_model, vlm_key,
                            context=source_context, description=source_desc,
                        )
                        if caption:
                            data["text"] = caption

                # Inline base64 images in markdown
                elif "data:image/" in data["text"]:
                    if not quiet:
                        print(f"    {src_path.name} → inline captions", flush=True)
                    data["text"] = caption_inline_images(
                        data["text"], vlm_url, vlm_model, vlm_key,
                        context=source_context, description=source_desc,
                    )
        finally:
            if vlm_entry:
                stop_service(vlm_entry)
    elif not quiet and vlm_url:
        print("  Phase 2: Caption (skipped — no images)")

    # ── Phase 3: Clean + Enrich ─────────────────────────────────
    llm_url = (llm_entry or {}).get("api_url", "")
    llm_model_name = (llm_entry or {}).get("model", "")
    llm_key = (llm_entry or {}).get("api_key", "")

    if not quiet:
        label = "Clean + Enrich" if enrich else "Clean"
        print(f"  Phase 3: {label}")

    if enrich and llm_entry:
        start_service(llm_entry)
    try:
        for path_key, data in parsed.items():
            if data.get("text") is None:
                continue

            resolved = data["resolved"]
            text = data["text"]
            input_len = len(text)

            if not quiet:
                print(f"    {resolved['orig']} → clean", end="", flush=True)
            cleaned = clean_text(text)

            if enrich and "context" in enrich:
                if not quiet:
                    print(" → enrich:context", end="", flush=True)
                cleaned = enrich_context(cleaned, llm_url, llm_model_name, llm_key)
            if enrich and "qa" in enrich:
                if not quiet:
                    print(" → enrich:qa", end="", flush=True)
                cleaned = enrich_qa(cleaned, llm_url, llm_model_name, llm_key)
            if enrich and "meta" in enrich:
                if not quiet:
                    print(" → enrich:meta", end="", flush=True)
                cleaned = enrich_meta(cleaned, llm_url, llm_model_name, llm_key)

            pii_findings = detect_pii(cleaned)

            extracted = extract_source_metadata(cleaned, str(data["target_path"]))
            for key in ("title", "author", "url", "date", "license"):
                if key not in resolved or resolved[key] is None:
                    if extracted.get(key):
                        resolved[key] = extracted[key]

            if not quiet:
                delta = input_len - len(cleaned)
                print(f" → done ({delta:+d} chars)")

            data["cleaned"] = cleaned
            data["input_len"] = input_len
            data["pii"] = pii_findings
    finally:
        if enrich and llm_entry:
            stop_service(llm_entry)

    # ── Phase 4: Dedup + Validate + Write ───────────────────────
    if not quiet:
        print("  Phase 4: Validate + Write")

    # Dedup analysis (report-only)
    dup_warnings = {}
    content_map = {p: d["cleaned"] for p, d in parsed.items() if "cleaned" in d}
    if content_map:
        exact_report = find_exact_duplicates(content_map)
        for group in exact_report.duplicates:
            for f in group["files"][1:]:
                dup_warnings[f] = "exact duplicate"
        near_report = find_near_duplicates(content_map, threshold=0.8)
        for group in near_report.duplicates:
            for f in group["files"][1:]:
                if f not in dup_warnings:
                    dup_warnings[f] = "near-duplicate"

    enriched_sources = []
    for path_key, data in parsed.items():
        resolved = data["resolved"]

        if "cleaned" not in data:
            enriched_sources.append(resolved)
            continue

        cleaned = data["cleaned"]
        target_path = data["target_path"]

        file_out = _prep_dir / target_path.parent
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
        if path_key in dup_warnings:
            report["duplicate"] = dup_warnings[path_key]
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
