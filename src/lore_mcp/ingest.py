"""Ingestion pipeline: preprocessing, chunking, indexing. See docs/architecture.md."""

import hashlib
import json
import logging
import os
from pathlib import Path

from lore_mcp.collections import collection_db_path
from lore_mcp.embedder import Embedder
from lore_mcp.recipe import extract_source_metadata, parse_recipe
from lore_mcp.preprocess import clean_text
from lore_mcp.store import (
    create_tables,
    delete_source_chunks,
    get_source_hashes,
    insert_chunks,
    open_db,
    set_source_hash,
    upsert_source,
    validate_model,
)

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 128
EMBED_BATCH_SIZE = 32
MIN_DOC_LENGTH = 100


class ConsecutiveErrorThreshold:
    """Stop build if too many consecutive files fail."""

    def __init__(self, max_consecutive: int = 3):
        self.max_consecutive = max_consecutive
        self._count = 0
        self.errors: list[dict] = []

    def record_error(self, file: str, error: str) -> None:
        self._count += 1
        self.errors.append({"file": file, "error": error})
        if self._count >= self.max_consecutive:
            raise RuntimeError(
                f"{self._count} consecutive embedding failures — "
                f"likely systemic problem. Stopping."
            )

    def record_success(self) -> None:
        self._count = 0


def get_batch_size(config=None) -> int:
    """Read embedding batch size from config or use default."""
    if config:
        return config.embedding_batch_size
    return EMBED_BATCH_SIZE


def chunk_document(
    text: str,
    source_file: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Split text into chunks via Docling HybridChunker.

    Loads markdown into Docling Markdown backend to get a structured
    DoclingDocument, then chunks with HybridChunker which preserves
    table boundaries and heading context.
    """
    import tempfile

    from docling.document_converter import DocumentConverter
    from docling_core.transforms.chunker import HybridChunker

    max_tokens = max(chunk_size // 4, 64)

    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(text)
        tmp_path = f.name

    try:
        import warnings
        converter = DocumentConverter()
        doc = converter.convert(tmp_path).document
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning,
                                    module="docling_core")
            chunker = HybridChunker(max_tokens=max_tokens)
        doc_chunks = list(chunker.chunk(doc))
    finally:
        os.unlink(tmp_path)

    chunks = []
    for i, c in enumerate(doc_chunks):
        headings = c.meta.headings if c.meta and c.meta.headings else []
        chunk_id = hashlib.sha256(
            f"{source_file}:{i}:{c.text[:64]}".encode()
        ).hexdigest()[:16]
        chunks.append({
            "id": chunk_id,
            "source_file": source_file,
            "chunk_index": i,
            "content": c.text,
            "metadata": json.dumps({"headings": headings}),
        })
    return chunks


def _ingest_file(
    db, md_file: Path, rel: str, embedder: Embedder,
    chunk_size: int, chunk_overlap: int,
    source_meta: dict | None = None,
) -> int:
    """Ingest a single file. Returns chunk count."""
    text = md_file.read_text(encoding="utf-8", errors="replace")
    raw_text = text
    text = clean_text(text)
    if len(text.strip()) < MIN_DOC_LENGTH:
        return 0

    _SOURCE_FIELDS = {"title", "author", "url", "date", "license", "level", "lang"}
    if source_meta:
        upsert_source(db, rel, **{k: v for k, v in source_meta.items() if k in _SOURCE_FIELDS})
    else:
        meta = extract_source_metadata(raw_text, rel)
        upsert_source(db, rel, **meta)

    if source_meta:
        chunk_size = source_meta.get("chunk_size", chunk_size)
        chunk_overlap = source_meta.get("chunk_overlap", chunk_overlap)

    batch_size = embedder.api_batch_size or get_batch_size()

    chunks = chunk_document(text, rel, chunk_size, chunk_overlap)
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        texts = [c["content"] for c in batch]
        embeddings = embedder.embed_batch(texts)
        insert_chunks(db, batch, embeddings)
    return len(chunks)


def ingest_source(
    db_path: str,
    md_file: Path,
    embedder: Embedder,
    source_meta: dict | None = None,
    db=None,
) -> dict:
    """Add a single source to an existing .db. See docs/studies/grooming-E3.14.md."""
    owns_db = db is None
    if owns_db:
        db = open_db(db_path)
    validate_model(db, embedder.model_name, embedder.model_dim)

    meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    chunk_size = int(meta.get("chunk_size", DEFAULT_CHUNK_SIZE))
    chunk_overlap = int(meta.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP))

    rel = md_file.name
    delete_source_chunks(db, rel)

    n = _ingest_file(db, md_file, rel, embedder,
                     chunk_size, chunk_overlap, source_meta)
    if owns_db:
        db.close()
    return {"file_count": 1 if n > 0 else 0, "chunk_count": n}


def ingest_directory(
    dir_path: str,
    db_path: str,
    embedder: Embedder,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    collection: str | None = None,
    db_dir: str | None = None,
) -> dict:
    """Index a directory of Markdown/text files into the store."""
    if collection and db_dir:
        db_path = collection_db_path(db_dir, collection)
    db = open_db(db_path)
    create_tables(db, embedder.model_name, embedder.model_dim,
                   chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    validate_model(db, embedder.model_name, embedder.model_dim)

    docs_path = Path(dir_path)
    md_files = sorted(docs_path.rglob("*.md"))
    file_count = 0
    chunk_count = 0
    threshold = ConsecutiveErrorThreshold()

    for md_file in md_files:
        try:
            rel = str(md_file.relative_to(docs_path))
            logger.debug("━━━ Indexing %s ━━━", rel)
            n = _ingest_file(db, md_file, rel, embedder, chunk_size, chunk_overlap)
            if n > 0:
                file_count += 1
                chunk_count += n
                threshold.record_success()
                logger.info("%s: %d chunks", rel, n)
        except Exception as e:
            threshold.record_error(str(md_file), str(e))
            logger.error("Failed to index %s: %s", md_file, e)

    db.close()
    return {"file_count": file_count, "chunk_count": chunk_count, "errors": threshold.errors}


def ingest_with_manifest(
    recipe_path: str,
    docs_dir: str,
    db_dir: str,
    embedder: Embedder,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    purge_absent: bool = True,
    collection: str = "",
) -> dict:
    """Index files listed in a YAML recipe into a named collection."""
    recipe = parse_recipe(recipe_path)
    collection = collection or recipe["collection"]
    level = recipe.get("level", "")

    db_path = collection_db_path(db_dir, collection)
    db = open_db(db_path)
    create_tables(db, embedder.model_name, embedder.model_dim,
                   chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    validate_model(db, embedder.model_name, embedder.model_dim)

    docs_path = Path(docs_dir)
    file_count = 0
    chunk_count = 0
    errors = []
    skipped = 0
    updated = 0
    purged = 0

    existing_hashes = get_source_hashes(db)
    recipe_paths = set()

    for source_entry in recipe["sources"]:
        src_path = source_entry.get("path") or source_entry.get("file", "")
        if not src_path:
            errors.append({"file": str(source_entry), "error": "No path or file field"})
            continue
        recipe_paths.add(src_path)
        md_file = docs_path / src_path
        if not md_file.exists():
            errors.append({"file": src_path, "error": "File not found"})
            continue

        content = md_file.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        if src_path in existing_hashes:
            if existing_hashes[src_path] == content_hash:
                skipped += 1
                logger.debug("Skip (unchanged): %s", src_path)
                continue
            else:
                delete_source_chunks(db, src_path)
                updated += 1
                logger.info("Update (changed): %s", src_path)

        try:
            logger.debug("━━━ Indexing %s ━━━", src_path)
            source_meta = {k: v for k, v in source_entry.items()}
            source_meta.setdefault("level", level)
            n = _ingest_file(db, md_file, src_path, embedder,
                             chunk_size, chunk_overlap, source_meta=source_meta)
            if n > 0:
                file_count += 1
                chunk_count += n
                set_source_hash(db, src_path, content_hash)
                logger.info("%s: %d chunks", src_path, n)
        except Exception as e:
            errors.append({"file": src_path, "error": str(e)})
            logger.error("Failed to index %s: %s", src_path, e)

    if purge_absent:
        for old_source in list(existing_hashes.keys()):
            if old_source not in recipe_paths:
                delete_source_chunks(db, old_source)
                purged += 1
                logger.info("Purge (absent from recipe): %s", old_source)

    db.close()
    return {
        "file_count": file_count, "chunk_count": chunk_count,
        "errors": errors, "skipped": skipped, "updated": updated,
        "purged": purged,
    }
