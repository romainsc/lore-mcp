"""Build workflow: manifest + models → optimized .db + metadata. See docs/architecture.md."""

import json
import logging
from pathlib import Path

from lore_mcp.embedder import Embedder
from lore_mcp.eval import run_optimize
from lore_mcp.ingest import ingest_with_manifest
from lore_mcp.recipe import parse_recipe
from lore_mcp.metadata import generate_all
from lore_mcp.preprocess import preprocess_sources
from lore_mcp.store import open_db, list_sources

logger = logging.getLogger(__name__)

QUESTIONS_FILE = "questions.json"
SCORES_FILE = "scores.jsonl"


def validate_models(
    configs: list[dict],
    embedders: dict | None = None,
) -> list[str]:
    """Validate all model configs before starting. Returns list of errors."""
    from lore_mcp.embedder import _probe_api

    errors = []
    for cfg in configs:
        name = cfg["name"]
        mode = cfg.get("mode", "builtin")

        if mode == "api":
            url = cfg.get("api_url")
            if not url:
                errors.append(f"{name}: mode=api but no api_url")
                continue
            if not _probe_api(url, cfg.get("api_model", name), verify=False):
                errors.append(f"{name}: API endpoint unreachable ({url})")
        elif embedders and name in embedders:
            pass
        else:
            cache_path = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{name.replace('/', '--')}"
            if not cache_path.exists():
                errors.append(f"{name}: not in HuggingFace cache, use --allow-download")

    return errors


def _start_embedders(config) -> dict:
    """Create embedders from config, starting services if needed. See E12.68."""
    from lore_mcp.embedder import create_embedder

    if config.embedding_models:
        return {
            emb_cfg["name"]: create_embedder(config, emb_cfg)
            for emb_cfg in config.embedding_models
        }

    entry = config.get_embedding_entry()
    if entry:
        from lore_mcp.preprocess.service import start_service
        start_service(entry)

    emb = create_embedder(config, entry)
    return {emb.model_name: emb}


def run_build(
    recipe_path: str,
    docs_dir: str,
    output_dir: str,
    config,
    embedders: dict | None = None,
    embedder: Embedder | None = None,
) -> dict:
    """Full build pipeline: [preprocess →] validate → optimize → index → metadata.

    All params resolved from config. embedders passed as instantiated objects.
    """
    force = config.force
    output_level = config.output_level
    skip_optimize = config.skip_optimize
    report_path = config.report_path or None
    chunk_sizes = config.optimize_chunk_sizes
    chunk_overlaps = config.optimize_chunk_overlaps
    top_ks = config.optimize_top_ks
    num_questions = config.optimize_num_questions

    _build_dir = getattr(config, "build_dir", "")

    from lore_mcp.task_manager import report_progress

    if config.preprocess:
        if _build_dir:
            # E12.90: recipe-prep goes in build_dir
            prep_recipe_path = Path(_build_dir) / (
                Path(recipe_path).stem + "-prep" + Path(recipe_path).suffix
            )
        else:
            prep_recipe_path = Path(recipe_path).parent / (
                Path(recipe_path).stem + "-prep" + Path(recipe_path).suffix
            )
        config.preprocess_recipe_out = str(prep_recipe_path)
        report_progress("Preprocessing sources")
        preprocess_sources(recipe_path, docs_dir, config)
        recipe_path = str(prep_recipe_path)
        if _build_dir:
            docs_dir = str(Path(_build_dir) / "prep")
        else:
            docs_dir = str(Path(docs_dir) / config.preprocess_prep_dir / Path(docs_dir).name)

    # Use prep dir as docs_dir if it exists (previous preprocess run)
    if not config.preprocess and _build_dir:
        prep_dir = Path(_build_dir) / "prep"
        prep_manifest = Path(_build_dir) / (
            Path(recipe_path).stem + "-prep" + Path(recipe_path).suffix
        )
        if prep_dir.exists() and any(prep_dir.iterdir()):
            docs_dir = str(prep_dir)
            if prep_manifest.exists():
                recipe_path = str(prep_manifest)

    recipe = parse_recipe(recipe_path)
    collection = getattr(config, "collection_override", "") or recipe["collection"]
    if _build_dir:
        output_path = Path(_build_dir)
    else:
        output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if embedders is None and embedder is not None:
        embedders = {embedder.model_name: embedder}
    if not embedders:
        embedders = _start_embedders(config)

    if _build_dir:
        work_path = output_path / ".work"
    elif config.work_dir:
        work_path = Path(config.work_dir)
    else:
        work_path = output_path / ".build-work"
    work_path.mkdir(parents=True, exist_ok=True)

    from lore_mcp.progress import ProgressReporter
    import time as _time

    build_reporter = ProgressReporter(
        collection=collection,
        models=list(embedders.keys()),
        total_configs=0,
        level=output_level,
    )
    build_start = _time.time()

    resumed = False
    optimization = None
    winning_model = next(iter(embedders))
    if skip_optimize:
        winning_chunk_size = config.chunk_size
        winning_chunk_overlap = config.chunk_overlap
    else:
        winning_chunk_size = chunk_sizes[0] if chunk_sizes else 1024
        winning_chunk_overlap = chunk_overlaps[0] if chunk_overlaps else 128

    if not skip_optimize:
        report_progress("Optimizing chunking parameters")
        optimization = _run_optimization(
            recipe_path=recipe_path,
            docs_dir=docs_dir,
            embedders=embedders,
            work_dir=str(work_path),
            force=force,
            output_level=output_level,
            config=config,
        )
        resumed = optimization.get("resumed", False)
        best = optimization.get("best", {})
        if best:
            winning_model = best.get("model_name", winning_model)
            winning_chunk_size = best.get("chunk_size", winning_chunk_size)
            winning_chunk_overlap = best.get("chunk_overlap", winning_chunk_overlap)

    for emb in embedders.values():
        emb.unload()

    build_reporter.print_section(
        f"Final build — {winning_model} chunk={winning_chunk_size}/{winning_chunk_overlap}"
    )

    final_db = str(output_path / f"{collection}.db")
    final_emb = embedders[winning_model]

    t0 = _time.time()
    cache_valid = False
    if not force and Path(final_db).exists():
        try:
            _db = open_db(final_db)
            _meta = {r[0]: r[1] for r in _db.execute("SELECT key, value FROM meta").fetchall()}
            _src = list_sources(_db)
            _db.close()
            cache_valid = (
                len(_src) > 0
                and _meta.get("chunk_size") == str(winning_chunk_size)
                and _meta.get("chunk_overlap") == str(winning_chunk_overlap)
                and _meta.get("model_name") == winning_model
            )
        except Exception:
            cache_valid = False

    if cache_valid:
        build_reporter.print_step("Skipped (cached)")
        report_progress("Indexing skipped (cached)")
    else:
        if Path(final_db).exists():
            Path(final_db).unlink()
        report_progress(f"Indexing {collection} ({winning_model})")
        ingest_with_manifest(
            recipe_path, docs_dir, str(output_path), final_emb,
            chunk_size=winning_chunk_size, chunk_overlap=winning_chunk_overlap,
            collection=collection,
        )
        build_reporter.print_step("Indexing", elapsed=_time.time() - t0)

    final_emb.unload()

    t0 = _time.time()
    report_progress("Generating metadata")
    generate_all(final_db)
    build_reporter.print_step("Metadata", elapsed=_time.time() - t0)

    db = open_db(final_db)
    sources = list_sources(db)
    db.close()

    report = {
        "collection": collection,
        "model_name": winning_model,
        "chunk_size": winning_chunk_size,
        "chunk_overlap": winning_chunk_overlap,
        "file_count": len(sources),
        "chunk_count": sum(s["count"] for s in sources),
        "optimization": optimization,
        "resumed": resumed,
    }

    json_report_path = output_path / "build-report.json"
    json_report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    build_reporter.print_summary(
        files=len(sources),
        chunks=sum(s["count"] for s in sources),
        configs_tested=len(optimization.get("all", [])) if optimization else 0,
        elapsed=_time.time() - build_start,
        report_path=str(json_report_path),
    )

    return report


def _run_optimization(
    recipe_path: str,
    docs_dir: str,
    embedders: dict,
    work_dir: str,
    chunk_sizes: list[int] | None = None,
    chunk_overlaps: list[int] | None = None,
    top_ks: list[int] | None = None,
    num_questions: int = 50,
    force: bool = False,
    output_level: str = "default",
    metrics: list[str] | None = None,
    judge_url: str = "",
    judge_model: str = "",
    judge_verify_ssl: bool = True,
    report_path: str | None = None,
    config=None,
) -> dict:
    """Run optimization with resumability."""
    if config is not None:
        if chunk_sizes is None:
            chunk_sizes = config.optimize_chunk_sizes
        if chunk_overlaps is None:
            chunk_overlaps = config.optimize_chunk_overlaps
        if top_ks is None:
            top_ks = config.optimize_top_ks
        if not num_questions or num_questions == 50:
            num_questions = config.optimize_num_questions or 50
        if metrics is None:
            metrics = config.optimize_metrics or None
        if not judge_url:
            judge_url = config.llm_api_url
        if not judge_model:
            judge_model = config.llm_model
            judge_verify_ssl = config.llm_verify_ssl

    work_path = Path(work_dir)
    scores_path = work_path / SCORES_FILE
    questions_path = work_path / QUESTIONS_FILE

    existing_scores = []
    resumed = False

    if not force and scores_path.exists():
        existing_scores = [
            json.loads(line)
            for line in scores_path.read_text().strip().split("\n")
            if line.strip()
        ]
        resumed = True
        logger.info("Resuming: %d existing scores", len(existing_scores))

    result = run_optimize(
        embedders=embedders,
        db_dir=work_dir,
        recipe_path=recipe_path,
        docs_dir=docs_dir,
        chunk_sizes=chunk_sizes,
        chunk_overlaps=chunk_overlaps,
        top_ks=top_ks,
        num_questions=num_questions,
        output_level=output_level,
        metrics=metrics,
        judge_url=judge_url,
        judge_model=judge_model,
        judge_verify_ssl=judge_verify_ssl,
        report_path=report_path,
    )

    with open(scores_path, "w", encoding="utf-8") as f:
        for entry in result.get("all", []):
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    result["resumed"] = resumed
    return result
