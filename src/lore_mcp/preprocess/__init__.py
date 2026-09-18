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
    judge_captions,
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


def _phase_path(prep_dir: Path, target: Path, phase: str) -> Path:
    """Build phase-suffixed output path."""
    return prep_dir / target.parent / f"{target.stem}.{phase}{target.suffix}"


def _write_phase(prep_dir: Path, target: Path, phase: str, text: str) -> Path:
    """Write text to a phase-suffixed file."""
    p = _phase_path(prep_dir, target, phase)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _cleanup_phase_files(prep_dir: Path, target: Path) -> None:
    """Remove intermediate phase files after final write."""
    for f in prep_dir.glob(f"{target.stem}.phase*{target.suffix}"):
        f.unlink(missing_ok=True)


def _describe_phases(caption_entries, llm_entry, enrich, caption_selection=""):
    """Build phase description for announcement."""
    phases = ["parse"]
    if caption_entries:
        names = [e.get("name", e.get("model", "?")) for e in caption_entries]
        phases.append(f"caption ({', '.join(names)})")
        if len(caption_entries) > 1 and caption_selection:
            phases[-1] += f" → {caption_selection}"
    llm_name = (llm_entry or {}).get("name", (llm_entry or {}).get("model", ""))
    if enrich and llm_name:
        phases.append(f"clean+enrich (LLM: {llm_name}, techniques: {','.join(enrich)})")
    elif enrich:
        phases.append(f"clean+enrich (techniques: {','.join(enrich)})")
    else:
        phases.append("clean")
    phases.append("validate+write")
    return phases


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
    caption_entries: list[dict] | None = None,
    judge_entry: dict | None = None,
    caption_selection: str = "first_nonempty",
    output_level: str = "default",
) -> list[dict]:
    """Preprocess sources listed in a manifest. Returns reports.

    Pipeline phases (each writes to disk with phase suffix):
    1. Parse ALL sources (Docling/trafilatura/markitdown, no LLM)
    2. Caption images — one sub-phase per model (start/stop IS)
    3. Clean + Enrich via LLM (start/stop IS)
    4. Dedup + Validate + Write final (no model)
    """
    # Backward compat: vlm_entry → single caption_entries
    if vlm_entry and not caption_entries:
        caption_entries = [vlm_entry]
        if caption_selection == "first_nonempty":
            caption_selection = "first_nonempty"
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

    # ── Phase announcement ─────────────────────────────────────
    phase_list = _describe_phases(caption_entries, llm_entry, enrich, caption_selection)
    phase_meta = {
        "phases": [p.split(" (")[0] for p in phase_list],
        "caption_models": [e.get("name", e.get("model", "")) for e in (caption_entries or [])],
        "caption_selection": caption_selection if caption_entries and len(caption_entries) > 1 else "",
        "llm": (llm_entry or {}).get("model", ""),
        "enrich_techniques": enrich or [],
    }
    if not quiet:
        print(f"  Active phases: {', '.join(phase_list)}")

    # ── Phase 1: Resolve + Parse (no LLM/VLM) ──────────────────
    parsed = {}
    phase1_count = 0
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

        _write_phase(_prep_dir, target_path, "phase1-parse", text)
        phase1_count += 1

        if not quiet:
            print(" → ok")

        parsed[resolved["path"]] = {
            "resolved": resolved,
            "text": text,
            "src_path": src_path,
            "target_path": target_path,
        }

    unload_docling()

    # ── Phase 2: Caption images — one sub-phase per model ─────
    has_images = any(
        d.get("text") is not None and (
            d.get("src_path") and (
                d["src_path"].suffix.lower() in IMAGE_EXTENSIONS
                or "data:image/" in (d.get("text") or "")
            )
        )
        for d in parsed.values()
    )

    caption_stats = {"captioned": 0, "skipped": 0, "failed": 0}
    ocr_cache = {}
    model_results = {}  # path_key -> {model_name: caption_text}

    if has_images and caption_entries:
        for model_idx, cap_entry in enumerate(caption_entries):
            model_name = cap_entry.get("name", f"model{model_idx}")
            cap_url = cap_entry.get("api_url", "")
            cap_model = cap_entry.get("model", "")
            cap_key = cap_entry.get("api_key", "")

            if not cap_url:
                continue

            if not quiet:
                print(f"  Phase 2.{model_idx + 1}: Caption ({model_name})")

            start_service(cap_entry)
            try:
                for path_key, data in parsed.items():
                    if data.get("text") is None:
                        continue

                    resolved = data["resolved"]
                    src_path = data.get("src_path")
                    if not src_path:
                        continue
                    target_path = data["target_path"]
                    source_desc = resolved.get("description", "")
                    source_context = f"{resolved.get('title', '')} — {manifest.get('collection', '')}"

                    result_text = None

                    if src_path.suffix.lower() in IMAGE_EXTENSIONS:
                        ocr_text = data.get("text", "")
                        if not quiet:
                            print(f"    {src_path.name} → caption", flush=True)
                        try:
                            caption = caption_image(
                                src_path, cap_url, cap_model, cap_key,
                                context=source_context + ("\n\nOCR text:\n" + ocr_text if ocr_text else ""),
                                description=source_desc,
                            )
                            if caption:
                                result_text = caption
                                caption_stats["captioned"] += 1
                        except Exception as e:
                            caption_stats["failed"] += 1
                            logger.warning("Caption failed (%s) for %s: %s", model_name, src_path.name, e)

                    elif "data:image/" in data["text"]:
                        if not quiet:
                            print(f"    {src_path.name} → inline captions", flush=True)

                        phase_tag = f"phase2-caption-{model_name}"

                        def _save_progress(updated_text, _tp=target_path, _pt=phase_tag):
                            _write_phase(_prep_dir, _tp, _pt, updated_text)

                        try:
                            result_text = caption_inline_images(
                                data["text"], cap_url, cap_model, cap_key,
                                context=source_context, description=source_desc,
                                on_progress=_save_progress,
                                ocr_cache=ocr_cache,
                            )
                            caption_stats["captioned"] += 1
                        except Exception as e:
                            caption_stats["failed"] += 1
                            logger.warning("Inline captions failed (%s) for %s: %s", model_name, src_path.name, e)

                    if result_text is not None:
                        if path_key not in model_results:
                            model_results[path_key] = {}
                        model_results[path_key][model_name] = result_text
                        _write_phase(_prep_dir, target_path, f"phase2-caption-{model_name}", result_text)
            finally:
                stop_service(cap_entry)

        # Select/fuse captions from multiple models
        if model_results:
            if not quiet and len(caption_entries) > 1:
                print(f"  Phase 2 selection: {caption_selection}")
            for path_key, captions_by_model in model_results.items():
                data = parsed[path_key]
                if not captions_by_model:
                    continue
                if len(captions_by_model) == 1 or caption_selection == "first_nonempty":
                    data["text"] = next(v for v in captions_by_model.values() if v)
                elif caption_selection == "longest":
                    data["text"] = max(captions_by_model.values(), key=len)
                elif caption_selection == "judge" and judge_entry:
                    ocr_text = ocr_cache.get(path_key, "")
                    alt_text = data["resolved"].get("description", "")
                    judge_url = judge_entry.get("api_url", "")
                    judge_model = judge_entry.get("model", "")
                    judge_key = judge_entry.get("api_key", "")
                    try:
                        if not quiet:
                            print(f"    {data['resolved']['orig']} → judge", flush=True)
                        start_service(judge_entry)
                        data["text"] = judge_captions(
                            ocr_text, alt_text, captions_by_model,
                            judge_url, judge_model, judge_key,
                        )
                        stop_service(judge_entry)
                    except Exception as e:
                        logger.warning("Judge failed for %s: %s", path_key, e)
                        data["text"] = next(v for v in captions_by_model.values() if v)
                else:
                    data["text"] = next(v for v in captions_by_model.values() if v)
    elif not quiet and caption_entries:
        print("  Phase 2: Caption (skipped — no images)")

    # ── Phase 3: Clean + Enrich ─────────────────────────────────
    llm_url = (llm_entry or {}).get("api_url", "")
    llm_model_name = (llm_entry or {}).get("model", "")
    llm_key = (llm_entry or {}).get("api_key", "")

    phase3_label = "enrich" if enrich else "clean"
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
            target_path = data["target_path"]
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

            extracted = extract_source_metadata(cleaned, str(target_path))
            for key in ("title", "author", "url", "date", "license"):
                if key not in resolved or resolved[key] is None:
                    if extracted.get(key):
                        resolved[key] = extracted[key]

            if not quiet:
                delta = input_len - len(cleaned)
                print(f" → done ({delta:+d} chars)")

            _write_phase(_prep_dir, target_path, f"phase3-{phase3_label}", cleaned)

            data["cleaned"] = cleaned
            data["input_len"] = input_len
            data["pii"] = pii_findings
    finally:
        if enrich and llm_entry:
            stop_service(llm_entry)

    # ── Phase 4: Dedup + Validate + Write ───────────────────────
    if not quiet:
        print("  Phase 4: Validate + Write")

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
    write_count = 0
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

        _cleanup_phase_files(_prep_dir, target_path)
        write_count += 1

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

    # Phase summary
    if not quiet:
        summary_parts = [f"parse ({phase1_count}/{total})"]
        if has_images and caption_entries:
            n_models = len(caption_entries)
            summary_parts.append(
                f"caption ({n_models} model{'s' if n_models > 1 else ''}, "
                f"{caption_stats['captioned']} ok, "
                f"{caption_stats['failed']} failed)"
            )
        summary_parts.append(f"clean+{phase3_label} ({len(content_map)}/{total})")
        summary_parts.append(f"write ({write_count}/{total})")
        print(f"  Phases completed: {', '.join(summary_parts)}")

    # Add phase metadata to report
    report_data = {
        "ok": [r["file"] for r in reports if r["status"] == "ok"],
        "missing": [r["file"] for r in reports if r["status"] == "missing"],
        "error": [r["file"] for r in reports if r["status"] == "error"],
        "poor": [r["file"] for r in reports if r["status"] == "poor"],
        "pii": [
            {"file": r["file"], "findings": r["pii"]}
            for r in reports if r.get("pii")
        ],
        "duplicates": [
            {"file": r["file"], "type": r["duplicate"]}
            for r in reports if r.get("duplicate")
        ],
        "phases": phase_meta,
    }

    report_path = _prep_dir / "preprocess-report.json"
    import json
    report_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if not quiet:
        print(f"\n{len([r for r in reports if r['status'] == 'ok'])} files preprocessed → {_prep_dir}")
        print(f"  Report: {report_path}")

    return reports
