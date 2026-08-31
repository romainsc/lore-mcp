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


def _get_db_dir() -> str | None:
    """Return LORE_DB_DIR if set, else None."""
    return os.environ.get("LORE_DB_DIR")


def _get_db_path() -> str:
    """Return LORE_DB_PATH for single-collection mode."""
    return os.environ.get("LORE_DB_PATH", "./lore.db")


def _is_multi_collection() -> bool:
    """True if LORE_DB_DIR is set (multi-collection mode)."""
    return _get_db_dir() is not None


def _get_single_db():
    """Lazy-load and cache the single-collection database connection."""
    global _single_db
    with _init_lock:
        if _single_db is None:
            _single_db = open_db(_get_db_path())
    return _single_db


def _get_embedder():
    """Lazy-load the embedder on first query."""
    global _embedder
    with _init_lock:
        if _embedder is None:
            _embedder = Embedder(
                model_name=os.environ.get("LORE_MODEL", "BAAI/bge-m3"),
                mode=os.environ.get("LORE_EMBED_MODE", "builtin"),
                api_url=os.environ.get("LORE_API_URL"),
                api_model=os.environ.get("LORE_API_MODEL"),
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
def search_docs(query: str, top_k: int = 5, collection: str = "") -> str:
    """Semantic search over indexed documents.

    Returns the most relevant passages for the given query,
    with similarity scores and source files. In multi-collection
    mode, specify a collection name or leave empty to search
    across all collections.
    """
    embedder = _get_embedder()
    query_embedding = embedder.embed(query)
    backend = embedder.mode if embedder.mode != "builtin" else "builtin"

    if _is_multi_collection():
        db_dir = _get_db_dir()
        if collection:
            results = search_collection(db_dir, collection, query_embedding, top_k=top_k)
        else:
            results = search_across(db_dir, query_embedding, top_k=top_k)
    else:
        db = _get_single_db()
        validate_model(db, embedder.model_name, embedder.model_dim)
        results = search(db, query_embedding, top_k=top_k)

    return format_search_results(results, backend)


@mcp.tool()
def list_indexed_sources(collection: str = "") -> str:
    """List all indexed files with chunk counts.

    In multi-collection mode, specify a collection name or
    leave empty to list sources across all collections.
    """
    if _is_multi_collection():
        db_dir = _get_db_dir()
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

    Only available in multi-collection mode (LORE_DB_DIR set).
    """
    if not _is_multi_collection():
        return "Single-collection mode (LORE_DB_PATH). Set LORE_DB_DIR for multi-collection."
    collections = discover_collections(_get_db_dir())
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

    # eval subcommand
    eval_parser = sub.add_parser("eval", help="Evaluate RAG retrieval quality")
    eval_parser.add_argument("--db", default=os.environ.get("LORE_DB_PATH", "./lore.db"),
                             help="Path to .db file")
    eval_parser.add_argument("--num-questions", type=int, default=50)
    eval_parser.add_argument("--top-k", type=int, default=5)
    eval_parser.add_argument("--output", default=None, help="Output report JSON path")

    # optimize subcommand
    optimize_parser = sub.add_parser("optimize", help="Optimize chunking parameters")
    opt_group = optimize_parser.add_mutually_exclusive_group(required=True)
    opt_group.add_argument("--source-dir", help="Source documents directory")
    opt_group.add_argument("--manifest", help="YAML manifest (preserves biblio metadata)")
    optimize_parser.add_argument("--docs-dir", help="Documents directory (with --manifest)")
    optimize_parser.add_argument("--db-dir", default="./optimize-dbs", help="Working directory for temp DBs")
    optimize_parser.add_argument("--num-questions", type=int, default=30)
    optimize_parser.add_argument("--models", default=None,
                                 help="Comma-separated model names or path to YAML config")
    optimize_parser.add_argument("--output", default=None, help="Output report JSON path")

    # build subcommand
    build_parser = sub.add_parser("build", help="Build optimized .db from manifest")
    build_parser.add_argument("manifest", help="YAML manifest path")
    build_parser.add_argument("--docs-dir", required=True, help="Source documents directory")
    build_parser.add_argument("--output-dir", required=True, help="Output directory for .db + metadata")
    build_parser.add_argument("--models", default=None,
                              help="Comma-separated model names or YAML config path")
    build_parser.add_argument("--skip-optimize", action="store_true", help="Skip optimization, use defaults")
    build_parser.add_argument("--num-questions", type=int, default=50)
    build_parser.add_argument("--allow-download", action="store_true", help="Allow model downloads")
    build_parser.add_argument("--force", action="store_true", help="Ignore cached state, start fresh")

    args = parser.parse_args()

    if args.command == "eval":
        _run_eval(args)
    elif args.command == "optimize":
        _run_optimize(args)
    elif args.command == "build":
        _run_build(args)
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


def _run_optimize(args):
    """Run chunking parameter optimization."""
    from lore_mcp.eval import run_optimize, parse_model_configs, parse_model_configs_from_cli
    from lore_mcp.embedder import Embedder

    docs_dir = args.docs_dir or (args.source_dir if args.source_dir else None)
    embedders = None

    if args.models:
        if Path(args.models).exists():
            configs = parse_model_configs(args.models)
        else:
            configs = parse_model_configs_from_cli(args.models)
        embedders = {}
        for cfg in configs:
            embedders[cfg["name"]] = Embedder(
                model_name=cfg["name"],
                mode=cfg.get("mode", "builtin"),
                api_url=cfg.get("api_url"),
                api_model=cfg.get("api_model"),
            )

    results = run_optimize(
        embedder=_get_embedder() if not embedders else None,
        embedders=embedders,
        db_dir=args.db_dir,
        source_dir=args.source_dir,
        manifest_path=getattr(args, "manifest", None),
        docs_dir=docs_dir,
        num_questions=args.num_questions,
    )

    best = results["best"]
    if best:
        print(f"\nBest: chunk={best['chunk_size']}/{best['chunk_overlap']} "
              f"top_k={best['top_k']} avg={best['avg_score']:.4f}")

    if args.output:
        import json
        Path(args.output).write_text(json.dumps(results, indent=2))
        print(f"Report: {args.output}")


def _run_build(args):
    """Run the full build workflow."""
    from lore_mcp.build import run_build, validate_models
    from lore_mcp.eval import parse_model_configs, parse_model_configs_from_cli
    from lore_mcp.embedder import Embedder

    embedders = None
    if args.models:
        if Path(args.models).exists():
            configs = parse_model_configs(args.models)
        else:
            configs = parse_model_configs_from_cli(args.models)

        if not args.allow_download:
            errors = validate_models(configs)
            if errors:
                for e in errors:
                    print(f"  ERROR: {e}")
                print("Use --allow-download to download missing models.")
                return

        embedders = {}
        for cfg in configs:
            embedders[cfg["name"]] = Embedder(
                model_name=cfg["name"],
                mode=cfg.get("mode", "builtin"),
                api_url=cfg.get("api_url"),
                api_model=cfg.get("api_model"),
            )

    result = run_build(
        manifest_path=args.manifest,
        docs_dir=args.docs_dir,
        output_dir=args.output_dir,
        embedder=_get_embedder() if not embedders else None,
        embedders=embedders,
        skip_optimize=args.skip_optimize,
        num_questions=args.num_questions,
        force=args.force,
    )

    print(f"\nBuild complete: {result['collection']}")
    print(f"  Model: {result['model_name']}")
    print(f"  Chunk: {result['chunk_size']}/{result['chunk_overlap']}")
    print(f"  Files: {result['file_count']}, Chunks: {result['chunk_count']}")
    print(f"  Output: {args.output_dir}")
