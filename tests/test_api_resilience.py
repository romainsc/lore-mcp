"""Tests for E10.18: embedding API resilience."""

import time
from unittest.mock import MagicMock, patch

import pytest

from lore_mcp.embedder import Embedder


class MockResponse:
    def __init__(self, status_code, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=MagicMock(), response=self
            )


def _make_api_embedder():
    return Embedder(
        model_name="test", mode="api",
        api_url="http://localhost:8081/v1/embeddings"
    )


class TestRetryOnTransientErrors:
    """MVP1: retry with backoff on 429/500/503."""

    def test_retry_on_429(self):
        from lore_mcp.embedder import _embed_api_with_retry
        emb = _make_api_embedder()
        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                return MockResponse(429, headers={"Retry-After": "0"})
            return MockResponse(200, {"data": [{"embedding": [0.1] * 8}]})

        with patch("httpx.post", side_effect=mock_post):
            result = _embed_api_with_retry(emb, ["test"])
            assert len(result) == 1
            assert call_count[0] == 3

    def test_retry_on_500(self):
        from lore_mcp.embedder import _embed_api_with_retry
        emb = _make_api_embedder()
        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                return MockResponse(500)
            return MockResponse(200, {"data": [{"embedding": [0.1] * 8}]})

        with patch("httpx.post", side_effect=mock_post):
            result = _embed_api_with_retry(emb, ["test"])
            assert call_count[0] == 2

    def test_exhaust_retries_raises(self):
        from lore_mcp.embedder import _embed_api_with_retry, EmbeddingAPIError
        emb = _make_api_embedder()

        def mock_post(*args, **kwargs):
            return MockResponse(500)

        with patch("httpx.post", side_effect=mock_post):
            with pytest.raises(EmbeddingAPIError):
                _embed_api_with_retry(emb, ["test"], max_retries=2)


class TestBatchReduction:
    """MVP2: halve batch on 422."""

    def test_reduce_batch_on_422(self):
        from lore_mcp.embedder import _embed_api_with_retry
        emb = _make_api_embedder()
        batch_sizes_seen = []

        def mock_post(*args, **kwargs):
            data = kwargs.get("json", args[1] if len(args) > 1 else {})
            batch_size = len(data.get("input", []))
            batch_sizes_seen.append(batch_size)
            if batch_size > 2:
                return MockResponse(422)
            return MockResponse(200, {
                "data": [{"embedding": [0.1] * 8} for _ in range(batch_size)]
            })

        with patch("httpx.post", side_effect=mock_post):
            result = _embed_api_with_retry(emb, ["a", "b", "c", "d"])
            assert len(result) == 4
            assert max(batch_sizes_seen) == 4
            assert min(batch_sizes_seen) <= 2


class TestFailFast:
    """MVP3: fail fast on 401/404."""

    def test_fail_fast_401(self):
        from lore_mcp.embedder import _embed_api_with_retry, EmbeddingAPIError
        emb = _make_api_embedder()

        def mock_post(*args, **kwargs):
            return MockResponse(401)

        with patch("httpx.post", side_effect=mock_post):
            with pytest.raises(EmbeddingAPIError, match="401"):
                _embed_api_with_retry(emb, ["test"])

    def test_fail_fast_404(self):
        from lore_mcp.embedder import _embed_api_with_retry, EmbeddingAPIError
        emb = _make_api_embedder()

        def mock_post(*args, **kwargs):
            return MockResponse(404)

        with patch("httpx.post", side_effect=mock_post):
            with pytest.raises(EmbeddingAPIError, match="404"):
                _embed_api_with_retry(emb, ["test"])

    def test_no_retry_on_401(self):
        from lore_mcp.embedder import _embed_api_with_retry, EmbeddingAPIError
        emb = _make_api_embedder()
        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            return MockResponse(401)

        with patch("httpx.post", side_effect=mock_post):
            with pytest.raises(EmbeddingAPIError):
                _embed_api_with_retry(emb, ["test"])
            assert call_count[0] == 1


class TestConsecutiveErrorThreshold:
    """MVP3: stop build after N consecutive failures."""

    def test_threshold_raises(self):
        from lore_mcp.ingest import ConsecutiveErrorThreshold
        threshold = ConsecutiveErrorThreshold(max_consecutive=3)
        threshold.record_error("file1.md", "err")
        threshold.record_error("file2.md", "err")
        with pytest.raises(RuntimeError, match="consecutive"):
            threshold.record_error("file3.md", "err")

    def test_success_resets_counter(self):
        from lore_mcp.ingest import ConsecutiveErrorThreshold
        threshold = ConsecutiveErrorThreshold(max_consecutive=3)
        threshold.record_error("file1.md", "err")
        threshold.record_error("file2.md", "err")
        threshold.record_success()
        threshold.record_error("file3.md", "err")
        threshold.record_error("file4.md", "err")
        # No raise — counter was reset by success
