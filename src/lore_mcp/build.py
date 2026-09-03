"""Build workflow: manifest + models → optimized .db + metadata. See docs/architecture.md."""

import json
import logging
from pathlib import Path

from lore_mcp.embedder import Embedder
from lore_mcp.eval import run_optimize, generate_questions_from_db
from lore_mcp.ingest import ingest_with_manifest
from lore_mcp.manifest import parse_manifest
from lore_mcp.metadata import generate_all
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


def run_build(
    manifest_path: str,
    docs_dir: str,
    output_dir: str,
    embedder: Embedder | None = None,
    embedders: dict | None = None,
    skip_optimize: bool = False,
    chunk_sizes: list[int] | None = None,
    chunk_overlaps: list[int] | None = None,
    top_ks: list[int] | None = None,
    num_questions: int = 50,
    work_dir: str | None = None,
    force: bool = False,
    output_level: str = "default",
    metrics: list[str] | None = None,
    judge_url: str = "",
    judge_model: str = "",
    judge_verify_ssl: bool = True,
    report_path: str | None = None,
) -> dict:
    """Full build pipeline: validate → optimize → index → metadata."""
    manifest = parse_manifest(manifest_path)
    collection = manifest["collection"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if embedders is None and embedder is not None:
        embedders = {embedder.model_name: embedder}
    if not embedders:
        raise ValueError("Provide embedder or embedders")

    work_path = Path(work_dir) if work_dir else output_path / ".build-work"
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
    winning_chunk_size = chunk_sizes[0] if chunk_sizes else 1024
    winning_chunk_overlap = chunk_overlaps[0] if chunk_overlaps else 128

    if not skip_optimize:
        optimization = _run_optimization(
            manifest_path=manifest_path,
            docs_dir=docs_dir,
            embedders=embedders,
            work_dir=str(work_path),
            chunk_sizes=chunk_sizes,
            chunk_overlaps=chunk_overlaps,
            top_ks=top_ks,
            num_questions=num_questions,
            force=force,
            output_level=output_level,
            metrics=metrics,
            judge_url=judge_url,
            judge_model=judge_model,
            judge_verify_ssl=judge_verify_ssl,
            report_path=report_path,
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
    if not force and Path(final_db).exists():
        build_reporter.print_step("Skipped (cached)")
    else:
        if Path(final_db).exists():
            Path(final_db).unlink()
        ingest_with_manifest(
            manifest_path, docs_dir, str(output_path), final_emb,
            chunk_size=winning_chunk_size, chunk_overlap=winning_chunk_overlap,
        )
        build_reporter.print_step("Indexing", elapsed=_time.time() - t0)

    final_emb.unload()

    t0 = _time.time()
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
    manifest_path: str,
    docs_dir: str,
    embedders: dict,
    work_dir: str,
    chunk_sizes: list[int] | None,
    chunk_overlaps: list[int] | None,
    top_ks: list[int] | None,
    num_questions: int,
    force: bool,
    output_level: str = "default",
    metrics: list[str] | None = None,
    judge_url: str = "",
    judge_model: str = "",
    judge_verify_ssl: bool = True,
    report_path: str | None = None,
) -> dict:
    """Run optimization with resumability."""
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
        manifest_path=manifest_path,
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
