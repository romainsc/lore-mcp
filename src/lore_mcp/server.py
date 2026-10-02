"""MCP server exposing search_docs and list_sources. See docs/architecture.md."""

import logging
import os
import threading
from pathlib import Path

from mcp.server import MCPServer

from lore_mcp.embedder import Embedder
from lore_mcp.store import list_sources as store_list_sources
from lore_mcp.store import open_db, search, validate_model

logger = logging.getLogger(__name__)

mcp = MCPServer(
    "lore-mcp",
    instructions=(
        "lore-mcp: semantic search over documents.\n"
        "- Search: search_docs(query). Instant.\n"
        "- Build index: start_build(recipe, build_dir). Long-running, poll with get_task_status().\n"
        "- Preprocess: start_preprocess(recipe, build_dir). Long-running.\n"
        "- Add source: add_source(file, build_dir). Preprocesses and indexes one file.\n"
        "- Remove source: remove_source(source, build_dir). Instant.\n"
        "- Evaluate: start_eval(build_dir). Long-running.\n"
        "- Optimize: start_optimize(recipe, build_dir). Long-running.\n"
        "- Enrich: start_enrich(recipe, build_dir). Long-running.\n"
        "- Sources: list_indexed_sources(). Instant.\n"
        "- Status: get_service_status(), get_task_status(task_id), list_tasks().\n"
        "- Lint: lint_source(path). Instant.\n"
    ),
)

_embedder = None
_db_cache: dict = {}
_init_lock = threading.Lock()
_config = None


def _get_config():
    """Return the loaded LoreConfig (set during main())."""
    global _config
    if _config is None:
        from lore_mcp.config import LoreConfig
        _config = LoreConfig.defaults()
    return _config


def _get_db(collection: str = "") -> "sqlite3.Connection":
    """Get or open a cached db connection for a collection."""
    cfg = _get_config()
    name = collection or cfg.default_collection

    # Legacy: if db_path is explicitly set and no collection specified, use it
    if not collection and cfg.db_path and cfg.db_path != "./lore.db":
        db_path = cfg.db_path
    else:
        db_path = str(cfg.collection_db(name))

    with _init_lock:
        if name not in _db_cache:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            _db_cache[name] = open_db(db_path)
    return _db_cache[name]


def _invalidate_db(collection: str = ""):
    """Drop cached db connection(s) so next query re-opens from disk."""
    with _init_lock:
        if collection:
            _db_cache.pop(collection, None)
        else:
            _db_cache.clear()


_service_started = False


def _get_embedder():
    """Lazy-load the embedder on first query. Auto-starts service from registry."""
    global _embedder, _service_started, _service_start_time, _last_embedder_error
    cfg = _get_config()
    with _init_lock:
        if _embedder is None:
            import time as _time
            logger.info("_get_embedder: creating (thread=%s, _service_started=%s)",
                        threading.current_thread().name, _service_started)

            entry = cfg.get_embedding_entry()
            if entry and not _service_started:
                logger.info("_get_embedder: starting service %s", entry.get("name"))
                from lore_mcp.preprocess.service import start_service
                start_service(entry)
                _service_started = True
                _service_start_time = _time.time()

            if not cfg.embedding_model:
                from lore_mcp.store import get_meta
                db = _get_db()
                meta = get_meta(db)
                model = meta.get("model_name", "")
                if not model:
                    raise ValueError(
                        "No embedding model configured and no model_name in DB meta. "
                        "Set embedding.model in config.yaml or use a .db with model metadata."
                    )
                logger.info("Auto-configured embedding model from DB: %s", model)
                cfg.embedding_model = model

            from lore_mcp.embedder import create_embedder
            try:
                _embedder = create_embedder(cfg, entry)
                _last_embedder_error = ""
                logger.info("_get_embedder: embedder created (%s, mode=%s)",
                            _embedder.model_name, _embedder.mode)
            except Exception as e:
                _last_embedder_error = str(e)
                raise
        else:
            logger.debug("_get_embedder: reusing existing embedder")
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
    backend = embedder.mode if embedder.mode != "builtin" else "builtin"
    parsed_filters = _parse_filters(filter)

    db = _get_db(collection)
    validate_model(db, embedder.model_name, embedder.model_dim)
    query_embedding = embedder.embed(query)
    results = search(db, query_embedding, top_k=top_k, query_text=query,
                     reranking_model=cfg.reranking_model, filters=parsed_filters)

    return format_search_results(results, backend)


@mcp.tool()
def list_indexed_sources(collection: str = "") -> str:
    """List all indexed files with chunk counts.

    In multi-collection mode, specify a collection name or
    leave empty to list sources across all collections.
    """
    db = _get_db(collection)
    sources = store_list_sources(db)
    return format_sources(sources)


@mcp.tool()
def list_collections() -> str:
    """List available collections with chunk and file counts.

    Only available in multi-collection mode (database.dir in config).
    """
    cfg = _get_config()
    data_dir = cfg.data_dir
    if not data_dir.exists():
        return f"No collections found in {data_dir}"
    db_files = list(data_dir.rglob("*.db"))
    if not db_files:
        return f"No collections found in {data_dir}"
    collections = []
    for db_file in sorted(db_files):
        col_name = db_file.stem
        try:
            db = open_db(str(db_file))
            sources = store_list_sources(db)
            total_chunks = sum(s.get("chunk_count", 0) for s in sources)
            collections.append({
                "name": col_name,
                "files": len(sources),
                "chunks": total_chunks,
            })
            db.close()
        except Exception:
            collections.append({"name": col_name, "files": 0, "chunks": 0})
    if len(collections) == 1:
        c = collections[0]
        return f"1 collection: {c['name']} ({c['files']} files, {c['chunks']} chunks)"
    lines = [f"{len(collections)} collection(s):"]
    for c in collections:
        lines.append(f"  {c['name']}: {c['files']} files, {c['chunks']} chunks")
    return "\n".join(lines)


@mcp.tool()
def lint_source(path: str) -> str:
    """Analyze a source file for RAG indexing quality.

    Returns verdict, text density, heading structure, and
    quality score. Use before indexing to identify poor sources.
    """
    from lore_mcp.lint import analyze_file
    p = Path(path)
    if not p.exists():
        return f"Error: file not found — {path}"
    try:
        report = analyze_file(p)
        lines = [
            f"File: {report['file']}",
            f"Verdict: {report['verdict']}",
            f"Text density: {report['text_density']:.2f}",
            f"Words: {report['word_count']}",
            f"Headings: {report['heading_count']} (depth {report.get('heading_depth', 0)})",
            f"Structure score: {report.get('structure_score', 0):.2f}",
        ]
        if report.get("base64_count"):
            lines.append(f"Base64 images: {report['base64_count']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error analyzing {path}: {e}"


@mcp.tool()
def list_pipeline_state() -> str:
    """List resumable pipeline checkpoints.

    Shows checkpoint states stored in XDG_STATE_HOME,
    with hash, size, phase count, and source count.
    """
    from lore_mcp.checkpoint import list_states
    states = list_states()
    if not states:
        return "No pipeline states found."
    lines = []
    for s in states:
        lines.append(
            f"{s['hash']}  {s.get('size_mb', 0):.1f} MB  "
            f"{s.get('phases', 0)} phases  {s.get('sources', 0)} sources"
        )
    return "\n".join(lines)


@mcp.tool()
def purge_pipeline_state(
    hash: str = "", older_than_days: int = 0, purge_all: bool = False
) -> str:
    """Clean up pipeline checkpoint state.

    Specify hash to purge one state, older_than_days to purge
    old states, or purge_all=true to remove everything.
    """
    from lore_mcp.checkpoint import purge_state_by_hash, purge_states
    if hash:
        ok = purge_state_by_hash(hash)
        return f"Purged {hash}" if ok else f"State {hash} not found"
    days = older_than_days if older_than_days else 7
    removed = purge_states(max_age_days=days, purge_all=purge_all)
    return f"Purged {removed} state(s)"


_service_start_time = 0
_last_embedder_error = ""

from lore_mcp.task_manager import TaskManager
_task_manager = TaskManager()


@mcp.tool()
def get_task_status(task_id: str) -> str:
    """Check status of a background task.

    Returns task state (pending/running/completed/failed),
    progress message, result or error, and elapsed time.
    Poll this after starting a long-running operation.
    """
    import time as _time
    info = _task_manager.status(task_id)
    if not info:
        return f"Task {task_id} not found"
    elapsed = int((info.completed_at or _time.time()) - info.started_at)
    lines = [f"Task {info.id} ({info.name}): {info.status}"]
    if info.progress:
        lines.append(f"Progress: {info.progress}")
    if info.result:
        lines.append(f"Result: {info.result}")
    if info.error:
        lines.append(f"Error: {info.error}")
    lines.append(f"Elapsed: {elapsed}s")
    return "\n".join(lines)


@mcp.tool()
def cancel_task(task_id: str) -> str:
    """Cancel a pending background task.

    Only tasks waiting in the queue (pending) can be cancelled.
    Running tasks must complete or be interrupted externally.
    """
    if _task_manager.cancel(task_id):
        return f"Task {task_id} cancelled"
    return f"Task {task_id} cannot be cancelled (not pending or not found)"


@mcp.tool()
def list_tasks() -> str:
    """List all background tasks with their status.

    Shows task ID, name, status, and elapsed time for
    each task started in this session.
    """
    import time as _time
    tasks = _task_manager.list_tasks()
    if not tasks:
        return "No tasks"
    lines = []
    for t in tasks:
        elapsed = int((t.completed_at or _time.time()) - t.started_at)
        lines.append(f"{t.id} {t.name}: {t.status} ({elapsed}s)")
    return "\n".join(lines)


@mcp.tool()
def get_service_status() -> str:
    """Report status of inference services and embedder.

    Returns the state of each registered service (ready/unavailable/starting),
    uptime, last error, and embedder state.
    """
    import time
    from lore_mcp.preprocess.service import _running_services, check_service

    lines = []
    if _running_services:
        for entry in _running_services:
            name = entry.get("name", "unknown")
            healthy = check_service(entry)
            state = "ready" if healthy else "starting" if _service_started else "unavailable"
            line = f"Service {name}: {state}"
            if _service_start_time:
                uptime = int(time.time() - _service_start_time)
                line += f" (uptime: {uptime}s)"
            lines.append(line)
    else:
        lines.append("No services registered")

    if _embedder is not None:
        lines.append(f"Embedder: loaded ({_embedder.model_name}, mode={_embedder.mode})")
    else:
        state = "starting" if _service_started else "not loaded"
        lines.append(f"Embedder: {state}")

    if _last_embedder_error:
        lines.append(f"Last error: {_last_embedder_error}")

    return "\n".join(lines)


# ── E3.09b-f: Long-running MCP tools ─────────────────────


@mcp.tool()
def start_build(recipe: str, build_dir: str, force: bool = False) -> str:
    """Build a searchable index from a recipe file.

    Runs preprocessing, optimization, and indexing in background.
    Returns a task ID — poll with get_task_status().

    recipe: path to YAML recipe file (sources + options)
    build_dir: output directory for .db, prep/, reports
    force: rebuild from scratch, ignore cached state
    """
    from lore_mcp.build import run_build

    cfg = _get_config()
    cfg.build_dir = build_dir
    cfg.force = force
    cfg.preprocess = True
    cfg.output_level = "quiet"
    docs_dir = getattr(cfg, "orig_dir", None) or "."

    def _do_build():
        return run_build(recipe, docs_dir, build_dir, cfg)

    task_id = _task_manager.start("build", _do_build)
    return f"Build started: {task_id}. Poll with get_task_status('{task_id}')"


@mcp.tool()
def start_preprocess(recipe: str, build_dir: str, force: bool = False) -> str:
    """Preprocess sources from a recipe file.

    Parses, cleans, and enriches sources. Results in build_dir/prep/.
    Returns a task ID — poll with get_task_status().

    recipe: path to YAML recipe file
    build_dir: output directory for prep/ and intermediates
    force: reprocess from scratch
    """
    from lore_mcp.preprocess import preprocess_sources

    cfg = _get_config()
    cfg.build_dir = build_dir
    cfg.force = force
    cfg.output_level = "quiet"
    docs_dir = getattr(cfg, "orig_dir", None) or "."

    def _do_preprocess():
        return preprocess_sources(recipe, docs_dir, cfg)

    task_id = _task_manager.start("preprocess", _do_preprocess)
    return f"Preprocess started: {task_id}. Poll with get_task_status('{task_id}')"


@mcp.tool()
def add_source(
    file: str,
    collection: str = "",
    url: str = "",
    title: str = "",
    author: str = "",
    license: str = "",
    date: str = "",
    lang: str = "",
    level: str = "",
    enrich: str = "",
    preprocess: bool = True,
) -> str:
    """Add a source to the index.

    Preprocesses (parse, clean, enrich) and indexes a single file.
    If the source already exists, it is re-indexed.

    file: path to source file (any supported format)
    collection: target collection (default from config)

    Advanced:
    enrich: override enrichment techniques (comma-separated)
    preprocess: set false if file is already clean markdown
    """
    import yaml
    import tempfile

    cfg = _get_config()
    col_name = collection or cfg.default_collection
    col_dir = cfg.collection_dir(col_name)
    db_path = str(cfg.collection_db(col_name))
    prep_dir = col_dir / "prep"
    file_path = Path(file)

    entry = {"file": file}
    for k, v in [("url", url), ("title", title), ("author", author),
                 ("license", license), ("date", date), ("lang", lang),
                 ("level", level)]:
        if v:
            entry[k] = v

    source_meta = {k: v for k, v in entry.items() if k != "file" and k != "url"}

    recipe_data = {"collection": col_name, "sources": [entry]}
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="lore-add-"
    )
    tmp.write(yaml.dump(recipe_data, default_flow_style=False, allow_unicode=True))
    tmp.close()

    def _do_add():
        try:
            from lore_mcp.ingest import ingest_source
            from lore_mcp.preprocess.parse import detect_format

            # Resolve source file
            md_file = file_path
            if not md_file.exists() and url:
                import urllib.request
                md_file = Path(tempfile.mkdtemp()) / file_path.name
                urllib.request.urlretrieve(url, str(md_file))

            if not md_file.exists():
                return {"file_count": 0, "chunk_count": 0,
                        "errors": [f"File not found: {file}"]}

            # Preprocess if needed
            if preprocess:
                fmt = detect_format(str(md_file))
                if fmt != "markdown":
                    from lore_mcp.preprocess.parse import parse_to_markdown
                    text = parse_to_markdown(str(md_file))
                    prep_dir.mkdir(parents=True, exist_ok=True)
                    prep_file = prep_dir / (md_file.stem + ".md")
                    prep_file.write_text(text, encoding="utf-8")
                    md_file = prep_file

                from lore_mcp.preprocess import clean_text
                text = md_file.read_text(encoding="utf-8")
                cleaned = clean_text(text)
                md_file.write_text(cleaned, encoding="utf-8")

            # Enrich if configured
            if enrich:
                from lore_mcp.config import LoreConfig
                enrich_cfg = LoreConfig.from_file(str(Path(tmp.name).parent / "dummy")) if False else cfg
                enrich_cfg.enrich_techniques = enrich.split(",")

            # Ingest
            col_dir.mkdir(parents=True, exist_ok=True)
            db_exists = Path(db_path).exists()

            if db_exists:
                embedder = _get_embedder()
                result = ingest_source(db_path, md_file, embedder,
                                       source_meta or None)
            else:
                from lore_mcp.store import create_tables
                embedder = _get_embedder()
                db = open_db(db_path)
                create_tables(db, embedder.model_name, embedder.model_dim,
                              chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)
                db.close()
                result = ingest_source(db_path, md_file, embedder,
                                       source_meta or None)

            _invalidate_db(col_name)
            return result
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    task_id = _task_manager.start("add_source", _do_add)
    return f"Adding source: {task_id}. Poll with get_task_status('{task_id}')"


@mcp.tool()
def remove_source(source: str, collection: str = "") -> str:
    """Remove a source from the index.

    source: source file name as shown in list_indexed_sources
    collection: target collection (default from config)
    """
    from lore_mcp.store import delete_source_chunks

    cfg = _get_config()
    col_name = collection or cfg.default_collection
    db_path = str(cfg.collection_db(col_name))

    if not Path(db_path).exists():
        return f"No .db found for collection '{col_name}'"

    db = open_db(db_path)

    existing = db.execute(
        "SELECT source_file FROM sources WHERE source_file = ?", (source,)
    ).fetchone()
    if not existing:
        db.close()
        return f"Source '{source}' not found in collection '{col_name}'"

    delete_source_chunks(db, source)
    db.close()
    _invalidate_db(col_name)
    return f"Removed '{source}' from collection '{col_name}'"


@mcp.tool()
def start_eval(build_dir: str, num_questions: int = 50) -> str:
    """Evaluate retrieval quality of an indexed collection.

    Runs evaluation with heading-based questions and reports
    NDCG, recall, hit, and other metrics. Returns a task ID.

    build_dir: directory containing the .db to evaluate
    num_questions: number of evaluation questions to generate
    """
    from lore_mcp.eval import EvalConfig, run_eval

    db_files = list(Path(build_dir).glob("*.db"))
    if not db_files:
        return f"No .db found in {build_dir}"

    cfg = _get_config()
    eval_cfg = EvalConfig(
        llm_url=cfg.llm_api_url,
        llm_model=cfg.llm_model,
        verify_ssl=cfg.llm_verify_ssl,
    )
    eval_cfg.num_questions = num_questions

    db_path = str(db_files[0])
    output = str(Path(build_dir) / "eval-report.json")

    def _do_eval():
        embedder = _get_embedder()
        results = run_eval(db_path, embedder, eval_cfg, output_path=output)
        scores = ", ".join(f"{k}={v:.3f}" for k, v in results.get("scores", {}).items())
        return f"{results.get('num_questions', 0)} questions. {scores}"

    task_id = _task_manager.start("eval", _do_eval)
    return f"Eval started: {task_id}. Poll with get_task_status('{task_id}')"


@mcp.tool()
def start_optimize(recipe: str, build_dir: str) -> str:
    """Auto-optimize chunking parameters for best retrieval quality.

    Tests multiple chunk_size, overlap, and top_k combinations.
    Returns a task ID.

    recipe: path to YAML recipe file
    build_dir: output directory for optimized .db
    """
    from lore_mcp.eval import run_optimize

    cfg = _get_config()
    prep_dir = Path(build_dir) / "prep"
    docs_dir = str(prep_dir) if prep_dir.exists() else "."

    def _do_optimize():
        embedder = _get_embedder()
        results = run_optimize(
            embedder=embedder,
            recipe_path=recipe,
            docs_dir=docs_dir,
            db_dir=build_dir,
            num_questions=cfg.optimize_num_questions,
            output_level="quiet",
        )
        best = results.get("best", {})
        return (
            f"Best: chunk={best.get('chunk_size')}/{best.get('chunk_overlap')} "
            f"top_k={best.get('top_k')} avg={best.get('avg_score', 0):.4f}"
        )

    task_id = _task_manager.start("optimize", _do_optimize)
    return f"Optimize started: {task_id}. Poll with get_task_status('{task_id}')"


@mcp.tool()
def start_enrich(recipe: str, build_dir: str, techniques: str = "context,qa,meta") -> str:
    """Enrich preprocessed sources with LLM-generated content.

    Adds contextual paragraphs, generated questions, and metadata
    summaries per section. Returns a task ID.

    recipe: path to YAML recipe file
    build_dir: build directory with prep/ sources
    techniques: comma-separated enrichment techniques (context, qa, meta)
    """
    from lore_mcp.preprocess import preprocess_sources

    cfg = _get_config()
    cfg.build_dir = build_dir
    cfg.output_level = "quiet"
    cfg.enrich_techniques = techniques.split(",")
    docs_dir = getattr(cfg, "orig_dir", None) or "."

    def _do_enrich():
        return preprocess_sources(recipe, docs_dir, cfg)

    task_id = _task_manager.start("enrich", _do_enrich)
    return f"Enrich started: {task_id}. Poll with get_task_status('{task_id}')"


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
    parser.add_argument(
        "--config",
        default=None,
        help="Config YAML file (for MCP serve mode)",
    )

    # Common flags for all subcommands
    common = argparse.ArgumentParser(add_help=False)
    output_group = common.add_mutually_exclusive_group()
    output_group.add_argument("--quiet", action="store_true", help="No console output")
    output_group.add_argument("--progress", action="store_true", help="Minimal milestone output")
    output_group.add_argument("--verbose", action="store_true", help="Detailed per-file output")
    common.add_argument("--debug", action="count", default=0, help="Debug lore-mcp (-dd for all components)")
    common.add_argument("--config", default=None, help="Config YAML file (required for models, API keys, etc.)")
    common.add_argument("--allow-download", action="store_true",
                        help="Allow downloads (models from HuggingFace + sources from URLs)")

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
    opt_group.add_argument("--recipe", help="YAML recipe (preserves biblio metadata)")
    optimize_parser.add_argument("--docs-dir", help="Documents directory (with --recipe)")
    optimize_parser.add_argument("--db-dir", default="./optimize-dbs", help="Working directory for temp DBs")
    optimize_parser.add_argument("--num-questions", type=int, default=30,
                                 help="Total evaluation questions (sampled across all docs, default: 30)")
    optimize_parser.add_argument("--output", default=None, help="Output report JSON path")
    optimize_parser.add_argument("--report", default=None, help="Output detailed eval report (markdown)")

    # build subcommand
    build_parser = sub.add_parser("build", parents=[common], help="Build optimized .db from recipe")
    build_parser.add_argument("recipe", nargs="?", default=None, help="YAML recipe path (optional — scans --orig-dir if absent)")
    build_parser.add_argument("--orig-dir", default=None, help="Read-only source files directory")
    build_parser.add_argument("--build-dir", default=None, help="Build output directory (.db, prep/, .work/, reports)")
    build_parser.add_argument("--skip-optimize", action="store_true", help="Skip optimization, use defaults")
    build_parser.add_argument("--num-questions", type=int, default=50,
                              help="Total evaluation questions (sampled across all docs, default: 50)")
    build_parser.add_argument("--force", action="store_true", help="Ignore cached state, start fresh")
    build_parser.add_argument("--report", default=None, help="Output detailed eval report (markdown)")
    build_parser.add_argument("--preprocess", action="store_true", help="Run preprocess before build (convert + clean sources)")
    build_parser.add_argument("--keep-intermediates", action="store_true", help="Keep intermediate files in .work/ after build")
    # Deprecated flags (backward compat)
    build_parser.add_argument("--docs-dir", default=None, help="[DEPRECATED] Use --orig-dir + --build-dir")
    build_parser.add_argument("--output-dir", default=None, help="[DEPRECATED] Use --build-dir")
    build_parser.add_argument("--prep-dir", default=None, help="[DEPRECATED] Use --build-dir")
    build_parser.add_argument("--intermediates-dir", default=None, help="[DEPRECATED] Use --build-dir")

    # preprocess subcommand
    prep_parser = sub.add_parser("preprocess", parents=[common], help="Clean and normalize sources for RAG indexing")
    prep_parser.add_argument("recipe", nargs="?", default=None, help="YAML recipe path (optional — scans --orig-dir if absent)")
    prep_parser.add_argument("--orig-dir", default=None, help="Read-only source files directory")
    prep_parser.add_argument("--build-dir", default=None, help="Build output directory (prep/, .work/, reports)")
    prep_parser.add_argument("--recipe-out", default=None, help="Output path for enriched recipe (default: <name>-prep.yaml)")
    prep_parser.add_argument("--force", action="store_true", help="Index even poor-quality files")
    prep_parser.add_argument("--keep-intermediates", action="store_true", help="Keep intermediate files in .work/")
    prep_parser.add_argument("--report", default=None, help="Report file path (default: ./preprocess-report.json). Serves as checkpoint for resume")
    # Deprecated flags (backward compat)
    prep_parser.add_argument("--docs-base-dir", default=None, help="[DEPRECATED] Use --orig-dir + --build-dir")
    prep_parser.add_argument("--prep-dir", default=None, help="[DEPRECATED] Use --build-dir")
    prep_parser.add_argument("--intermediates-dir", default=None, help="[DEPRECATED] Use --build-dir")
    prep_parser.add_argument("--enrich", default=None, help="LLM enrichment: context,qa (comma-separated)")
    prep_parser.add_argument("--llm-url", default=None, help="LLM endpoint URL (overrides config)")
    prep_parser.add_argument("--llm-model", default=None, help="LLM model name (overrides config)")
    prep_parser.add_argument("--llm-key", default=None, help="LLM API key (overrides config)")

    # enrich subcommand
    enrich_parser = sub.add_parser("enrich", parents=[common], help="LLM enrichment on preprocessed sources")
    enrich_parser.add_argument("recipe", help="YAML recipe path (use recipe-prep)")
    enrich_parser.add_argument("--docs-dir", required=True, help="Directory with preprocessed sources")
    enrich_parser.add_argument("--output-dir", required=True, help="Output directory for enriched files")
    enrich_parser.add_argument("--enrich", required=True, help="Enrichment modes: context,qa (comma-separated)")
    enrich_parser.add_argument("--llm-url", default=None, help="LLM endpoint URL")
    enrich_parser.add_argument("--llm-model", default=None, help="LLM model name")
    enrich_parser.add_argument("--llm-key", default=None, help="LLM API key")

    # lint subcommand
    lint_parser = sub.add_parser("lint", parents=[common], help="Analyze source quality before indexing")
    lint_parser.add_argument("recipe", help="YAML recipe path")
    lint_parser.add_argument("--docs-dir", default=".", help="Base directory for recipe paths (default: .)")
    lint_parser.add_argument("--report", default=None, help="Output quality report (markdown)")

    # state subcommand
    sub.add_parser("init", help="Generate a bootstrap config.yaml with all options documented")

    state_parser = sub.add_parser("state", help="Manage pipeline state (intermediates)")
    state_parser.add_argument("--list", action="store_true", help="List all pipeline states")
    state_parser.add_argument("--purge", nargs="?", const="__interactive__", default=None, help="Purge a state by hash, or with --older-than / --all")
    state_parser.add_argument("--older-than", type=int, default=None, help="Purge states older than N days (with --purge)")
    state_parser.add_argument("--all", action="store_true", help="Purge all states (with --purge)")

    args = parser.parse_args()

    # Load config
    global _config
    from lore_mcp.config import LoreConfig
    config_path = getattr(args, "config", None)
    if config_path:
        _config = LoreConfig.from_file(config_path)
    else:
        xdg_config = Path.home() / ".config" / "lore-mcp" / "config.yaml"
        if xdg_config.exists():
            _config = LoreConfig.from_file(str(xdg_config))
        else:
            _config = LoreConfig.defaults()

    from lore_mcp.progress import configure_logging, output_level_from_args
    output_level = output_level_from_args(args)
    configure_logging(output_level)

    if args.command == "init":
        _run_init()
    elif args.command == "eval":
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
    elif args.command == "state":
        _run_state(args)
    else:
        mcp.run(transport=args.transport)


def _run_init():
    """Generate a bootstrap config.yaml."""
    import importlib.resources
    target = Path("config.yaml")
    if target.exists():
        print(f"config.yaml already exists. Remove it first or use a different directory.")
        return
    bootstrap = importlib.resources.files("lore_mcp").joinpath("bootstrap.yaml")
    target.write_text(bootstrap.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Generated {target} with all options documented.")
    print(f"Uncomment and edit the options you need.")


def _run_state(args):
    """Manage pipeline state directories."""
    from lore_mcp.checkpoint import list_states, purge_states, purge_state_by_hash

    if args.purge is not None:
        if getattr(args, "all", False):
            n = purge_states(purge_all=True)
            print(f"Purged {n} state(s).")
        elif args.older_than is not None:
            n = purge_states(max_age_days=args.older_than)
            print(f"Purged {n} state(s) older than {args.older_than} days.")
        elif args.purge != "__interactive__":
            ok = purge_state_by_hash(args.purge)
            if ok:
                print(f"Purged state {args.purge}.")
            else:
                print(f"State {args.purge} not found.")
        else:
            print("Usage: --purge <hash> | --purge --older-than N | --purge --all")
    else:
        states = list_states()
        if not states:
            print("No pipeline states.")
        else:
            print(f"{len(states)} state(s):\n")
            for s in states:
                phases = s.get("phases", 0)
                sources = s.get("sources", 0)
                print(f"  {s['hash']}  {s['size_mb']:>6.1f} MB  {phases} phases  {sources} sources")
            print(f"\n  Location: {states[0]['path'].rsplit('/', 1)[0]}")


def _run_eval(args):
    """Run RAG evaluation."""
    from lore_mcp.eval import EvalConfig, run_eval

    embedder = _get_embedder()
    cfg = _get_config()
    config = EvalConfig(
        llm_url=cfg.llm_api_url,
        llm_model=cfg.llm_model,
        verify_ssl=cfg.llm_verify_ssl,
    )
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

    from lore_mcp.embedder import create_embedder
    embedders = None
    if cfg.embedding_models:
        embedders = {
            emb_cfg["name"]: create_embedder(cfg, emb_cfg)
            for emb_cfg in cfg.embedding_models
        }
    else:
        entry = cfg.get_embedding_entry()
        if entry:
            from lore_mcp.preprocess.service import start_service
            start_service(entry)
        emb = create_embedder(cfg, entry)
        embedders = {emb.model_name: emb}

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
        recipe_path=getattr(args, "recipe", None),
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

    has_preprocess = getattr(args, "preprocess", False)

    if has_preprocess:
        embedders = None
        build_config = None
        if getattr(args, "config", None):
            from lore_mcp.build_config import BuildConfig
            build_config = BuildConfig.from_file(args.config)
    else:
        embedders, build_config = _load_embedders_from_config_or_args(args)
        if embedders and not getattr(args, "allow_download", False):
            configs = [{"name": n, "mode": e.mode, "api_url": e.api_url} for n, e in embedders.items()]
            errors = validate_models(configs, embedders=embedders)
            if errors:
                for e in errors:
                    print(f"  ERROR: {e}")
                return

    # E12.90: resolve directory arguments with backward compat
    import warnings as _warnings
    _build_dir = getattr(args, "build_dir", None)
    _orig_dir = getattr(args, "orig_dir", None)
    _docs_dir = getattr(args, "docs_dir", None)
    _output_dir = getattr(args, "output_dir", None)
    _prep_dir_arg = getattr(args, "prep_dir", None)
    _inter_dir = getattr(args, "intermediates_dir", None)

    if _docs_dir and not _build_dir:
        _warnings.warn("--docs-dir is deprecated, use --orig-dir + --build-dir", DeprecationWarning, stacklevel=1)
    if _output_dir and not _build_dir:
        _warnings.warn("--output-dir is deprecated, use --build-dir", DeprecationWarning, stacklevel=1)

    if _build_dir:
        docs_dir = _orig_dir or _docs_dir or "."
        output_dir = _build_dir
    elif _output_dir or _docs_dir:
        docs_dir = _docs_dir or _orig_dir or "."
        output_dir = _output_dir or "."
    else:
        print("Error: --build-dir is required (or use deprecated --output-dir + --docs-dir)")
        sys.exit(1)

    recipe_path = args.recipe
    if not recipe_path:
        from lore_mcp.recipe import scan_directory
        import yaml as _yaml
        scan_base = _orig_dir or docs_dir
        scanned = scan_directory(scan_base)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        recipe_path = str(Path(output_dir) / "generated-recipe.yaml")
        Path(recipe_path).parent.mkdir(parents=True, exist_ok=True)
        Path(recipe_path).write_text(
            _yaml.dump(scanned, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"  Generated recipe: {recipe_path} ({len(scanned['sources'])} sources)")

    cfg = _get_config()
    cfg.skip_optimize = args.skip_optimize
    cfg.force = args.force
    cfg.output_level = output_level
    cfg.report_path = getattr(args, "report", None) or ""
    cfg.preprocess = has_preprocess
    cfg.allow_download = getattr(args, "allow_download", False)
    cfg.optimize_num_questions = args.num_questions
    cfg.keep_intermediates = getattr(args, "keep_intermediates", False)

    if _build_dir:
        cfg.build_dir = _build_dir
        cfg.orig_dir = _orig_dir or docs_dir
    else:
        cfg.preprocess_orig_dir = getattr(args, "orig_dir", None) or "."
        cfg.preprocess_prep_dir = _prep_dir_arg or "prep"
        cfg.intermediates_dir = _inter_dir or ""

    if build_config:
        cfg.optimize_chunk_sizes = build_config.chunk_sizes
        cfg.optimize_chunk_overlaps = build_config.chunk_overlaps
        cfg.optimize_top_ks = build_config.top_ks
        cfg.optimize_metrics = build_config.metrics or cfg.optimize_metrics

    result = run_build(
        recipe_path, docs_dir, output_dir, cfg,
        embedders=embedders,
        embedder=_get_embedder() if (not embedders and not has_preprocess) else None,
    )


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

    reports = lint_sources(args.docs_dir, args.recipe)

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
    from lore_mcp.progress import output_level_from_args

    cfg = _get_config()

    # CLI overrides on config
    if args.enrich:
        cfg.enrich_techniques = args.enrich.split(",")
    cfg.force = args.force
    cfg.output_level = output_level_from_args(args)
    cfg.report_path = getattr(args, "report", None) or ""
    cfg.allow_download = getattr(args, "allow_download", False)
    cfg.preprocess_recipe_out = args.recipe_out or ""
    cfg.keep_intermediates = getattr(args, "keep_intermediates", False)

    # E12.90: resolve directory arguments with backward compat
    import warnings as _warnings
    _build_dir = getattr(args, "build_dir", None)
    _orig_dir = getattr(args, "orig_dir", None)
    _docs_base_dir = getattr(args, "docs_base_dir", None)
    _prep_dir_arg = getattr(args, "prep_dir", None)
    _inter_dir = getattr(args, "intermediates_dir", None)

    if _docs_base_dir and not _build_dir:
        _warnings.warn("--docs-base-dir is deprecated, use --orig-dir + --build-dir", DeprecationWarning, stacklevel=1)

    if _build_dir:
        cfg.build_dir = _build_dir
        cfg.orig_dir = _orig_dir or "."
        docs_base_dir = _orig_dir or "."
    elif _docs_base_dir:
        docs_base_dir = _docs_base_dir
        cfg.preprocess_orig_dir = _orig_dir or "."
        cfg.preprocess_prep_dir = _prep_dir_arg or "."
        cfg.intermediates_dir = _inter_dir or ""
    else:
        print("Error: --build-dir is required (or use deprecated --docs-base-dir)")
        sys.exit(1)

    # CLI LLM overrides: inject into registry
    if args.llm_url or args.llm_model or args.llm_key:
        llm_name = cfg.enrich_models[0] if cfg.enrich_models else "cli-llm"
        try:
            entry = dict(cfg.get_llm(llm_name))
        except KeyError:
            entry = {"name": llm_name}
        if args.llm_url:
            entry["api_url"] = args.llm_url
        if args.llm_model:
            entry["model"] = args.llm_model
        if args.llm_key:
            entry["api_key"] = args.llm_key
        cfg.llm_registry = [e if e.get("name") != llm_name else entry
                            for e in cfg.llm_registry]
        if not any(e.get("name") == llm_name for e in cfg.llm_registry):
            cfg.llm_registry.append(entry)
        if not cfg.enrich_models:
            cfg.enrich_models = [llm_name]

    recipe_path = args.recipe
    if not recipe_path:
        from lore_mcp.recipe import scan_directory
        import yaml as _yaml
        if _build_dir:
            scan_base = cfg.orig_dir
            out_base = _build_dir
        else:
            scan_base = str(Path(docs_base_dir) / cfg.preprocess_orig_dir)
            out_base = str(Path(docs_base_dir) / cfg.preprocess_prep_dir)
        scanned = scan_directory(scan_base)
        Path(out_base).mkdir(parents=True, exist_ok=True)
        recipe_path = str(Path(out_base) / "generated-recipe.yaml")
        Path(recipe_path).write_text(
            _yaml.dump(scanned, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"  Generated recipe: {recipe_path} ({len(scanned['sources'])} sources)")

    reports = preprocess_sources(recipe_path, docs_base_dir, cfg)

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
    _build_dir = getattr(args, "build_dir", None)
    if _build_dir:
        prep_dir = Path(_build_dir) / "prep"
    elif args.prep_dir:
        prep_dir = Path(args.prep_dir) if Path(args.prep_dir).is_absolute() else Path(args.docs_base_dir or ".") / args.prep_dir
    else:
        prep_dir = Path(".")
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
    from lore_mcp.recipe import parse_recipe
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

    recipe = parse_recipe(args.recipe)
    docs_dir = Path(args.docs_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for source in recipe["sources"]:
        path = source.get("path", source.get("file", ""))
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
