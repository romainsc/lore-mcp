-- Table RAG pour le corpus Red Hat
-- E1.04 : indexation des 194 documents MD
--
-- Utilise pgvector 0.8.3 avec HNSW cosine.
-- Config issue d'AutoRAG E1.08 : bge-m3 1024d.
--
-- Usage :
--   psql -h CHANGE_ME_HOST -p 30432 \
--     -U llamastack -d llamastack \
--     -f claude/scripts/create-rag-table.sql

CREATE TABLE IF NOT EXISTS rag_chunks (
  id TEXT PRIMARY KEY,
  source_file TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1024) NOT NULL,
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
  ON rag_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS rag_chunks_source_idx
  ON rag_chunks (source_file);
