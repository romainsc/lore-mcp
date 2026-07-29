"""Tests for lore_mcp.ingest. See docs/architecture.md for design context."""

import pytest

from lore_mcp.ingest import chunk_document, preprocess


class TestPreprocess:
    def test_strips_nul(self):
        assert preprocess("hello\x00world") == "helloworld"

    def test_strips_base64_lines(self):
        text = "line 1\n![img](data:image/png;base64,iVBOR...)\nline 3"
        result = preprocess(text)
        assert "base64" not in result
        assert "line 1" in result
        assert "line 3" in result

    def test_preserves_normal_text(self):
        text = "This is normal\nMarkdown content.\n\n## Heading\n"
        assert preprocess(text) == text

    def test_empty_input(self):
        assert preprocess("") == ""


class TestChunkDocument:
    def test_produces_chunks(self):
        text = "word " * 1000
        chunks = chunk_document(text, "test.md")
        assert len(chunks) > 1

    def test_chunk_has_required_fields(self):
        text = "word " * 1000
        chunks = chunk_document(text, "test.md")
        for c in chunks:
            assert "id" in c
            assert "source_file" in c
            assert "chunk_index" in c
            assert "content" in c

    def test_source_file_set(self):
        text = "word " * 1000
        chunks = chunk_document(text, "docs/intro.md")
        assert all(c["source_file"] == "docs/intro.md" for c in chunks)

    def test_chunk_index_sequential(self):
        text = "word " * 1000
        chunks = chunk_document(text, "test.md")
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_deterministic_ids(self):
        text = "word " * 1000
        chunks_a = chunk_document(text, "test.md")
        chunks_b = chunk_document(text, "test.md")
        assert [c["id"] for c in chunks_a] == [c["id"] for c in chunks_b]

    def test_small_document_single_chunk(self):
        text = "Short document."
        chunks = chunk_document(text, "small.md")
        assert len(chunks) == 1

    def test_custom_chunk_size(self):
        text = "word " * 500
        small = chunk_document(text, "f.md", chunk_size=256, chunk_overlap=32)
        big = chunk_document(text, "f.md", chunk_size=2048, chunk_overlap=128)
        assert len(small) > len(big)

    def test_respects_markdown_separators(self):
        text = "# Title\n\nParagraph one.\n\n## Section\n\nParagraph two.\n"
        chunks = chunk_document(text, "f.md", chunk_size=50, chunk_overlap=0)
        assert len(chunks) >= 2
