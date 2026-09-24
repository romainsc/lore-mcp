"""Preprocessing pipeline for RAG-ready markdown. See docs/preprocessing.md."""

import logging
from pathlib import Path

import yaml

from lore_mcp.manifest import (
    expand_directory_entries,
    extract_source_metadata,
    parse_manifest,
    resolve_source_fields,
)
from lore_mcp.preprocess.clean import clean_text
from lore_mcp.preprocess.dedup import find_exact_duplicates, find_near_duplicates
from lore_mcp.preprocess.parse import (
    FormatNotSupported,
    IMAGE_EXTENSIONS,
    caption_inline_frames,
    caption_standalone_image,
    caption_with_docling,
    classify_parse_result,
    detect_format,
    judge_captions,
    parse_to_markdown,
    parse_video,
    transcribe_audio,
    unload_docling,
)
from lore_mcp.preprocess.enrich import enrich_context, enrich_meta, enrich_qa
from lore_mcp.preprocess.pii import detect_pii
from lore_mcp.preprocess.service import start_service, stop_service, capture_service_logs
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
    """Build phase-suffixed output path. Always .md (preprocessing output is markdown)."""
    if target.suffix.lower() == ".md":
        return prep_dir / target.parent / f"{target.stem}.{phase}.md"
    return prep_dir / target.parent / f"{target.stem}.{phase}{target.suffix}.md"


def _write_phase(prep_dir: Path, target: Path, phase: str, text: str) -> Path:
    """Write text to a phase-suffixed file."""
    p = _phase_path(prep_dir, target, phase)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _cleanup_phase_files(prep_dir: Path, target: Path) -> None:
    """Remove intermediate phase files after final write."""
    for pattern in [f"{target.stem}.phase*.md",
                    f"{target.stem}.caption-*.md",
                    f"{target.stem}.docling.json"]:
        for f in prep_dir.glob(pattern):
            f.unlink(missing_ok=True)


def _write_report(prep_dir: Path, reports: list, phase_meta: dict | None = None):
    """Write preprocess report incrementally. See E12.69."""
    import json as _j
    data = {
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
    }
    if phase_meta:
        data["phases"] = phase_meta
    (prep_dir / "preprocess-report.json").write_text(
        _j.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
    )


def _describe_phases(caption_models, llm_entry, enrich):
    """Build phase description for announcement."""
    phases = ["parse"]
    if caption_models:
        names = [e.get("name", e.get("model", "?")) for e in caption_models]
        phases.append(f"caption ({', '.join(names)})")
    llm_name = (llm_entry or {}).get("name", (llm_entry or {}).get("model", ""))
    if enrich and llm_name:
        phases.append(f"clean+enrich (LLM: {llm_name}, techniques: {','.join(enrich)})")
    elif enrich:
        phases.append(f"clean+enrich (techniques: {','.join(enrich)})")
    else:
        phases.append("clean")
    phases.append("validate+write")
    return phases


def _phase1_worker(manifest_path, docs_base_dir, orig_dir, prep_dir,
                   report_path, output_level, ocr_engine="", ocr_lang=None,
                   allow_download=False):
    """Parse all sources in a subprocess. Writes phase1 files + report JSON.

    Pure parse — no captioning. Saves Docling document as JSON
    for later captioning (parse-once, caption-N).
    """
    import json as _json

    manifest = parse_manifest(manifest_path)
    base = Path(docs_base_dir)
    _orig_dir = Path(orig_dir) if orig_dir else base
    if not _orig_dir.is_absolute():
        _orig_abs = base / _orig_dir
    else:
        _orig_abs = _orig_dir
    manifest = expand_directory_entries(manifest, str(_orig_abs))
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

    quiet = output_level == "quiet"
    total = len(manifest["sources"])
    parsed_meta = {}
    errors = []

    if not quiet:
        print("  Phase 1: Parse")

    for src_idx, source in enumerate(manifest["sources"], 1):
        try:
            resolved = resolve_source_fields(source)
        except ValueError as e:
            errors.append({
                "file": source.get("orig", source.get("url", "?")),
                "status": "error", "message": str(e),
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
                errors.append({
                    "file": resolved["path"], "status": "missing",
                    "message": f"Original file not found: {orig_name}",
                })
                parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "missing"}
                continue
            elif resolved.get("url"):
                if not allow_download:
                    errors.append({
                        "file": resolved["path"], "status": "error",
                        "message": f"URL source requires --allow-download: {resolved['url']}",
                    })
                    parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "error"}
                    continue
                fetched = _fetch_url(resolved["url"], _orig_dir / orig_name)
                if not fetched["ok"]:
                    errors.append({
                        "file": resolved["path"], "status": "error",
                        "message": f"Fetch failed: {fetched['error']}",
                    })
                    parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "error"}
                    continue

        src_path = _orig_dir / orig_name
        if not src_path.exists():
            errors.append({
                "file": resolved["path"], "status": "missing",
                "message": f"Original file not found: {orig_name}",
            })
            parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "missing"}
            continue

        # Save Docling JSON for docling-parsed files (for later captioning)
        from lore_mcp.preprocess.parse import detect_format
        backend = detect_format(src_path.name)
        docling_json = ""
        if backend == "docling":
            docling_json = str(_prep_dir / f"{target_path.stem}.docling.json")

        try:
            if not quiet:
                print(" → parse", end="", flush=True)
            source_lang = resolved.get("lang", "")
            effective_ocr_lang = [source_lang] if source_lang else (ocr_lang or [])
            text = parse_to_markdown(
                str(src_path), docling_json_path=docling_json,
                ocr_engine=ocr_engine, ocr_lang=effective_ocr_lang,
            )
        except (FormatNotSupported, ImportError, Exception) as e:
            errors.append({
                "file": resolved["path"], "status": "error",
                "message": str(e),
            })
            parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "error"}
            continue

        _write_phase(_prep_dir, target_path, "phase1-parse", text)

        if not quiet:
            print(" → ok")

        meta = {
            "resolved": resolved,
            "status": "ok",
            "src_path": str(src_path),
            "target_path": str(target_path),
            "text_file": str(_phase_path(_prep_dir, target_path, "phase1-parse")),
        }
        if docling_json and Path(docling_json).exists():
            meta["docling_json"] = docling_json
        parsed_meta[resolved["path"]] = meta

    report = {"parsed": parsed_meta, "errors": errors}
    Path(report_path).write_text(
        _json.dumps(report, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _resolve_from_config(config) -> dict:
    """Resolve preprocess params from a LoreConfig object."""
    params = {}
    params["enrich"] = config.enrich_techniques or None
    params["ocr_engine"] = config.ocr_engine
    params["ocr_lang"] = config.ocr_lang or None
    params["caption_selection"] = config.caption_selection
    params["video_scene_threshold"] = getattr(config, "video_scene_threshold", 0.3)

    # STT entry for audio/video
    stt_name = getattr(config, "stt_model", "")
    if stt_name:
        try:
            params["stt_entry"] = config.get_llm(stt_name)
        except KeyError:
            params["stt_entry"] = None
    else:
        params["stt_entry"] = None

    # LLM entry for enrichment
    llm_name = config.enrich_models[0] if config.enrich_models else None
    if llm_name:
        try:
            params["llm_entry"] = config.get_llm(llm_name)
        except KeyError:
            params["llm_entry"] = None
    else:
        params["llm_entry"] = None

    # Caption primary
    if config.caption_primary:
        try:
            params["caption_primary"] = config.get_llm(config.caption_primary)
        except KeyError:
            pass

    # Caption additional
    additional_names = config.caption_additional or config.caption_models or []
    additional = []
    for name in additional_names:
        try:
            additional.append(config.get_llm(name))
        except KeyError:
            pass
    if additional:
        params["caption_additional"] = additional

    # Judge
    if config.caption_judge:
        try:
            params["judge_entry"] = config.get_llm(config.caption_judge)
        except KeyError:
            pass

    return params


def preprocess_sources(
    manifest_path: str,
    docs_base_dir: str,
    config,
) -> list[dict]:
    """Preprocess sources listed in a manifest. Returns reports.

    All parameters are resolved from the LoreConfig object.
    See docs/studies/design-preprocess-pipeline.md.
    """
    from lore_mcp.checkpoint import Checkpoint
    config_path = getattr(config, "_config_path", "")
    checkpoint = Checkpoint(manifest_path, config_path, force=config.force)
    logger.debug("Pipeline state: %s", checkpoint.state_dir)

    resolved = _resolve_from_config(config)
    orig_dir = config.preprocess_orig_dir
    prep_dir = config.preprocess_prep_dir
    manifest_out = config.preprocess_manifest_out or None
    force = config.force
    output_level = config.output_level
    keep_intermediates = bool(config.intermediates_dir)
    ocr_engine = config.ocr_engine or resolved.get("ocr_engine", "")
    ocr_lang = config.ocr_lang or resolved.get("ocr_lang")
    enrich = resolved.get("enrich")
    llm_entry = resolved.get("llm_entry")
    caption_primary = resolved.get("caption_primary")
    caption_additional = resolved.get("caption_additional")
    judge_entry = resolved.get("judge_entry")
    caption_selection = resolved.get("caption_selection", "first_nonempty")
    stt_entry = resolved.get("stt_entry")
    video_scene_threshold = resolved.get("video_scene_threshold", 0.3)

    # Build unified caption model list
    caption_models = []
    if caption_primary:
        caption_models.append(caption_primary)
    if caption_additional:
        caption_models.extend(e for e in caption_additional if e)

    manifest = parse_manifest(manifest_path)
    base = Path(docs_base_dir)

    _orig_dir = Path(orig_dir) if orig_dir else base
    if not _orig_dir.is_absolute():
        _orig_dir = base / _orig_dir

    # Output layout: prep_base_dir/  (report, manifest)
    #                prep_base_dir/<collection>/  (final .md files)
    #                intermediates_dir/  (phase files, stt cache)
    _prep_base_dir = Path(prep_dir) if prep_dir else base
    if not _prep_base_dir.is_absolute():
        _prep_base_dir = base / _prep_base_dir
    _prep_base_dir.mkdir(parents=True, exist_ok=True)

    collection_name = base.name
    _final_dir = _prep_base_dir / collection_name
    _final_dir.mkdir(parents=True, exist_ok=True)

    _inter_dir = Path(config.intermediates_dir) if config.intermediates_dir else checkpoint.state_dir
    _inter_dir.mkdir(parents=True, exist_ok=True)

    # _prep_dir alias for phase writes (intermediates)
    _prep_dir = _inter_dir

    urls_file = base / "urls.txt"
    if urls_file.exists():
        url_sources = _load_urls_file(urls_file)
        manifest["sources"].extend(url_sources)
        logger.info("Loaded %d URLs from %s", len(url_sources), urls_file)

    reports = []
    quiet = output_level == "quiet"
    total = len(manifest["sources"])

    # ── Phase announcement ─────────────────────────────────────
    phase_list = _describe_phases(caption_models, llm_entry, enrich)
    phase_meta = {
        "phases": [p.split(" (")[0] for p in phase_list],
        "caption_models": [e.get("name", "") for e in caption_models],
        "llm": (llm_entry or {}).get("model", ""),
        "enrich_techniques": enrich or [],
    }
    if not quiet:
        print(f"  Active phases: {', '.join(phase_list)}")

    import subprocess as _sp
    import sys
    from lore_mcp.preprocess.service import _log_vram
    logger.debug("VRAM at lore-mcp launch (before subprocess):")
    _log_vram()
    try:
        cuda_result = _sp.run(
            [sys.executable, "-c",
             "import torch, json; "
             "d = {'cuda': torch.cuda.is_available()}; "
             "d['device'] = torch.cuda.get_device_name(0) if d['cuda'] else ''; "
             "d['vram_mb'] = torch.cuda.get_device_properties(0).total_memory // 1048576 if d['cuda'] else 0; "
             "print(json.dumps(d))"],
            capture_output=True, text=True, timeout=10,
        )
        import json as _json_cuda
        cuda_info = _json_cuda.loads(cuda_result.stdout)
        logger.debug("CUDA: %s", cuda_info)
    except Exception:
        pass
    logger.debug("VRAM after CUDA check:")
    _log_vram()

    # ── Phase 1: Parse in subprocess (no captioning) ──────────
    import json as _json
    import multiprocessing
    from lore_mcp.checkpoint import phase_hash as _phase_hash

    p1_hash = _phase_hash(manifest_path, config, "phase1")
    report_path = _prep_dir / "phase1-report.json"
    if checkpoint.is_phase_done("phase1", expected_hash=p1_hash) and report_path.exists():
        logger.info("Phase 1 skipped (checkpoint, hash=%s)", p1_hash[:8])
    else:
        if checkpoint.is_phase_done("phase1"):
            logger.info("Phase 1 config changed (hash mismatch), re-running")
            checkpoint.invalidate_phase("stt")
            checkpoint.invalidate_phase("frame_caption")
        p = multiprocessing.Process(
            target=_phase1_worker,
            args=(manifest_path, docs_base_dir, orig_dir, str(_inter_dir),
                  str(report_path), output_level, ocr_engine, ocr_lang,
                  config.allow_download),
        )
        p.start()
        p.join()
        checkpoint.mark_phase_done("phase1", hash_value=p1_hash)

    logger.debug("VRAM after subprocess exit (before caption):")
    _log_vram()

    parsed = {}
    phase1_count = 0
    if report_path.exists():
        phase1_report = _json.loads(report_path.read_text(encoding="utf-8"))
        for err in phase1_report.get("errors", []):
            reports.append({
                "file": err["file"], "status": err["status"],
                "message": err.get("message", ""),
                "input_len": 0, "output_len": 0,
            })
        for path_key, meta in phase1_report.get("parsed", {}).items():
            resolved = meta["resolved"]
            if meta["status"] != "ok":
                parsed[path_key] = {"resolved": resolved, "text": None}
                continue
            text_file = Path(meta["text_file"])
            text = text_file.read_text(encoding="utf-8") if text_file.exists() else None
            parsed[path_key] = {
                "resolved": resolved,
                "text": text,
                "src_path": Path(meta["src_path"]),
                "target_path": Path(meta["target_path"]),
                "docling_json": meta.get("docling_json", ""),
            }
            if text is not None:
                phase1_count += 1
    elif p.exitcode != 0:
        logger.error("Phase 1 subprocess failed with exit code %d", p.exitcode)

    # ── Phase 1.5: Standalone image fallback (E12.45) ──────────
    # Docling produces empty output on standalone photos. Detect and
    # mark for direct VLM captioning instead of Docling caption path.
    standalone_images = set()
    for path_key, data in parsed.items():
        docling_json = data.get("docling_json", "")
        if not docling_json or not Path(docling_json).exists():
            continue
        src_path = data.get("src_path")
        if not src_path or src_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        text = data.get("text", "") or ""
        if len(text.strip()) < 10:
            standalone_images.add(path_key)
            logger.info("Standalone image detected (empty Docling output): %s",
                        data["resolved"]["orig"])

    # ── Phase 1.6: Audio/Video transcription (E12.48/49) ───────
    if stt_entry:
        stt_url = stt_entry.get("api_url", "")
        stt_model_name = stt_entry.get("model", "")
        stt_timeout = stt_entry.get("timeout", 600)
        if stt_url:
            needs_stt = False
            for path_key, data in parsed.items():
                src_path = data.get("src_path")
                if not src_path:
                    continue
                fmt = detect_format(src_path.name)
                if fmt not in ("audio", "video"):
                    continue
                orig_name = data["resolved"]["orig"]
                if checkpoint.is_completed("stt", orig_name):
                    continue
                stt_cache = _prep_dir / f"{Path(orig_name).stem}.stt.json"
                if fmt == "video" and stt_cache.exists():
                    continue
                needs_stt = True
                break
            if needs_stt:
                start_service(stt_entry)
            else:
                logger.info("STT skipped (all sources cached or completed)")
            try:
                for path_key, data in parsed.items():
                    src_path = data.get("src_path")
                    if not src_path:
                        continue
                    fmt = detect_format(src_path.name)
                    orig_name = data["resolved"]["orig"]
                    if checkpoint.is_completed("stt", orig_name):
                        logger.debug("Skip (checkpoint): %s", orig_name)
                        continue
                    if fmt == "audio":
                        if not quiet:
                            print(f"    {orig_name} → transcribe", flush=True)
                        try:
                            lang = data["resolved"].get("lang", "")
                            from lore_mcp.preprocess.parse import _get_audio_duration
                            audio_dur = _get_audio_duration(str(src_path))
                            effective_timeout = max(stt_timeout, int(audio_dur * 2)) if audio_dur else stt_timeout
                            stt_result = transcribe_audio(
                                str(src_path), stt_url, stt_model_name,
                                language=lang, timeout=effective_timeout,
                            )
                            data["text"] = stt_result["text"]
                            if stt_result.get("language") and not data["resolved"].get("lang"):
                                data["resolved"]["lang"] = stt_result["language"]
                            _write_phase(_prep_dir, data["target_path"],
                                         "phase1-parse", stt_result["text"])
                            checkpoint.mark_completed("stt", orig_name)
                        except Exception as e:
                            logger.warning("Transcription failed for %s: %s",
                                           data["resolved"]["orig"], e)
                    elif fmt == "video":
                        if not quiet:
                            print(f"    {data['resolved']['orig']} → transcribe+frames", flush=True)
                        try:
                            lang = data["resolved"].get("lang", "")
                            source_strategy = data["resolved"].get(
                                "video_frame_strategy",
                                getattr(config, "video_frame_strategy", "scene"),
                            )
                            vid_result = parse_video(
                                str(src_path), stt_url, stt_model_name,
                                language=lang,
                                scene_threshold=video_scene_threshold,
                                timeout=stt_timeout,
                                frame_strategy=source_strategy,
                                frame_interval=getattr(config, "video_frame_interval", 30),
                                ocr_change_threshold=getattr(config, "video_ocr_change_threshold", 0.3),
                                cache_dir=str(_prep_dir),
                            )
                            data["text"] = vid_result["text"]
                            if vid_result.get("language") and not data["resolved"].get("lang"):
                                data["resolved"]["lang"] = vid_result["language"]
                            _write_phase(_prep_dir, data["target_path"],
                                         "phase1-parse", vid_result["text"])
                            checkpoint.mark_completed("stt", orig_name)
                        except Exception as e:
                            logger.warning("Video parsing failed for %s: %s",
                                           data["resolved"]["orig"], e)
            finally:
                if needs_stt:
                    capture_service_logs(stt_entry, str(_prep_dir))
                    stop_service(stt_entry)

    # ── Phase 1.7: Caption video frames with transcript context (E12.52)
    if caption_models:
        cap_entry = caption_models[0]
        cap_url = cap_entry.get("api_url", "")
        cap_model_name = cap_entry.get("model", "")
        if cap_url:
            video_sources = [
                (pk, d) for pk, d in parsed.items()
                if d.get("text") and d.get("src_path")
                and "base64" in (d.get("text") or "")
            ]
            if video_sources:
                if not quiet:
                    print(f"  Phase 1.7: Caption video frames ({cap_entry.get('name', '')})")
                start_service(cap_entry)
                try:
                    for path_key, data in video_sources:
                        if checkpoint.is_completed("frame_caption", path_key):
                            continue
                        if not quiet:
                            print(f"    {data['resolved']['orig']} → caption frames", flush=True)
                        cap_timeout = cap_entry.get("timeout", 600)
                        captioned = caption_inline_frames(
                            data["text"], cap_url, cap_model_name,
                            timeout=cap_timeout,
                        )
                        data["text"] = captioned
                        _write_phase(_prep_dir, data["target_path"],
                                     "phase1-parse", captioned)
                        checkpoint.mark_completed("frame_caption", path_key)
                finally:
                    capture_service_logs(cap_entry, str(_prep_dir))
                    stop_service(cap_entry)

    # ── Phase 2: Caption via Docling native (all models) ──────
    # Each model: load Docling JSON → PictureDescriptionApiModel → markdown
    has_docling_docs = any(
        d.get("docling_json") and Path(d["docling_json"]).exists()
        for d in parsed.values()
    )

    caption_stats = {"captioned": 0, "skipped": 0, "failed": 0}
    model_results = {}  # path_key -> {model_name: caption_text}

    if has_docling_docs and caption_models:
        for model_idx, cap_entry in enumerate(caption_models):
            model_name = cap_entry.get("name", f"model{model_idx}")
            cap_url = cap_entry.get("api_url", "")
            cap_model = cap_entry.get("model", "")

            if not cap_url:
                continue

            if not quiet:
                print(f"  Phase 2.{model_idx + 1}: Caption ({model_name})")

            start_service(cap_entry)
            try:
                for path_key, data in parsed.items():
                    docling_json = data.get("docling_json", "")
                    if not docling_json or not Path(docling_json).exists():
                        continue

                    caption_phase = f"caption_{model_name}"
                    if checkpoint.is_completed(caption_phase, path_key):
                        logger.debug("Skip caption (checkpoint): %s", path_key)
                        continue

                    target_path = data["target_path"]

                    if not quiet:
                        print(f"    {data['resolved']['orig']} → caption", flush=True)

                    try:
                        cap_timeout = cap_entry.get("timeout", 180)
                        if path_key in standalone_images:
                            caption_text = caption_standalone_image(
                                str(data["src_path"]), cap_url, cap_model,
                                timeout=cap_timeout,
                            )
                        else:
                            caption_text = caption_with_docling(
                                docling_json, cap_url, cap_model,
                                timeout=cap_timeout,
                                checkpoint=checkpoint,
                                phase_name=caption_phase,
                                source_key=path_key,
                            )
                        if caption_text:
                            if path_key not in model_results:
                                model_results[path_key] = {}
                            model_results[path_key][model_name] = caption_text
                            _write_phase(_prep_dir, target_path,
                                         f"caption-{model_name}", caption_text)
                            caption_stats["captioned"] += 1
                            checkpoint.mark_completed(caption_phase, path_key)
                    except Exception as e:
                        caption_stats["failed"] += 1
                        logger.warning("Caption failed (%s) for %s: %s",
                                       model_name, data["resolved"]["orig"], e)
            finally:
                capture_service_logs(cap_entry, str(_prep_dir))
                stop_service(cap_entry)

        # Select/fuse captions from models
        if model_results:
            caption_selection_used = caption_selection
            if not quiet and len(caption_models) > 1:
                print(f"  Phase 2 selection: {caption_selection}")
            for path_key, captions_by_model in model_results.items():
                data = parsed[path_key]
                if not captions_by_model:
                    continue

                # Include phase 1 text (no caption) as candidate "phase1"
                phase1_text = data.get("text", "")
                if phase1_text:
                    captions_by_model["phase1"] = phase1_text

                selected = None

                if len(captions_by_model) == 1 or caption_selection == "first_nonempty":
                    selected = next((v for v in captions_by_model.values() if v), None)
                elif caption_selection == "longest":
                    selected = max(captions_by_model.values(), key=len)
                elif caption_selection == "judge" and judge_entry:
                    alt_text = data["resolved"].get("description", "")
                    judge_url = judge_entry.get("api_url", "")
                    judge_model_name = judge_entry.get("model", "")
                    judge_key = judge_entry.get("api_key", "")
                    try:
                        if not quiet:
                            print(f"    {data['resolved']['orig']} → judge", flush=True)
                        start_service(judge_entry)
                        selected = judge_captions(
                            "", alt_text, captions_by_model,
                            judge_url, judge_model_name, judge_key,
                        )
                        capture_service_logs(judge_entry, str(_prep_dir))
                        stop_service(judge_entry)
                    except Exception as e:
                        logger.warning("Judge failed for %s: %s", path_key, e)
                        selected = next((v for v in captions_by_model.values() if v), None)
                else:
                    selected = next((v for v in captions_by_model.values() if v), None)

                if selected:
                    data["text"] = selected
    elif not quiet and caption_models:
        print("  Phase 2: Caption (skipped — no Docling documents)")

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
            if checkpoint.is_completed("phase3", path_key):
                continue

            resolved = data["resolved"]
            target_path = data["target_path"]
            text = data["text"]
            input_len = len(text)

            if not quiet:
                print(f"    {resolved['orig']} → clean", end="", flush=True)
            cleaned = clean_text(text)

            source_lang = resolved.get("lang", "")

            if enrich and "context" in enrich:
                if not quiet:
                    print(" → enrich:context", end="", flush=True)
                cleaned = enrich_context(cleaned, llm_url, llm_model_name, llm_key, lang=source_lang)
            if enrich and "qa" in enrich:
                if not quiet:
                    print(" → enrich:qa", end="", flush=True)
                cleaned = enrich_qa(cleaned, llm_url, llm_model_name, llm_key, lang=source_lang)
            if enrich and "meta" in enrich:
                if not quiet:
                    print(" → enrich:meta", end="", flush=True)
                cleaned = enrich_meta(cleaned, llm_url, llm_model_name, llm_key, lang=source_lang)

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
            checkpoint.mark_completed("phase3", path_key)
    finally:
        if enrich and llm_entry:
            capture_service_logs(llm_entry, str(_prep_dir))
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

        file_out = _final_dir / target_path.parent
        file_out.mkdir(parents=True, exist_ok=True)
        out_name = target_path.name + ".md" if target_path.suffix.lower() != ".md" else target_path.name
        out_file = file_out / out_name
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
            _write_report(_prep_base_dir, reports)
            enriched_sources.append(resolved)
            continue

        if not keep_intermediates:
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
        _write_report(_prep_base_dir, reports)

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
        if has_docling_docs and caption_models:
            n_models = len(caption_models)
            summary_parts.append(
                f"caption ({n_models} model{'s' if n_models > 1 else ''}, "
                f"{caption_stats['captioned']} ok, "
                f"{caption_stats['failed']} failed)"
            )
        summary_parts.append(f"clean+{phase3_label} ({len(content_map)}/{total})")
        summary_parts.append(f"write ({write_count}/{total})")
        print(f"  Phases completed: {', '.join(summary_parts)}")

    # Final report with phase metadata
    _write_report(_prep_base_dir, reports, phase_meta)
    if not quiet:
        report_path_out = _prep_base_dir / "preprocess-report.json"
        print(f"\n{len([r for r in reports if r['status'] == 'ok'])} files preprocessed → {_final_dir}")
        print(f"  Report: {report_path_out}")

    return reports
