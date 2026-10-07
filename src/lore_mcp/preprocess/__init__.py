"""Preprocessing pipeline for RAG-ready markdown. See docs/preprocessing.md."""

import logging
from pathlib import Path

import yaml

from lore_mcp.recipe import (
    expand_directory_entries,
    extract_source_metadata,
    parse_recipe,
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
    detect_format,
    judge_captions,
    parse_to_markdown,
    parse_video,
    transcribe_audio,
)
from lore_mcp.preprocess.enrich import enrich_context, enrich_meta, enrich_qa, enrich_stt_fix, enrich_speaker_id
from lore_mcp.preprocess.pii import detect_pii
from lore_mcp.preprocess.service import start_service, stop_service
from lore_mcp.preprocess.validate import quality_gate

logger = logging.getLogger(__name__)

__all__ = ["clean_text", "preprocess_file", "preprocess_sources"]


def _load_urls_file(path: Path) -> list[dict]:
    """Read urls.txt and return recipe source entries."""
    sources = []
    for line in path.read_text(encoding="utf-8").splitlines():
        url = line.strip()
        if url and not url.startswith("#"):
            sources.append({"url": url})
    return sources


def _extract_stt_segments(markdown_text: str) -> list[dict]:
    """Parse STT markdown back into segments with timestamps and text."""
    import re
    segments = []
    current_start = 0.0
    for line in markdown_text.split("\n"):
        ts_match = re.match(r"^##\s*\[(\d+):(\d+):(\d+)\]", line)
        if ts_match:
            h, m, s = int(ts_match.group(1)), int(ts_match.group(2)), int(ts_match.group(3))
            current_start = h * 3600 + m * 60 + s
        elif line.strip() and not line.startswith("#"):
            segments.append({
                "text": line.strip(),
                "start": current_start,
                "end": current_start + 10.0,
            })
    return segments


_VIDEO_PLATFORM_PATTERNS = (
    "youtube.com/watch",
    "youtu.be/",
    "vimeo.com/",
    "dailymotion.com/video",
    "linkedin.com/learning/",
    "peertube.",
)


def _is_video_platform_url(url: str) -> bool:
    """Detect video platform URLs that should be handled by yt-dlp."""
    lower = url.lower()
    return any(p in lower for p in _VIDEO_PLATFORM_PATTERNS)


def _video_filename_from_url(url: str) -> str:
    """Extract a unique filename from a video platform URL using video ID."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/")
        else:
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        if video_id:
            return f"{video_id}.mp4"
    path = parsed.path.rstrip("/")
    last_segment = path.split("/")[-1] if path else "video"
    return f"{last_segment}.mp4"


def _fetch_url(url: str, dest: Path) -> dict:
    """Download a URL to a local file. Adds extension from content-type if missing."""
    import mimetypes
    import urllib.request
    import urllib.error

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lore-mcp/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
            from lore_mcp.preprocess.parse import detect_format, FormatNotSupported
            needs_ext = not dest.suffix
            if not needs_ext:
                try:
                    detect_format(dest.name)
                except (FormatNotSupported, Exception):
                    needs_ext = True
            if needs_ext and content_type:
                ext = mimetypes.guess_extension(content_type) or ""
                if ext == ".htm":
                    ext = ".html"
                if ext:
                    dest = dest.parent / (dest.name + ext)
            dest.write_bytes(data)
        return {"ok": True, "path": str(dest)}
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


def _phase1_worker(recipe_path, orig_dir, work_dir,
                   report_path, output_level, ocr_engine="", ocr_lang=None,
                   allow_download=False):
    """Parse all sources in a subprocess. Writes phase1 files + report JSON.

    Pure parse — no captioning. Saves Docling document as JSON
    for later captioning (parse-once, caption-N).
    """
    import json as _json

    recipe = parse_recipe(recipe_path)
    recipe_orig_dir = recipe.get("orig_dir", "")
    _orig_dir = Path(orig_dir).resolve() if orig_dir else Path.cwd()
    if recipe_orig_dir and not orig_dir:
        _orig_dir = Path(recipe_orig_dir)
        if not _orig_dir.is_absolute():
            _orig_dir = Path.cwd() / _orig_dir
    recipe = expand_directory_entries(recipe, str(_orig_dir))
    _prep_dir = Path(work_dir) if work_dir else _orig_dir
    _prep_dir.mkdir(parents=True, exist_ok=True)

    _downloads_dir = _prep_dir / "downloads"

    urls_file = _orig_dir / "urls.txt"
    if urls_file.exists():
        url_sources = _load_urls_file(urls_file)
        recipe["sources"].extend(url_sources)

    quiet = output_level == "quiet"
    total = len(recipe["sources"])
    parsed_meta = {}
    errors = []
    docling_batch = []

    if not quiet:
        print("  Phase 1: Parse")

    for src_idx, source in enumerate(recipe["sources"], 1):
        try:
            resolved = resolve_source_fields(source)
        except ValueError as e:
            errors.append({
                "file": source.get("file", source.get("url", "?")),
                "status": "error", "message": str(e),
            })
            continue

        orig_name = resolved["file"]
        target_path = Path(resolved["path"])
        orig_was_explicit = "file" in source

        if not quiet:
            print(f"    [{src_idx}/{total}] {orig_name}", end="", flush=True)

        if not (_orig_dir / orig_name).exists():
            for candidate in sorted(_orig_dir.glob(f"{orig_name}.*")):
                orig_name = candidate.name
                resolved["file"] = orig_name
                break
            else:
                for candidate in sorted(_downloads_dir.glob(f"{orig_name}.*")) if _downloads_dir.exists() else []:
                    orig_name = candidate.name
                    resolved["file"] = orig_name
                    break

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
                source_url = resolved["url"]
                if _is_video_platform_url(source_url):
                    video_name = _video_filename_from_url(source_url)
                    video_dest = _orig_dir / video_name
                    dl_dest = _downloads_dir / video_name
                    if not video_dest.exists() and not dl_dest.exists():
                        try:
                            _downloads_dir.mkdir(parents=True, exist_ok=True)
                            from lore_mcp.preprocess.parse import download_video
                            dl = download_video(source_url, str(_downloads_dir),
                                                lang=resolved.get("lang", ""))
                            if dl.get("error"):
                                raise RuntimeError(dl["error"])
                            if dl.get("video_path"):
                                orig_name = Path(dl["video_path"]).name
                            elif dl.get("captions_text"):
                                md_name = video_name.rsplit(".", 1)[0] + ".md"
                                md_path = _downloads_dir / md_name
                                md_path.write_text(dl["captions_text"], encoding="utf-8")
                                orig_name = md_name
                            else:
                                raise RuntimeError("No video or captions downloaded")
                            resolved["file"] = orig_name
                            stem = Path(orig_name).stem
                            resolved["path"] = f"{stem}.md"
                            if dl.get("title"):
                                resolved.setdefault("title", dl["title"])
                        except Exception as e:
                            errors.append({
                                "file": resolved["path"], "status": "error",
                                "message": f"Video download failed: {e}",
                            })
                            parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "error"}
                            continue
                    else:
                        orig_name = video_name
                        resolved["file"] = orig_name
                else:
                    _downloads_dir.mkdir(parents=True, exist_ok=True)
                    fetched = _fetch_url(source_url, _downloads_dir / orig_name)
                    if not fetched["ok"]:
                        errors.append({
                            "file": resolved["path"], "status": "error",
                            "message": f"Fetch failed: {fetched['error']}",
                        })
                        parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "error"}
                        continue
                    if fetched.get("path"):
                        orig_name = Path(fetched["path"]).name
                        resolved["file"] = orig_name

        target_path = Path(resolved["path"])
        src_path = _orig_dir / orig_name
        if not src_path.exists() and (_downloads_dir / orig_name).exists():
            src_path = _downloads_dir / orig_name
        if not src_path.exists():
            errors.append({
                "file": resolved["path"], "status": "missing",
                "message": f"Original file not found: {orig_name}",
            })
            parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "missing"}
            continue

        from lore_mcp.preprocess.parse import detect_format
        try:
            backend = detect_format(str(src_path))
        except (FormatNotSupported, Exception) as e:
            errors.append({
                "file": resolved["path"], "status": "error",
                "message": str(e),
            })
            parsed_meta[resolved["path"]] = {"resolved": resolved, "status": "error"}
            if not quiet:
                print(f" → {e}")
            continue
        docling_json = ""
        if backend == "docling":
            docling_json = str(_prep_dir / f"{target_path.stem}.docling.json")

        if backend == "docling":
            docling_batch.append({
                "src_path": str(src_path),
                "target_path": target_path,
                "resolved": resolved,
                "docling_json": docling_json,
            })
            if not quiet:
                print("", flush=True)
            continue

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

        if backend in ("markitdown", "json", "code"):
            from lore_mcp.preprocess.narrate import narrate_structured
            text = narrate_structured(text, backend, filename=src_path.name)

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

    # Batch-process Docling sources (E12.87)
    if docling_batch:
        from lore_mcp.preprocess.parse import parse_batch_docling
        batch_paths = [d["src_path"] for d in docling_batch]
        batch_jsons = [d["docling_json"] for d in docling_batch]
        if not quiet:
            print(f"    Docling batch: {len(docling_batch)} sources")
        try:
            batch_results = parse_batch_docling(
                batch_paths, batch_jsons, ocr_engine, ocr_lang,
            )
        except Exception as e:
            batch_results = {}
            for d in docling_batch:
                errors.append({
                    "file": d["resolved"]["path"], "status": "error",
                    "message": str(e),
                })
                parsed_meta[d["resolved"]["path"]] = {"resolved": d["resolved"], "status": "error"}

        for d in docling_batch:
            src_str = d["src_path"]
            result = batch_results.get(src_str)
            if not result or result.get("text") is None:
                err_msg = result.get("error", "batch conversion produced no output") if result else "not in batch results"
                errors.append({
                    "file": d["resolved"]["path"], "status": "error",
                    "message": err_msg,
                })
                parsed_meta[d["resolved"]["path"]] = {"resolved": d["resolved"], "status": "error"}
                continue

            batch_text = result["text"]
            src_ext = Path(d["src_path"]).suffix.lower()
            if src_ext in (".xlsx", ".csv", ".json"):
                from lore_mcp.preprocess.narrate import narrate_structured
                batch_text = narrate_structured(batch_text, "docling")
            _write_phase(_prep_dir, d["target_path"], "phase1-parse", batch_text)
            if not quiet:
                print(f"    {d['resolved']['file']} → ok")

            meta = {
                "resolved": d["resolved"],
                "status": "ok",
                "src_path": src_str,
                "target_path": str(d["target_path"]),
                "text_file": str(_phase_path(_prep_dir, d["target_path"], "phase1-parse")),
            }
            dj = result.get("docling_json", "")
            if dj and Path(dj).exists():
                meta["docling_json"] = dj
            parsed_meta[d["resolved"]["path"]] = meta

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

    # Diarization entry
    diarize_name = getattr(config, "diarization_model", "")
    if diarize_name:
        try:
            params["diarize_entry"] = config.get_llm(diarize_name)
        except KeyError:
            params["diarize_entry"] = None
    else:
        params["diarize_entry"] = None
    params["diarization_device"] = getattr(config, "diarization_device", "auto")

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
    recipe_path: str,
    docs_base_dir: str,
    config,
) -> list[dict]:
    """Preprocess sources listed in a recipe. Returns reports.

    All parameters are resolved from the LoreConfig object.
    docs_base_dir is kept for backward compat but config.orig_dir
    takes precedence when set.
    """
    from lore_mcp.checkpoint import Checkpoint
    from lore_mcp.task_manager import check_cancelled

    _build_dir = config.build_dir
    _orig_dir_cfg = config.orig_dir

    if not _build_dir:
        _build_dir = str(Path(docs_base_dir).resolve())
        config.build_dir = _build_dir

    config_path = getattr(config, "_config_path", "")
    work_dir = str(Path(_build_dir) / ".work")
    checkpoint = Checkpoint(recipe_path, config_path, force=config.force,
                            state_dir=work_dir)
    logger.debug("Pipeline state: %s", checkpoint.state_dir)

    resolved = _resolve_from_config(config)
    recipe_out = config.preprocess_recipe_out or None
    force = config.force
    skip_poor = getattr(config, "skip_poor", False)
    output_level = config.output_level
    keep_intermediates = config.keep_intermediates
    ocr_engine = config.ocr_engine or resolved.get("ocr_engine", "")
    ocr_lang = config.ocr_lang or resolved.get("ocr_lang")
    enrich = resolved.get("enrich")
    llm_entry = resolved.get("llm_entry")
    caption_primary = resolved.get("caption_primary")
    caption_additional = resolved.get("caption_additional")
    judge_entry = resolved.get("judge_entry")
    caption_selection = resolved.get("caption_selection", "first_nonempty")
    stt_entry = resolved.get("stt_entry")
    diarize_entry = resolved.get("diarize_entry")
    diarization_device = resolved.get("diarization_device", "auto")
    video_scene_threshold = resolved.get("video_scene_threshold", 0.3)

    # Build unified caption model list
    caption_models = []
    if caption_primary:
        caption_models.append(caption_primary)
    if caption_additional:
        caption_models.extend(e for e in caption_additional if e)

    recipe = parse_recipe(recipe_path)
    recipe_orig_dir = recipe.get("orig_dir", "")
    if not _orig_dir_cfg and recipe_orig_dir:
        _orig_dir_cfg = recipe_orig_dir

    if _orig_dir_cfg:
        _orig_dir = Path(_orig_dir_cfg).resolve()
    elif docs_base_dir:
        _orig_dir = Path(docs_base_dir).resolve()
    else:
        _orig_dir = Path.cwd()

    _bd = Path(_build_dir).resolve()
    _bd.mkdir(parents=True, exist_ok=True)
    _prep_base_dir = _bd

    _final_dir = _bd / "prep"
    _final_dir.mkdir(parents=True, exist_ok=True)

    _inter_dir = _bd / ".work"
    _inter_dir.mkdir(parents=True, exist_ok=True)

    # _prep_dir alias for phase writes (intermediates)
    _prep_dir = _inter_dir

    urls_file = _orig_dir / "urls.txt"
    if urls_file.exists():
        url_sources = _load_urls_file(urls_file)
        recipe["sources"].extend(url_sources)
        logger.info("Loaded %d URLs from %s", len(url_sources), urls_file)

    reports = []
    quiet = output_level == "quiet"
    total = len(recipe["sources"])

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

    check_cancelled()
    # ── Phase 1: Parse in subprocess (no captioning) ──────────
    import json as _json
    import multiprocessing
    from lore_mcp.checkpoint import phase_hash as _phase_hash

    p1_hash = _phase_hash(recipe_path, config, "phase1")
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
            args=(recipe_path, str(_orig_dir), str(_inter_dir),
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

    # Skip global STT when diarization configured (E12.141) — per-speaker STT in phase 1.5
    skip_global_stt = bool(diarize_entry and diarize_entry.get("model"))

    # ── Phase 1 validation: detect STT placeholders (E12.129) ──
    _STT_PLACEHOLDERS = ("requires STT service", "requires STT service + ffmpeg")
    for path_key, data in parsed.items():
        text = data.get("text") or ""
        if any(ph in text for ph in _STT_PLACEHOLDERS):
            resolved = data["resolved"]
            if skip_global_stt:
                # Expected: per-speaker STT in phase 1.5 will handle this
                data["text"] = None
            else:
                logger.warning("STT placeholder detected: %s", resolved["file"])
                reports.append({
                    "file": resolved.get("path", path_key),
                    "status": "error",
                    "message": "STT service unavailable — audio/video not transcribed",
                    "input_len": 0, "output_len": 0,
                })
                data["text"] = None

    # ── Phase 1 validation: check referenced files exist (E12.80) ──
    missing_intermediates = []
    for path_key, data in parsed.items():
        dj = data.get("docling_json", "")
        if dj and not Path(dj).exists():
            missing_intermediates.append(path_key)
        tf = data.get("text") is None and data.get("resolved", {}).get("status") != "error"
        if tf:
            text_file = str(_prep_dir / f"{Path(data.get('target_path', '')).stem}.phase1-parse.md")
            if not Path(text_file).exists():
                missing_intermediates.append(path_key)
    if missing_intermediates:
        logger.warning(
            "Phase 1 intermediates missing for %d sources: %s — re-run with --force",
            len(missing_intermediates),
            ", ".join(missing_intermediates[:5]),
        )

    check_cancelled()
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
                        data["resolved"]["file"])

    check_cancelled()
    # ── Phase 1.6: Audio/Video transcription (E12.48/49) ───────
    if stt_entry and not skip_global_stt:
        stt_url = stt_entry.get("api_url", "")
        stt_model_name = stt_entry.get("model", "")
        stt_timeout = stt_entry.get("timeout", 600)
        if stt_url:
            needs_stt = False
            _sub_exts = (".vtt", ".srt", ".en.vtt", ".fr.vtt",
                         ".en.srt", ".fr.srt")
            for path_key, data in parsed.items():
                src_path = data.get("src_path")
                if not src_path:
                    continue
                fmt = detect_format(src_path.name)
                if fmt not in ("audio", "video"):
                    continue
                orig_name = data["resolved"]["file"]
                if checkpoint.is_completed("stt", orig_name):
                    continue
                stt_cache = _prep_dir / f"{Path(orig_name).stem}.stt.json"
                if fmt == "video" and stt_cache.exists():
                    continue
                if fmt == "video" and any(
                    src_path.with_suffix(e).exists() for e in _sub_exts
                ):
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
                    orig_name = data["resolved"]["file"]
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
                                verify_ssl=stt_entry.get("verify_ssl", True),
                                params=stt_entry.get("params"),
                            )
                            data["text"] = stt_result["text"]
                            if stt_result.get("language") and not data["resolved"].get("lang"):
                                data["resolved"]["lang"] = stt_result["language"]
                            _write_phase(_prep_dir, data["target_path"],
                                         "phase1-parse", stt_result["text"])
                            checkpoint.mark_completed("stt", orig_name)
                        except Exception as e:
                            logger.warning("Transcription failed for %s: %s",
                                           data["resolved"]["file"], e)
                    elif fmt == "video":
                        lang = data["resolved"].get("lang", "")
                        source_url = data["resolved"].get("url", "")

                        # E12.73: try yt-dlp for platform URLs (captions → skip STT)
                        if source_url and config.allow_download:
                            try:
                                from lore_mcp.preprocess.parse import download_video
                                if not quiet:
                                    print(f"    {data['resolved']['file']} → download+captions", flush=True)
                                dl = download_video(source_url, str(_prep_dir), lang=lang)
                                if dl.get("captions_text"):
                                    logger.info("Captions downloaded (%s), skipping STT",
                                                dl.get("captions_source", "?"))
                                    data["text"] = dl["captions_text"]
                                    if dl.get("language") and not data["resolved"].get("lang"):
                                        data["resolved"]["lang"] = dl["language"]
                                    for k in ("title", "author", "duration", "upload_date", "captions_source"):
                                        if dl.get(k):
                                            data["resolved"][k] = dl[k]
                                    _write_phase(_prep_dir, data["target_path"],
                                                 "phase1-parse", dl["captions_text"])
                                    checkpoint.mark_completed("stt", orig_name)
                                    continue
                            except Exception as e:
                                logger.warning("yt-dlp download failed for %s: %s, falling back to STT",
                                               orig_name, e)

                        # Check for existing subtitle files alongside video
                        sub_found = False
                        for sub_ext in (".vtt", ".srt", ".en.vtt", ".fr.vtt",
                                        ".en.srt", ".fr.srt"):
                            sub_file = src_path.with_suffix(sub_ext)
                            if sub_file.exists():
                                sub_text = sub_file.read_text(encoding="utf-8", errors="replace")
                                if len(sub_text.strip()) > 10:
                                    logger.info("Subtitles found: %s", sub_file.name)
                                    if not quiet:
                                        print(f"    {orig_name} → subtitles ({sub_file.name})", flush=True)
                                    data["text"] = sub_text
                                    _write_phase(_prep_dir, data["target_path"],
                                                 "phase1-parse", sub_text)
                                    checkpoint.mark_completed("stt", orig_name)
                                    sub_found = True
                                    break
                        if sub_found:
                            continue

                        if not quiet:
                            print(f"    {data['resolved']['file']} → transcribe+frames", flush=True)
                        try:
                            source_strategy = data["resolved"].get(
                                "video_frame_strategy",
                                getattr(config, "video_frame_strategy", "scene"),
                            )
                            from lore_mcp.preprocess.parse import _get_audio_duration
                            vid_dur = _get_audio_duration(str(src_path))
                            effective_vid_timeout = max(stt_timeout, int(vid_dur * 2)) if vid_dur else stt_timeout
                            vid_result = parse_video(
                                str(src_path), stt_url, stt_model_name,
                                language=lang,
                                scene_threshold=video_scene_threshold,
                                timeout=effective_vid_timeout,
                                frame_strategy=source_strategy,
                                frame_interval=getattr(config, "video_frame_interval", 30),
                                ocr_change_threshold=getattr(config, "video_ocr_change_threshold", 0.3),
                                cache_dir=str(_prep_dir),
                                params=stt_entry.get("params"),
                            )
                            data["text"] = vid_result["text"]
                            if vid_result.get("language") and not data["resolved"].get("lang"):
                                data["resolved"]["lang"] = vid_result["language"]
                            _write_phase(_prep_dir, data["target_path"],
                                         "phase1-parse", vid_result["text"])
                            checkpoint.mark_completed("stt", orig_name)
                        except Exception as e:
                            logger.warning("Video parsing failed for %s: %s",
                                           data["resolved"]["file"], e)
            finally:
                if needs_stt:
                    stop_service(stt_entry)

    check_cancelled()
    # ── Phase 1.5: Speaker diarization (E12.125 + E12.137 + E12.138)
    if diarize_entry:
        diarize_model = diarize_entry.get("model", "")
        if diarize_model:
            from lore_mcp.preprocess.diarize import (
                diarize_audio, align_speakers, format_diarized_markdown,
                extract_speaker_audio, reconstruct_timeline,
            )
            diarized_count = 0
            _needs_fallback_stt = False
            for path_key, data in parsed.items():
                src_path = data.get("src_path")
                if not src_path:
                    continue
                fmt = detect_format(src_path.name)
                if fmt not in ("audio", "video"):
                    continue
                if not quiet:
                    print(f"    {data['resolved']['file']} → diarize", flush=True)
                import sys as _sys
                _saved_stdout, _saved_stderr = _sys.stdout, _sys.stderr
                _sys.stdout = _sys.__stdout__
                _sys.stderr = _sys.__stderr__
                try:
                    turns, diarize_err = diarize_audio(str(src_path), diarize_model, diarization_device)
                finally:
                    _sys.stdout = _saved_stdout
                    _sys.stderr = _saved_stderr
                if diarize_err:
                    logger.warning("Diarization error for %s: %s", data["resolved"]["file"], diarize_err)
                    data.setdefault("warnings", []).append(f"diarization: {diarize_err}")
                if not turns:
                    # No speaker turns — fall back to direct STT if available
                    if skip_global_stt and stt_entry and not data.get("text"):
                        data.setdefault("warnings", []).append("diarization: no turns, falling back to direct STT")
                        _needs_fallback_stt = True
                    continue
                title = Path(data["resolved"]["file"]).stem.replace("-", " ").replace("_", " ")

                # Per-speaker STT (E12.138) if STT entry available
                if stt_entry and not data.get("text"):
                    speaker_audios = extract_speaker_audio(str(src_path), turns)
                    if speaker_audios:
                        if not quiet:
                            print(f"      STT per speaker ({len(speaker_audios)} speakers)", flush=True)
                        stt_url = stt_entry.get("api_url", "")
                        stt_model_name = stt_entry.get("model", "")
                        stt_timeout = stt_entry.get("timeout", 600)
                        per_speaker = {}
                        start_service(stt_entry)
                        for spk_id, spk_data in speaker_audios.items():
                            try:
                                spk_dur = sum(s[1] - s[0] for s in spk_data["segments"])
                                effective_timeout = max(stt_timeout, int(spk_dur * 2))
                                stt_result = transcribe_audio(
                                    spk_data["path"], stt_url, stt_model_name,
                                    timeout=effective_timeout,
                                )
                                stt_text = stt_result.get("text", "") if isinstance(stt_result, dict) else str(stt_result)
                                stt_segments = _extract_stt_segments(stt_text)
                                per_speaker[spk_id] = {
                                    "text": stt_text,
                                    "segments": stt_segments,
                                    "seg_table": spk_data["segments"],
                                    "total_dur": spk_dur,
                                }
                                if not quiet:
                                    lang = stt_result.get("language", "?") if isinstance(stt_result, dict) else "?"
                                    print(f"        {spk_id}: {len(stt_segments)} segs, lang={lang}", flush=True)
                            except Exception as e:
                                logger.warning("Per-speaker STT failed for %s: %s", spk_id, e)
                                per_speaker[spk_id] = {"text": "", "segments": [], "seg_table": [], "total_dur": 0}
                            finally:
                                Path(spk_data["path"]).unlink(missing_ok=True)
                        data["text"] = reconstruct_timeline(turns, per_speaker, title)
                        _write_phase(_prep_dir, data["target_path"], "phase1-diarize", data["text"])
                        diarized_count += 1
                        continue

                # Fallback: align existing STT text with diarization turns
                if data.get("text"):
                    stt_text = data["text"]
                    segments = _extract_stt_segments(stt_text)
                    aligned = align_speakers(segments, turns)
                    data["text"] = format_diarized_markdown(aligned, title)
                    _write_phase(_prep_dir, data["target_path"], "phase1-diarize", data["text"])
                    diarized_count += 1
            if not quiet and diarized_count:
                print(f"    Diarized {diarized_count} source(s)")

    # Fallback STT for audio/video when diarization skipped global STT but produced no text (E12.143)
    if skip_global_stt and stt_entry:
        stt_url = stt_entry.get("api_url", "")
        stt_model_name = stt_entry.get("model", "")
        stt_timeout = stt_entry.get("timeout", 600)
        fallback_count = 0
        if stt_url:
            for path_key, data in parsed.items():
                src_path = data.get("src_path")
                if not src_path or data.get("text"):
                    continue
                fmt = detect_format(src_path.name)
                if fmt not in ("audio", "video"):
                    continue
                if not quiet:
                    print(f"    {data['resolved']['file']} → STT fallback (no diarization)", flush=True)
                try:
                    from lore_mcp.preprocess.parse import _get_audio_duration
                    dur = _get_audio_duration(str(src_path))
                    effective_timeout = max(stt_timeout, int(dur * 2)) if dur else stt_timeout
                    start_service(stt_entry)
                    if fmt == "audio":
                        stt_result = transcribe_audio(
                            str(src_path), stt_url, stt_model_name,
                            language=data["resolved"].get("lang", ""),
                            timeout=effective_timeout,
                            verify_ssl=stt_entry.get("verify_ssl", True),
                            params=stt_entry.get("params"),
                        )
                        data["text"] = stt_result.get("text", "") if isinstance(stt_result, dict) else str(stt_result)
                    elif fmt == "video":
                        vid_result = parse_video(
                            str(src_path), stt_url, stt_model_name,
                            language=data["resolved"].get("lang", ""),
                            timeout=effective_timeout,
                        )
                        data["text"] = vid_result.get("text", "") if isinstance(vid_result, dict) else str(vid_result)
                    if data["text"]:
                        _write_phase(_prep_dir, data["target_path"], "phase1-parse", data["text"])
                        fallback_count += 1
                except Exception as e:
                    logger.warning("Fallback STT failed for %s: %s", data["resolved"]["file"], e)
            if fallback_count and not quiet:
                print(f"    STT fallback: {fallback_count} source(s)")

    check_cancelled()
    # ── Phase 1.7: Caption inline images with VLM (E12.52)
    if caption_models:
        cap_entry = caption_models[0]
        cap_url = cap_entry.get("api_url", "")
        cap_model_name = cap_entry.get("model", "")
        if cap_url:
            image_sources = [
                (pk, d) for pk, d in parsed.items()
                if d.get("text") and d.get("src_path")
                and "base64" in (d.get("text") or "")
            ]
            if image_sources:
                if not quiet:
                    print(f"  Phase 1.7: Caption inline images ({cap_entry.get('name', '')})")
                start_service(cap_entry)
                try:
                    for path_key, data in image_sources:
                        if checkpoint.is_completed("frame_caption", path_key):
                            continue
                        if not quiet:
                            print(f"    {data['resolved']['file']} → caption images", flush=True)
                        cap_timeout = cap_entry.get("timeout", 600)
                        frame_inter = str(_prep_dir / f"{Path(path_key).stem}.frame-caption.md")
                        captioned = caption_inline_frames(
                            data["text"], cap_url, cap_model_name,
                            timeout=cap_timeout,
                            verify_ssl=cap_entry.get("verify_ssl", True),
                            intermediate_path=frame_inter,
                            params=cap_entry.get("params"),
                        )
                        data["text"] = captioned
                        _write_phase(_prep_dir, data["target_path"],
                                     "phase1-parse", captioned)
                        checkpoint.mark_completed("frame_caption", path_key)
                finally:
                    stop_service(cap_entry)

    check_cancelled()
    # ── Phase 2: Caption via Docling native (all models) ──────
    # Each model: load Docling JSON → PictureDescriptionApiModel → markdown
    has_docling_docs = any(
        d.get("docling_json") and Path(d["docling_json"]).exists()
        for d in parsed.values()
    )

    caption_stats = {"captioned": 0, "skipped": 0, "failed": 0}
    model_results = {}  # path_key -> {model_name: caption_text}

    p2_hash = _phase_hash(recipe_path, config, "phase2")
    p2_skipped = False
    if has_docling_docs and caption_models and checkpoint.is_phase_done("phase2", expected_hash=p2_hash):
        logger.info("Phase 2 skipped (checkpoint, hash=%s)", p2_hash[:8])
        p2_skipped = True
    elif has_docling_docs and caption_models and checkpoint.is_phase_done("phase2"):
        logger.info("Phase 2 config changed (hash mismatch), re-running")
        for mk in list(checkpoint._data.get("phases", {}).keys()):
            if mk.startswith("caption_"):
                checkpoint.invalidate_phase(mk)

    if p2_skipped:
        for path_key, data in parsed.items():
            if data.get("text") is None:
                continue
            target_path = data.get("target_path")
            if target_path:
                p2_file = _phase_path(_prep_dir, target_path, "phase2-caption")
                if p2_file.exists():
                    data["text"] = p2_file.read_text(encoding="utf-8")

    if has_docling_docs and caption_models and not p2_skipped:
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
                        print(f"    {data['resolved']['file']} → caption", flush=True)

                    try:
                        cap_timeout = cap_entry.get("timeout", 180)
                        if path_key in standalone_images:
                            caption_text = caption_standalone_image(
                                str(data["src_path"]), cap_url, cap_model,
                                timeout=cap_timeout,
                                verify_ssl=cap_entry.get("verify_ssl", True),
                                params=cap_entry.get("params"),
                            )
                        else:
                            caption_text = caption_with_docling(
                                docling_json, cap_url, cap_model,
                                timeout=cap_timeout,
                                concurrency=cap_entry.get("concurrency", 1),
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
                                       model_name, data["resolved"]["file"], e)
            finally:
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
                            print(f"    {data['resolved']['file']} → judge", flush=True)
                        start_service(judge_entry)
                        selected = judge_captions(
                            "", alt_text, captions_by_model,
                            judge_url, judge_model_name, judge_key,
                            verify_ssl=judge_entry.get("verify_ssl", True),
                            params=judge_entry.get("params"),
                        )
                        stop_service(judge_entry)
                    except Exception as e:
                        logger.warning("Judge failed for %s: %s", path_key, e)
                        selected = next((v for v in captions_by_model.values() if v), None)
                else:
                    selected = next((v for v in captions_by_model.values() if v), None)

                if selected:
                    data["text"] = selected
                    _write_phase(_prep_dir, data["target_path"],
                                 "phase2-caption", selected)
        checkpoint.mark_phase_done("phase2", hash_value=p2_hash)
    elif not quiet and caption_models:
        print("  Phase 2: Caption (skipped — no Docling documents)")

    check_cancelled()
    # ── Phase 3: Clean + Enrich ─────────────────────────────────
    from lore_mcp.preprocess.llm import LLMConfig
    llm_config = LLMConfig.from_registry(llm_entry) if llm_entry else None
    llm_url = (llm_entry or {}).get("api_url", "")
    llm_model_name = (llm_entry or {}).get("model", "")
    llm_key = (llm_entry or {}).get("api_key", "")
    llm_verify_ssl = (llm_entry or {}).get("verify_ssl", True)

    phase3_label = "enrich" if enrich else "clean"

    p3_hash = _phase_hash(recipe_path, config, "phase3")
    p3_skipped = False
    if checkpoint.is_phase_done("phase3", expected_hash=p3_hash):
        logger.info("Phase 3 skipped (checkpoint, hash=%s)", p3_hash[:8])
        p3_skipped = True
    elif checkpoint.is_phase_done("phase3"):
        logger.info("Phase 3 config changed (hash mismatch), re-running")
        checkpoint.invalidate_phase("phase3")

    if not p3_skipped:
        if not quiet:
            label = "Clean + Enrich" if enrich else "Clean"
            print(f"  Phase 3: {label}")

    if not p3_skipped and enrich and llm_entry:
        start_service(llm_entry)
    try:
        for path_key, data in parsed.items():
            if p3_skipped:
                break
            if data.get("text") is None:
                continue
            if checkpoint.is_completed("phase3", path_key):
                continue

            resolved = data["resolved"]
            target_path = data["target_path"]
            text = data["text"]
            input_len = len(text)

            if not quiet:
                print(f"    {resolved['file']} → clean", end="", flush=True)
            cleaned = clean_text(text)

            source_lang = resolved.get("lang", "")

            if enrich and "stt_fix" in enrich:
                if not quiet:
                    print(" → enrich:stt_fix", end="", flush=True)
                cleaned = enrich_stt_fix(cleaned, lang=source_lang, llm=llm_config)
            if enrich and "context" in enrich:
                if not quiet:
                    print(" → enrich:context", end="", flush=True)
                cleaned = enrich_context(cleaned, lang=source_lang, llm=llm_config)
            if enrich and "qa" in enrich:
                if not quiet:
                    print(" → enrich:qa", end="", flush=True)
                cleaned = enrich_qa(cleaned, lang=source_lang, llm=llm_config)
            if enrich and "meta" in enrich:
                if not quiet:
                    print(" → enrich:meta", end="", flush=True)
                cleaned = enrich_meta(cleaned, lang=source_lang, llm=llm_config)
            if enrich and "speaker_id" in enrich:
                if not quiet:
                    print(" → enrich:speaker_id", end="", flush=True)
                speakers_hint = resolved.get("speakers", "")
                cleaned = enrich_speaker_id(cleaned, speakers_hint=speakers_hint, llm=llm_config)

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
        if not p3_skipped:
            checkpoint.mark_phase_done("phase3", hash_value=p3_hash)
    finally:
        if not p3_skipped and enrich and llm_entry:
            stop_service(llm_entry)

    if p3_skipped:
        for path_key, data in parsed.items():
            if data.get("text") is None:
                continue
            target_path = data["target_path"]
            found = False
            for label in ("phase3-enrich", "phase3-clean"):
                p3_file = _phase_path(_prep_dir, target_path, label)
                if p3_file.exists():
                    data["cleaned"] = p3_file.read_text(encoding="utf-8")
                    data["input_len"] = len(data.get("text", ""))
                    data["pii"] = detect_pii(data["cleaned"])
                    found = True
                    break
            if not found:
                data["cleaned"] = clean_text(data["text"])
                data["input_len"] = len(data["text"])
                data["pii"] = detect_pii(data["cleaned"])

    check_cancelled()
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
            reported_files = {r["file"] for r in reports}
            if resolved.get("path", "") not in reported_files:
                reports.append({
                    "file": resolved.get("path", path_key),
                    "status": "error",
                    "message": "Not processed (phase 1 or 3 failure)",
                    "input_len": 0, "output_len": 0,
                })
            continue

        cleaned = data["cleaned"]
        target_path = data["target_path"]

        file_out = _final_dir / target_path.parent
        file_out.mkdir(parents=True, exist_ok=True)
        out_name = target_path.name + ".md" if target_path.suffix.lower() != ".md" else target_path.name
        out_file = file_out / out_name
        out_file.write_text(cleaned, encoding="utf-8")

        qg = quality_gate(str(out_file), force=True)

        if qg["verdict"] == "poor" and skip_poor:
            out_file.unlink()
            reports.append({
                "file": resolved["path"],
                "status": "poor",
                "message": f"Quality gate: {qg['verdict']} "
                           f"(density={qg['text_density']}, skipped via skip_poor)",
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

    # Write enriched recipe
    if recipe_out is None:
        mp = Path(recipe_path)
        recipe_out = str(mp.parent / f"{mp.stem}-prep{mp.suffix}")

    enriched = {
        "collection": recipe.get("collection", ""),
        "level": recipe.get("level", ""),
        "sources": enriched_sources,
    }
    if recipe.get("orig_dir"):
        enriched["orig_dir"] = recipe["orig_dir"]
    Path(recipe_out).write_text(
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

    if not keep_intermediates and _inter_dir.exists():
        import shutil
        shutil.rmtree(_inter_dir)

    return reports
