"""MCP server exposing search_docs and list_sources. See docs/architecture.md."""

import logging
import os
import threading
from pathlib import Path

from mcp.server import MCPServer

from lore_mcp.collections import (
    discover_collections,
    search_across,
    search_collection,
)
from lore_mcp.embedder import Embedder
from lore_mcp.store import list_sources as store_list_sources
from lore_mcp.store import open_db, search, validate_model

logger = logging.getLogger(__name__)

mcp = MCPServer("lore-mcp")

_embedder = None
_single_db = None
_init_lock = threading.Lock()
_config = None


def _get_config():
    """Return the loaded LoreConfig (set during main())."""
    global _config
    if _config is None:
        from lore_mcp.config import LoreConfig
        _config = LoreConfig.defaults()
    return _config


def _is_multi_collection() -> bool:
    return _get_config().is_multi_collection


def _get_single_db():
    """Lazy-load and cache the single-collection database connection."""
    global _single_db
    with _init_lock:
        if _single_db is None:
            _single_db = open_db(_get_config().db_path)
    return _single_db


def _get_embedder():
    """Lazy-load the embedder on first query."""
    global _embedder
    cfg = _get_config()
    with _init_lock:
        if _embedder is None:
            _embedder = Embedder(
                model_name=cfg.embedding_model,
                mode=cfg.embedding_mode,
                api_url=cfg.embedding_api_url or None,
                api_model=cfg.embedding_api_model or None,
            )
    return _embedder


def format_search_results(results: list[dict], backend: str) -> str:
    """Format search results for MCP tool output."""
    if not results:
        return "0 results."
    parts = []
    for r in results:
        collection = r.get("collection", "")
        prefix = f"[{collection}:{r['source_file']}]" if collection else f"[{r['source_file']}]"
        biblio_parts = []
        if r.get("title"):
            biblio_parts.append(f"Title: {r['title']}")
        if r.get("author"):
            biblio_parts.append(f"Author: {r['author']}")
        if r.get("license"):
            biblio_parts.append(f"License: {r['license']}")
        biblio = " | ".join(biblio_parts)
        header = f"{prefix} (score: {r['score']:.4f})"
        if biblio:
            header += f"\n  {biblio}"
        parts.append(f"{header}\n{r['content']}")
    header = f"{len(results)} result(s) (embedding: {backend})"
    return header + "\n\n---\n\n".join([""] + parts)


def format_sources(sources: list[dict]) -> str:
    """Format source listing for MCP tool output."""
    if not sources:
        return "0 chunks, 0 files."
    total = sum(s["count"] for s in sources)
    lines = [f"{total} chunks, {len(sources)} file(s)\n"]
    for s in sources:
        lines.append(f"  {s['source_file']}: {s['count']}")
    return "\n".join(lines)


def format_collections(collections: list[dict]) -> str:
    """Format collection listing for MCP tool output."""
    if not collections:
        return "No collections found."
    total_chunks = sum(c["chunk_count"] for c in collections)
    total_files = sum(c["file_count"] for c in collections)
    lines = [f"{len(collections)} collection(s), {total_chunks} chunks, {total_files} files\n"]
    for c in collections:
        level = f" [{c['level']}]" if c["level"] else ""
        model_info = ""
        if c.get("model_name"):
            dim = c.get("model_dim", "?")
            model_info = f" model: {c['model_name']} ({dim}d)"
        chunk_info = ""
        if c.get("chunk_size"):
            chunk_info = f" chunk: {c['chunk_size']}/{c.get('chunk_overlap', '?')}"
        params = f" ({model_info.strip()},{chunk_info})" if model_info or chunk_info else ""
        lines.append(f"  {c['name']}{level}: {c['chunk_count']} chunks, {c['file_count']} files{params}")
    return "\n".join(lines)


@mcp.tool()
def search_docs(query: str, top_k: int = 5, collection: str = "", filter: str = "") -> str:
    """Semantic search over indexed documents.

    Returns the most relevant passages for the given query,
    with similarity scores and source files. In multi-collection
    mode, specify a collection name or leave empty to search
    across all collections.

    filter: comma-separated key:value pairs to filter results.
    Available keys: source, title, author, license, level,
    date_from, date_to.
    Example: "source:architecture.md,level:libre"
    """
    from lore_mcp.store import _parse_filters
    cfg = _get_config()
    embedder = _get_embedder()
    query_embedding = embedder.embed(query)
    backend = embedder.mode if embedder.mode != "builtin" else "builtin"
    parsed_filters = _parse_filters(filter)

    if cfg.is_multi_collection:
        if collection:
            results = search_collection(cfg.db_dir, collection, query_embedding, top_k=top_k, query_text=query, reranking_model=cfg.reranking_model, filters=parsed_filters)
        else:
            results = search_across(cfg.db_dir, query_embedding, top_k=top_k, query_text=query, reranking_model=cfg.reranking_model, filters=parsed_filters)
    else:
        db = _get_single_db()
        validate_model(db, embedder.model_name, embedder.model_dim)
        results = search(db, query_embedding, top_k=top_k, query_text=query,
                         reranking_model=cfg.reranking_model, filters=parsed_filters)

    return format_search_results(results, backend)


@mcp.tool()
def list_indexed_sources(collection: str = "") -> str:
    """List all indexed files with chunk counts.

    In multi-collection mode, specify a collection name or
    leave empty to list sources across all collections.
    """
    if _is_multi_collection():
        db_dir = _get_config().db_dir
        if collection:
            from lore_mcp.collections import collection_db_path
            db = open_db(collection_db_path(db_dir, collection))
            try:
                sources = store_list_sources(db)
            finally:
                db.close()
            return format_sources(sources)
        else:
            all_sources = []
            for f in Path(db_dir).glob("*.db"):
                db = open_db(str(f))
                try:
                    sources = store_list_sources(db)
                    for s in sources:
                        s["source_file"] = f"{f.stem}/{s['source_file']}"
                    all_sources.extend(sources)
                finally:
                    db.close()
            return format_sources(all_sources)
    else:
        db = _get_single_db()
        sources = store_list_sources(db)
        return format_sources(sources)


@mcp.tool()
def list_collections() -> str:
    """List available collections with chunk and file counts.

    Only available in multi-collection mode (database.dir in config).
    """
    if not _is_multi_collection():
        return "Single-collection mode. Set database.dir in config for multi-collection."
    collections = discover_collections(_get_config().db_dir)
    return format_collections(collections)


def main():
    """Entry point for the lore-mcp CLI command."""
    import argparse

    parser = argparse.ArgumentParser(description="LORE — Local Offline Retrieval Engine for MCP")
    sub = parser.add_subparsers(dest="command")

    # Default: serve
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )

    # Common flags for all subcommands
    common = argparse.ArgumentParser(add_help=False)
    output_group = common.add_mutually_exclusive_group()
    output_group.add_argument("--quiet", action="store_true", help="No console output")
    output_group.add_argument("--progress", action="store_true", help="Minimal milestone output")
    output_group.add_argument("--verbose", action="store_true", help="Detailed per-file output")
    output_group.add_argument("--debug", action="store_true", help="Verbose + internal logs")
    common.add_argument("--config", default=None, help="Config YAML file (required for models, API keys, etc.)")
    common.add_argument("--allow-download", action="store_true",
                        help="Allow model downloads (builtin mode only)")

    # eval subcommand
    eval_parser = sub.add_parser("eval", parents=[common], help="Evaluate RAG retrieval quality")
    eval_parser.add_argument("--db", default="./lore.db",
                             help="Path to .db file")
    eval_parser.add_argument("--num-questions", type=int, default=50,
                             help="Total evaluation questions (sampled across all docs, default: 50)")
    eval_parser.add_argument("--top-k", type=int, default=5)
    eval_parser.add_argument("--output", default=None, help="Output report JSON path")

    # optimize subcommand
    optimize_parser = sub.add_parser("optimize", parents=[common], help="Optimize chunking parameters")
    opt_group = optimize_parser.add_mutually_exclusive_group(required=True)
    opt_group.add_argument("--source-dir", help="Source documents directory")
    opt_group.add_argument("--manifest", help="YAML manifest (preserves biblio metadata)")
    optimize_parser.add_argument("--docs-dir", help="Documents directory (with --manifest)")
    optimize_parser.add_argument("--db-dir", default="./optimize-dbs", help="Working directory for temp DBs")
    optimize_parser.add_argument("--num-questions", type=int, default=30,
                                 help="Total evaluation questions (sampled across all docs, default: 30)")
    optimize_parser.add_argument("--output", default=None, help="Output report JSON path")
    optimize_parser.add_argument("--report", default=None, help="Output detailed eval report (markdown)")

    # build subcommand
    build_parser = sub.add_parser("build", parents=[common], help="Build optimized .db from manifest")
    build_parser.add_argument("manifest", nargs="?", default=None, help="YAML manifest path (optional — scans docs-dir if absent)")
    build_parser.add_argument("--docs-dir", required=True, help="Source documents directory")
    build_parser.add_argument("--output-dir", required=True, help="Output directory for .db + metadata")
    build_parser.add_argument("--skip-optimize", action="store_true", help="Skip optimization, use defaults")
    build_parser.add_argument("--num-questions", type=int, default=50,
                              help="Total evaluation questions (sampled across all docs, default: 50)")
    build_parser.add_argument("--force", action="store_true", help="Ignore cached state, start fresh")
    build_parser.add_argument("--report", default=None, help="Output detailed eval report (markdown)")
    build_parser.add_argument("--preprocess", action="store_true", help="Run preprocess before build (convert + clean sources)")
    build_parser.add_argument("--orig-subdir", default=".", help="Original files subdirectory (with --preprocess)")
    build_parser.add_argument("--prep-subdir", default="prep", help="Preprocessed output subdirectory (with --preprocess)")

    # preprocess subcommand
    prep_parser = sub.add_parser("preprocess", parents=[common], help="Clean and normalize sources for RAG indexing")
    prep_parser.add_argument("manifest", help="YAML manifest path")
    prep_parser.add_argument("--docs-base-dir", required=True, help="Base directory for source files")
    prep_parser.add_argument("--orig-subdir", default=".", help="Subdirectory for original files (default: .)")
    prep_parser.add_argument("--prep-subdir", default=".", help="Subdirectory for preprocessed output (default: .)")
    prep_parser.add_argument("--manifest-out", default=None, help="Output path for enriched manifest (default: <name>-prep.yaml)")
    prep_parser.add_argument("--force", action="store_true", help="Index even poor-quality files")
    prep_parser.add_argument("--enrich", default=None, help="LLM enrichment: context,qa (comma-separated)")
    prep_parser.add_argument("--llm-url", default=None, help="LLM endpoint URL (default: LORE_LLM_URL)")
    prep_parser.add_argument("--llm-model", default=None, help="LLM model name (default: LORE_LLM_MODEL)")
    prep_parser.add_argument("--llm-key", default=None, help="LLM API key (default: LORE_LLM_KEY)")

    # enrich subcommand
    enrich_parser = sub.add_parser("enrich", parents=[common], help="LLM enrichment on preprocessed sources")
    enrich_parser.add_argument("manifest", help="YAML manifest path (use manifest-prep)")
    enrich_parser.add_argument("--docs-dir", required=True, help="Directory with preprocessed sources")
    enrich_parser.add_argument("--output-dir", required=True, help="Output directory for enriched files")
    enrich_parser.add_argument("--enrich", required=True, help="Enrichment modes: context,qa (comma-separated)")
    enrich_parser.add_argument("--llm-url", default=None, help="LLM endpoint URL")
    enrich_parser.add_argument("--llm-model", default=None, help="LLM model name")
    enrich_parser.add_argument("--llm-key", default=None, help="LLM API key")

    # lint subcommand
    lint_parser = sub.add_parser("lint", parents=[common], help="Analyze source quality before indexing")
    lint_parser.add_argument("manifest", help="YAML manifest path")
    lint_parser.add_argument("--docs-dir", default=".", help="Base directory for manifest paths (default: .)")
    lint_parser.add_argument("--report", default=None, help="Output quality report (markdown)")

    args = parser.parse_args()

    # Load config
    global _config
    from lore_mcp.config import LoreConfig
    config_path = getattr(args, "config", None)
    if config_path:
        _config = LoreConfig.from_file(config_path)
    else:
        _config = LoreConfig.defaults()

    from lore_mcp.progress import configure_logging, output_level_from_args
    output_level = output_level_from_args(args)
    configure_logging(output_level)

    if args.command == "eval":
        _run_eval(args)
    elif args.command == "optimize":
        _run_optimize(args, output_level)
    elif args.command == "build":
        _run_build(args, output_level)
    elif args.command == "lint":
        _run_lint(args)
    elif args.command == "preprocess":
        _run_preprocess(args)
    elif args.command == "enrich":
        _run_enrich(args)
    else:
        mcp.run(transport=args.transport)


def _run_eval(args):
    """Run RAG evaluation."""
    from lore_mcp.eval import EvalConfig, run_eval

    embedder = _get_embedder()
    config = EvalConfig.from_env()
    config.num_questions = args.num_questions
    config.top_k = args.top_k

    output = args.output or f"eval-report-{Path(args.db).stem}.json"
    results = run_eval(args.db, embedder, config, output_path=output)

    print(f"Evaluation complete: {results['num_questions']} questions, top_k={results['top_k']}")
    for metric, score in results["scores"].items():
        print(f"  {metric}: {score:.4f}")
    print(f"Report: {output}")


def _load_embedders_from_config_or_args(args):
    from lore_mcp.eval import parse_model_configs
    from lore_mcp.build_config import BuildConfig
    from lore_mcp.embedder import Embedder

    cfg = _get_config()
    build_config = None

    if getattr(args, "config", None):
        build_config = BuildConfig.from_file(args.config)

    embedders = None
    if cfg.embedding_models:
        embedders = {}
        for emb_cfg in cfg.embedding_models:
            embedders[emb_cfg["name"]] = Embedder(
                model_name=emb_cfg["name"],
                mode=emb_cfg.get("mode", cfg.embedding_mode),
                api_url=emb_cfg.get("api_url", cfg.embedding_api_url) or None,
                api_model=emb_cfg.get("api_model") or None,
                verify_ssl=emb_cfg.get("verify_ssl"),
            )
    else:
        embedders = {cfg.embedding_model: Embedder(
            model_name=cfg.embedding_model,
            mode=cfg.embedding_mode,
            api_url=cfg.embedding_api_url or None,
            api_model=cfg.embedding_api_model or None,
        )}

    return embedders, build_config


def _run_optimize(args, output_level="default"):
    """Run chunking parameter optimization."""
    from lore_mcp.eval import run_optimize

    docs_dir = args.docs_dir or (args.source_dir if args.source_dir else None)
    embedders, build_config = _load_embedders_from_config_or_args(args)

    kwargs = dict(
        embedder=_get_embedder() if not embedders else None,
        embedders=embedders,
        db_dir=args.db_dir,
        source_dir=args.source_dir,
        manifest_path=getattr(args, "manifest", None),
        docs_dir=docs_dir,
        num_questions=args.num_questions,
        output_level=output_level,
        report_path=getattr(args, "report", None),
    )
    cfg = _get_config()
    if build_config:
        kwargs.update(
            chunk_sizes=build_config.chunk_sizes,
            chunk_overlaps=build_config.chunk_overlaps,
            top_ks=build_config.top_ks,
            metrics=build_config.metrics,
            judge_url=build_config.judge_api_url,
            judge_model=build_config.judge_model,
            judge_verify_ssl=build_config.judge_verify_ssl,
        )
    kwargs.update(
        optimize_reranking=cfg.optimize_reranking or None,
        optimize_window_sizes=cfg.optimize_window_sizes or None,
        optimize_mmr=cfg.optimize_mmr or None,
    )
    results = run_optimize(**kwargs)

    if args.output:
        import json
        Path(args.output).write_text(json.dumps(results, indent=2))
        print(f"Report: {args.output}")


def _run_build(args, output_level="default"):
    """Run the full build workflow."""
    from lore_mcp.build import run_build, validate_models

    embedders, build_config = _load_embedders_from_config_or_args(args)

    if embedders and not getattr(args, "allow_download", False):
        configs = [{"name": n, "mode": e.mode, "api_url": e.api_url} for n, e in embedders.items()]
        errors = validate_models(configs, embedders=embedders)
        if errors:
            for e in errors:
                print(f"  ERROR: {e}")
            print("Use --allow-download to download missing models.")
            return

    manifest_path = args.manifest
    if not manifest_path:
        from lore_mcp.manifest import scan_directory
        import yaml as _yaml
        scanned = scan_directory(args.docs_dir)
        manifest_path = str(Path(args.output_dir) / "generated-manifest.yaml")
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        Path(manifest_path).write_text(
            _yaml.dump(scanned, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"  Generated manifest: {manifest_path} ({len(scanned['sources'])} sources)")

    kwargs = dict(
        manifest_path=manifest_path,
        docs_dir=args.docs_dir,
        output_dir=args.output_dir,
        embedder=_get_embedder() if not embedders else None,
        embedders=embedders,
        skip_optimize=args.skip_optimize,
        num_questions=args.num_questions,
        force=args.force,
        output_level=output_level,
        report_path=getattr(args, "report", None),
        preprocess=getattr(args, "preprocess", False),
        preprocess_orig_subdir=getattr(args, "orig_subdir", "."),
        preprocess_prep_subdir=getattr(args, "prep_subdir", "prep"),
    )
    if build_config:
        kwargs.update(
            chunk_sizes=build_config.chunk_sizes,
            chunk_overlaps=build_config.chunk_overlaps,
            top_ks=build_config.top_ks,
            metrics=build_config.metrics,
            judge_url=build_config.judge_api_url,
            judge_model=build_config.judge_model,
            judge_verify_ssl=build_config.judge_verify_ssl,
        )
    result = run_build(**kwargs)


def _run_lint(args):
    """Run source quality analysis."""
    import sys
    from lore_mcp.lint import lint_sources, format_lint_report

    has_config = getattr(args, "config", None)
    if not has_config:
        import logging
        logging.getLogger("lore_mcp").warning(
            "No --config: only text heuristics applied. "
            "Add --config for heading/content similarity scoring."
        )

    reports = lint_sources(args.docs_dir, args.manifest)

    if not getattr(args, "quiet", False):
        print(format_lint_report(reports))

    if args.report:
        Path(args.report).write_text(format_lint_report(reports), encoding="utf-8")
        print(f"Report: {args.report}")

    has_poor = any(r["verdict"] == "poor" for r in reports)
    if has_poor:
        sys.exit(1)


def _run_preprocess(args):
    """Run source preprocessing."""
    from lore_mcp.preprocess import preprocess_sources

    cfg = _get_config()
    enrich = args.enrich.split(",") if args.enrich else (cfg.enrich_techniques or None)

    llm_name = cfg.enrich_models[0] if cfg.enrich_models else None
    if llm_name and cfg.llm_registry:
        try:
            llm_entry = cfg.get_llm(llm_name)
        except KeyError:
            llm_entry = {}
    else:
        llm_entry = {}

    reports = preprocess_sources(
        args.manifest,
        args.docs_base_dir,
        orig_subdir=args.orig_subdir,
        prep_subdir=args.prep_subdir,
        manifest_out=args.manifest_out,
        force=args.force,
        enrich=enrich,
        llm_url=args.llm_url or llm_entry.get("api_url", cfg.llm_api_url),
        llm_model=args.llm_model or llm_entry.get("model", cfg.llm_model),
        llm_key=args.llm_key or llm_entry.get("api_key", cfg.llm_api_key),
    )

    for r in reports:
        status = r["status"]
        if status == "ok":
            delta = r["input_len"] - r["output_len"]
            sign = f"-{delta}" if delta > 0 else str(delta)
            print(f"  {r['file']} ({sign} chars)")
        elif status == "missing":
            print(f"  {r['file']} (MISSING)")
        elif status == "url":
            print(f"  {r['file']} (URL — {r['message']})")
        elif status == "poor":
            print(f"  {r['file']} (POOR — {r['message']})")
        elif status == "error":
            print(f"  {r['file']} (ERROR — {r['message']})")

    dup_warnings = [r for r in reports if r.get("duplicate")]
    if dup_warnings:
        print(f"\n  ⚠ Duplicate warnings ({len(dup_warnings)}):")
        for r in dup_warnings:
            print(f"    {r['file']} — {r['duplicate']}")

    pii_total = sum(len(r.get("pii", [])) for r in reports)
    if pii_total:
        print(f"\n  ⚠ PII warnings ({pii_total} findings):")
        for r in reports:
            for p in r.get("pii", []):
                print(f"    {r['file']}:{p['line']} — {p['type']}: {p['match']}")

    ok = sum(1 for r in reports if r["status"] == "ok")
    errors = [r for r in reports if r["status"] in ("missing", "error", "poor")]
    prep_dir = Path(args.docs_base_dir) / args.prep_subdir
    summary = f"{ok} files preprocessed → {prep_dir}"
    if errors:
        summary += f" ({len(errors)} failed)"
    print(f"\n{summary}")

    import json
    report_path = prep_dir / "preprocess-report.json"
    report_data = {
        "ok": [r["file"] for r in reports if r["status"] == "ok"],
        "missing": [r["file"] for r in reports if r["status"] == "missing"],
        "error": [{"file": r["file"], "message": r.get("message", "")}
                  for r in reports if r["status"] == "error"],
        "poor": [{"file": r["file"], "message": r.get("message", "")}
                 for r in reports if r["status"] == "poor"],
        "pii": [{"file": r["file"], "findings": r["pii"]}
                for r in reports if r.get("pii")],
        "duplicates": [{"file": r["file"], "type": r["duplicate"]}
                       for r in reports if r.get("duplicate")],
    }
    prep_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Report: {report_path}")

    if errors:
        import sys
        sys.exit(1)


def _run_enrich(args):
    """Run standalone LLM enrichment on preprocessed sources."""
    from lore_mcp.manifest import parse_manifest
    from lore_mcp.preprocess.enrich import enrich_context, enrich_qa

    cfg = _get_config()
    modes = args.enrich.split(",")

    llm_name = cfg.enrich_models[0] if cfg.enrich_models else None
    if llm_name and cfg.llm_registry:
        try:
            llm_entry = cfg.get_llm(llm_name)
        except KeyError:
            llm_entry = {}
    else:
        llm_entry = {}

    llm_url = args.llm_url or llm_entry.get("api_url", cfg.llm_api_url)
    llm_model = args.llm_model or llm_entry.get("model", cfg.llm_model)
    llm_key = args.llm_key or llm_entry.get("api_key", cfg.llm_api_key)

    manifest = parse_manifest(args.manifest)
    docs_dir = Path(args.docs_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for source in manifest["sources"]:
        path = source.get("path", source.get("orig", ""))
        src_file = docs_dir / path
        if not src_file.exists():
            print(f"  {path} (MISSING)")
            continue

        text = src_file.read_text(encoding="utf-8", errors="replace")

        if "context" in modes:
            text = enrich_context(text, llm_url, llm_model, llm_key)
        if "qa" in modes:
            text = enrich_qa(text, llm_url, llm_model, llm_key)

        out_file = output_dir / path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(text, encoding="utf-8")
        print(f"  {path} (enriched: {','.join(modes)})")
        count += 1

    print(f"\n{count} files enriched → {output_dir}")
