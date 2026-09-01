"""Ingestion pipeline: preprocessing, chunking, indexing. See docs/architecture.md."""

import hashlib
import logging
import os
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from lore_mcp.collections import collection_db_path
from lore_mcp.embedder import Embedder
from lore_mcp.manifest import extract_source_metadata, parse_manifest
from lore_mcp.store import (
    create_tables,
    insert_chunks,
    open_db,
    upsert_source,
    validate_model,
)

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 128
EMBED_BATCH_SIZE = 64
MIN_DOC_LENGTH = 100

MD_SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]


def get_chunk_config() -> tuple[int, int]:
    """Read chunk_size and overlap from env vars or use defaults."""
    size = int(os.environ.get("LORE_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE)))
    overlap = int(os.environ.get("LORE_CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP)))
    return size, overlap


def get_batch_size() -> int:
    """Read embedding batch size from env var or use default."""
    return int(os.environ.get("LORE_BATCH_SIZE", str(EMBED_BATCH_SIZE)))


def preprocess(text: str) -> str:
    """Strip NUL characters and base64 image data lines."""
    text = text.replace("\x00", "")
    return "\n".join(
        line for line in text.split("\n") if "base64," not in line
    )


def chunk_document(
    text: str,
    source_file: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Split text into chunks with deterministic IDs."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=MD_SEPARATORS,
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


def _ingest_file(
    db, md_file: Path, rel: str, embedder: Embedder,
    chunk_size: int, chunk_overlap: int,
    source_meta: dict | None = None,
) -> int:
    """Ingest a single file. Returns chunk count."""
    text = md_file.read_text(encoding="utf-8")
    raw_text = text
    text = preprocess(text)
    if len(text.strip()) < MIN_DOC_LENGTH:
        return 0

    if source_meta:
        upsert_source(db, rel, **{k: v for k, v in source_meta.items() if k != "path"})
    else:
        meta = extract_source_metadata(raw_text, rel)
        upsert_source(db, rel, **meta)

    batch_size = get_batch_size()
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
    errors = []

    for md_file in md_files:
        try:
            rel = str(md_file.relative_to(docs_path))
            n = _ingest_file(db, md_file, rel, embedder, chunk_size, chunk_overlap)
            if n > 0:
                file_count += 1
                chunk_count += n
                logger.info("%s: %d chunks", rel, n)
        except Exception as e:
            errors.append({"file": str(md_file), "error": str(e)})
            logger.error("Failed to index %s: %s", md_file, e)

    db.close()
    return {"file_count": file_count, "chunk_count": chunk_count, "errors": errors}


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
