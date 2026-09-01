"""Tests for E10.17 rev: smart batch size management."""

from unittest.mock import MagicMock, patch

import pytest

from lore_mcp.embedder import Embedder


def _make_api_embedder(batch_size=None):
    emb = Embedder(
        model_name="test", mode="api",
        api_url="http://localhost:8081/v1/embeddings",
    )
    if batch_size:
        emb.api_batch_size = batch_size
    return emb


class MockResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = {}

    def json(self):
        return self._json


class TestConfigBatchSize:
    def test_batch_size_from_config(self, tmp_path):
        """batch_size in YAML config is read per model."""
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "config.yaml"
        f.write_text("""
embedding:
  - name: model-a
    mode: api
    api_url: http://localhost:8081/v1/embeddings
    batch_size: 32
  - name: model-b
    mode: api
    api_url: http://localhost:8082/v1/embeddings
""")
        configs = parse_model_configs(str(f))
        assert configs[0].get("batch_size") == 32
        assert configs[1].get("batch_size") is None

    def test_embedder_stores_batch_size(self):
        emb = _make_api_embedder(batch_size=32)
        assert emb.api_batch_size == 32

    def test_embedder_default_batch_size(self):
        emb = _make_api_embedder()
        assert emb.api_batch_size is None


class TestSmartReduction:
    def test_finds_max_batch_size(self):
        """On 422, find the max accepted size (server accepts ≤16)."""
        from lore_mcp.embedder import _embed_api_with_retry
        emb = _make_api_embedder()
        server_max = 16

        def mock_post(*args, **kwargs):
            data = kwargs.get("json", {})
            batch = len(data.get("input", []))
            if batch > server_max:
                return MockResponse(422)
            return MockResponse(200, {
                "data": [{"embedding": [0.1] * 8} for _ in range(batch)]
            })

        with patch("httpx.post", side_effect=mock_post):
            result = _embed_api_with_retry(emb, [f"text{i}" for i in range(32)])
            assert len(result) == 32
            assert emb.api_batch_size == server_max

    def test_memoized_for_subsequent_calls(self):
        """Once discovered, the max is reused."""
        from lore_mcp.embedder import _embed_api_with_retry
        emb = _make_api_embedder()
        server_max = 8
        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            data = kwargs.get("json", {})
            batch = len(data.get("input", []))
            if batch > server_max:
                return MockResponse(422)
            return MockResponse(200, {
                "data": [{"embedding": [0.1] * 8} for _ in range(batch)]
            })

        with patch("httpx.post", side_effect=mock_post):
            _embed_api_with_retry(emb, [f"a{i}" for i in range(20)])
            first_calls = call_count[0]

            _embed_api_with_retry(emb, [f"b{i}" for i in range(20)])
            second_calls = call_count[0] - first_calls

        # Second run should have no 422s (batch already correct)
        assert emb.api_batch_size == server_max

    def test_config_batch_size_prevents_422(self):
        """Pre-configured batch_size avoids any 422."""
        from lore_mcp.embedder import _embed_api_with_retry
        emb = _make_api_embedder(batch_size=8)
        server_max = 8

        def mock_post(*args, **kwargs):
            data = kwargs.get("json", {})
            batch = len(data.get("input", []))
            if batch > server_max:
                return MockResponse(422)
            return MockResponse(200, {
                "data": [{"embedding": [0.1] * 8} for _ in range(batch)]
            })

        with patch("httpx.post", side_effect=mock_post):
            result = _embed_api_with_retry(emb, [f"text{i}" for i in range(20)])
            assert len(result) == 20
