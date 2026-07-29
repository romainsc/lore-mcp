#!/usr/bin/env python3
"""Index le corpus Red Hat MD dans pgvector.

Chunking récursif (1024/128) + embedding bge-m3
(GPU via vLLM ou CPU via sentence-transformers)
+ insertion dans pgvector.

Usage :
  python3 claude/scripts/index-corpus.py
  python3 claude/scripts/index-corpus.py --cpu
  python3 claude/scripts/index-corpus.py \
    --docs ~/CHANGE_ME_PATH/RedHat-md/ \
    --pg-host CHANGE_ME_HOST --pg-port 30432
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import psycopg2
import requests
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)

CHUNK_SIZE = 2048
CHUNK_OVERLAP = 128
EMBED_DIM = 1024
EMBED_BATCH = 64
VLLM_URL = (
    "https://bge-m3-autorag-ai-serving"
    ".CHANGE_ME_DOMAIN/v1/embeddings"
)
VLLM_MODEL = "BAAI/bge-m3-embedding"
PG_DEFAULTS = {
    "host": "CHANGE_ME_HOST",
    "port": 30432,
    "user": "llamastack",
    "dbname": "llamastack",
    "password": "CHANGE_ME_PASSWORD",
}


def strip_base64(text):
    text = text.replace("\x00", "")
    return "\n".join(
        l for l in text.split("\n")
        if "base64," not in l
    )


def chunk_document(text, source_file):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n## ", "\n### ", "\n#### ",
            "\n\n", "\n", " ", "",
        ],
    )
    chunks = splitter.split_text(text)
    results = []
    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.sha256(
            f"{source_file}:{i}:{chunk[:64]}".encode()
        ).hexdigest()[:16]
        results.append({
            "id": chunk_id,
            "source_file": source_file,
            "chunk_index": i,
            "content": chunk,
        })
    return results


def embed_gpu(texts):
    resp = requests.post(
        VLLM_URL,
        json={"model": VLLM_MODEL, "input": texts},
        verify=False,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    return [d["embedding"] for d in data]


def embed_cpu(texts, model):
    return model.encode(
        texts, normalize_embeddings=True
    ).tolist()


def insert_chunks(conn, chunks, embeddings):
    cur = conn.cursor()
    for chunk, emb in zip(chunks, embeddings):
        cur.execute(
            "INSERT INTO rag_chunks "
            "(id, source_file, chunk_index, "
            "content, embedding) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (
                chunk["id"],
                chunk["source_file"],
                chunk["chunk_index"],
                chunk["content"],
                json.dumps(emb),
            ),
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Index Red Hat MD corpus"
    )
    parser.add_argument(
        "--docs",
        default=os.path.expanduser(
            "~/CHANGE_ME_PATH/RedHat-md/"
        ),
    )
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument(
        "--pg-host", default=PG_DEFAULTS["host"]
    )
    parser.add_argument(
        "--pg-port",
        type=int,
        default=PG_DEFAULTS["port"],
    )
    args = parser.parse_args()

    cpu_model = None
    if args.cpu:
        from sentence_transformers import (
            SentenceTransformer,
        )
        print("Loading bge-m3 on CPU...")
        cpu_model = SentenceTransformer("BAAI/bge-m3")
        print("Model loaded.")
        embed_fn = lambda texts: embed_cpu(
            texts, cpu_model
        )
    else:
        print(f"Using GPU: {VLLM_URL}")
        try:
            embed_gpu(["test"])
            print("GPU embedding OK.")
        except Exception as e:
            print(f"GPU unavailable: {e}")
            print("Use --cpu for local embedding.")
            sys.exit(1)
        embed_fn = embed_gpu

    pg = {**PG_DEFAULTS}
    pg["host"] = args.pg_host
    pg["port"] = args.pg_port
    conn = psycopg2.connect(**pg)
    print(f"pgvector: {pg['host']}:{pg['port']}")

    docs_path = Path(args.docs)
    md_files = sorted(docs_path.rglob("*.md"))
    print(f"Documents: {len(md_files)}")

    total_chunks = 0
    total_inserted = 0
    t0 = time.time()

    for i, md_file in enumerate(md_files):
        rel = md_file.relative_to(docs_path)
        text = md_file.read_text(encoding="utf-8")
        text = strip_base64(text)

        if len(text.strip()) < 100:
            continue

        chunks = chunk_document(text, str(rel))
        total_chunks += len(chunks)

        for batch_start in range(
            0, len(chunks), EMBED_BATCH
        ):
            batch = chunks[
                batch_start:batch_start + EMBED_BATCH
            ]
            texts = [c["content"] for c in batch]
            embeddings = embed_fn(texts)
            insert_chunks(conn, batch, embeddings)
            total_inserted += len(batch)

        elapsed = time.time() - t0
        rate = total_inserted / elapsed if elapsed else 0
        print(
            f"[{i+1}/{len(md_files)}] {rel}: "
            f"{len(chunks)} chunks "
            f"({total_inserted} total, "
            f"{rate:.0f} chunks/s)"
        )

    conn.close()
    elapsed = time.time() - t0
    print(
        f"\nDone: {total_inserted} chunks "
        f"from {len(md_files)} docs "
        f"in {elapsed:.0f}s"
    )


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    main()
