"""Ingestion pipeline: preprocessing, chunking, indexing. See docs/architecture.md."""

import hashlib
import logging
import os
from pathlib import Path

from langchain_text_splitters import MarkdownTextSplitter

from lore_mcp.collections import collection_db_path
from lore_mcp.embedder import Embedder
from lore_mcp.manifest import extract_source_metadata, parse_manifest
from lore_mcp.preprocess import clean_text
from lore_mcp.store import (
    create_tables,
    insert_chunks,
    insert_parent_chunk,
    open_db,
    upsert_source,
    validate_model,
)

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 128
EMBED_BATCH_SIZE = 64
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


def get_chunk_config(config=None) -> tuple[int, int]:
    """Read chunk_size and overlap from config or use defaults."""
    if config:
        return config.chunk_size, config.chunk_overlap
    return DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP


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
    """Split text into chunks with deterministic IDs."""
    splitter = MarkdownTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    parts = splitter.split_text(text)
    chunks = []
    for i, part in enumerate(parts):
        chunk_id = hashlib.sha256(
            f"{source_file}:{i}:{part[:64]}".encode()
        ).hexdigest()[:16]
        chunks.append({
            "id": chunk_id,
            "source_file": source_file,
            "chunk_index": i,
            "content": part,
        })
    return chunks


DEFAULT_PARENT_SIZE = 2048


def chunk_document_parent_child(
    text: str,
    source_file: str,
    parent_size: int = DEFAULT_PARENT_SIZE,
    child_size: int = DEFAULT_CHUNK_SIZE,
    child_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[list[dict], list[dict]]:
    """Split text into parent chunks, then each parent into child chunks.

    Returns (parent_chunks, child_chunks). Each child has a 'parent_index'
    key referencing its parent's position in the parent_chunks list.
    """
    parent_splitter = MarkdownTextSplitter(
        chunk_size=parent_size,
        chunk_overlap=0,
    )
    child_splitter = MarkdownTextSplitter(
        chunk_size=child_size,
        chunk_overlap=child_overlap,
    )

    parent_texts = parent_splitter.split_text(text)
    parent_chunks = []
    child_chunks = []
    child_index = 0

    for pi, parent_text in enumerate(parent_texts):
        parent_chunks.append({
            "source_file": source_file,
            "content": parent_text,
        })
        child_texts = child_splitter.split_text(parent_text)
        for child_text in child_texts:
            chunk_id = hashlib.sha256(
                f"{source_file}:pc:{child_index}:{child_text[:64]}".encode()
            ).hexdigest()[:16]
            child_chunks.append({
                "id": chunk_id,
                "source_file": source_file,
                "chunk_index": child_index,
                "content": child_text,
                "parent_index": pi,
            })
            child_index += 1

    return parent_chunks, child_chunks


def _ingest_file(
    db, md_file: Path, rel: str, embedder: Embedder,
    chunk_size: int, chunk_overlap: int,
    source_meta: dict | None = None,
) -> int:
    """Ingest a single file. Returns chunk count."""
    text = md_file.read_text(encoding="utf-8")
    raw_text = text
    text = clean_text(text)
    if len(text.strip()) < MIN_DOC_LENGTH:
        return 0

    _SOURCE_FIELDS = {"title", "author", "url", "date", "license", "level"}
    if source_meta:
        upsert_source(db, rel, **{k: v for k, v in source_meta.items() if k in _SOURCE_FIELDS})
    else:
        meta = extract_source_metadata(raw_text, rel)
        upsert_source(db, rel, **meta)

    if source_meta:
        chunk_size = source_meta.get("chunk_size", chunk_size)
        chunk_overlap = source_meta.get("chunk_overlap", chunk_overlap)

    chunking_mode = source_meta.get("chunking_mode", "standard") if source_meta else "standard"
    batch_size = get_batch_size()

    if chunking_mode == "parent-child":
        parent_size = source_meta.get("parent_size", DEFAULT_PARENT_SIZE) if source_meta else DEFAULT_PARENT_SIZE
        parent_chunks, child_chunks = chunk_document_parent_child(
            text, rel, parent_size, chunk_size, chunk_overlap
        )
        parent_ids = []
        for pc in parent_chunks:
            pid = insert_parent_chunk(db, pc["source_file"], pc["content"])
            parent_ids.append(pid)
        for cc in child_chunks:
            cc["parent_id"] = parent_ids[cc.pop("parent_index")]
        for batch_start in range(0, len(child_chunks), batch_size):
            batch = child_chunks[batch_start : batch_start + batch_size]
            texts = [c["content"] for c in batch]
            embeddings = embedder.embed_batch(texts)
            insert_chunks(db, batch, embeddings)
        return len(child_chunks)
    else:
        chunks = chunk_document(text, rel, chunk_size, chunk_overlap)
        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            texts = [c["content"] for c in batch]
            embeddings = embedder.embed_batch(texts)
            insert_chunks(db, batch, embeddings)
        return len(chunks)


def ingest_directory(
    dir_path: str,
    db_path: str,
    embedder: Embedder,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    collection: str | None = None,
    db_dir: str | None = None,
) -> dict:
    """Index a directory of Markdown/text files into the store.

    Extracts source metadata from front matter when no manifest is used.
    Returns a summary dict with file_count, chunk_count, and errors.
    """
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
    manifest_path: str,
    docs_dir: str,
    db_dir: str,
    embedder: Embedder,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> dict:
    """Index files listed in a YAML manifest into a named collection.

    The manifest specifies the collection name, level, and per-source
    bibliographic metadata.
    """
    manifest = parse_manifest(manifest_path)
    collection = manifest["collection"]
    level = manifest.get("level", "")

    db_path = collection_db_path(db_dir, collection)
    db = open_db(db_path)
    create_tables(db, embedder.model_name, embedder.model_dim,
                   chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    validate_model(db, embedder.model_name, embedder.model_dim)

    docs_path = Path(docs_dir)
    file_count = 0
    chunk_count = 0
    errors = []

    for source_entry in manifest["sources"]:
        src_path = source_entry["path"]
        md_file = docs_path / src_path
        if not md_file.exists():
            errors.append({"file": src_path, "error": "File not found"})
            continue
        try:
            logger.debug("━━━ Indexing %s ━━━", src_path)
            source_meta = {k: v for k, v in source_entry.items()}
            source_meta.setdefault("level", level)
            n = _ingest_file(db, md_file, src_path, embedder,
                             chunk_size, chunk_overlap, source_meta=source_meta)
            if n > 0:
                file_count += 1
                chunk_count += n
                logger.info("%s: %d chunks", src_path, n)
        except Exception as e:
            errors.append({"file": src_path, "error": str(e)})
            logger.error("Failed to index %s: %s", src_path, e)

    db.close()
    return {"file_count": file_count, "chunk_count": chunk_count, "errors": errors}
