"""Tests for lore_mcp.embedder. See docs/architecture.md for design context."""

from unittest.mock import MagicMock, patch

import pytest

from lore_mcp.embedder import Embedder, assess_gpu, assess_cpu


DIMS = 1024
MODEL = "BAAI/bge-m3"


class TestAssessGpu:
    @patch("lore_mcp.embedder.torch")
    def test_no_cuda(self, mock_torch):
        mock_torch.cuda.is_available.return_value = False
        result = assess_gpu()
        assert result["available"] is False

    @patch("lore_mcp.embedder.torch")
    def test_enough_vram_fp32(self, mock_torch):
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.mem_get_info.return_value = (4 * 1024**3, 6 * 1024**3)
        mock_torch.cuda.get_device_capability.return_value = (8, 9)
        mock_torch.cuda.get_device_name.return_value = "Test GPU"
        result = assess_gpu()
        assert result["available"] is True
        assert result["recommended_dtype"] == "float32"

    @patch("lore_mcp.embedder.torch")
    def test_enough_vram_fp16_only(self, mock_torch):
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.mem_get_info.return_value = (int(1.8 * 1024**3), 4 * 1024**3)
        mock_torch.cuda.get_device_capability.return_value = (7, 5)
        mock_torch.cuda.get_device_name.return_value = "Test GPU"
        result = assess_gpu()
        assert result["available"] is True
        assert result["recommended_dtype"] == "float16"

    @patch("lore_mcp.embedder.torch")
    def test_not_enough_vram(self, mock_torch):
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.mem_get_info.return_value = (500 * 1024**2, 2 * 1024**3)
        mock_torch.cuda.get_device_capability.return_value = (7, 5)
        mock_torch.cuda.get_device_name.return_value = "Test GPU"
        result = assess_gpu()
        assert result["available"] is False
        assert "free" in result["message"].lower() or "vram" in result["message"].lower()

    @patch("lore_mcp.embedder.torch", None)
    def test_no_torch(self):
        result = assess_gpu()
        assert result["available"] is False


class TestAssessCpu:
    def test_returns_availability(self):
        result = assess_cpu()
        assert "available" in result
        assert "ram_available_gb" in result

    def test_reports_ram(self):
        result = assess_cpu()
        assert result["ram_available_gb"] > 0


class TestEmbedderInit:
    def test_default_mode_is_auto(self):
        emb = Embedder()
        assert emb.mode == "auto"

    def test_custom_model(self):
        emb = Embedder(model_name="custom/model")
        assert emb.model_name == "custom/model"

    def test_api_mode_without_url_raises(self):
        with pytest.raises(ValueError, match="LORE_API_URL"):
            Embedder(mode="api")

    def test_api_mode_with_url(self):
        emb = Embedder(mode="api", api_url="http://localhost:8000/v1/embeddings")
        assert emb.mode == "api"


class TestEmbedderEmbed:
    def _make_embedder_with_mock_model(self):
        emb = Embedder(mode="cpu")
        mock_model = MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.random.randn(DIMS).astype("float32")
        mock_model.get_sentence_embedding_dimension.return_value = DIMS
        emb._model = mock_model
        return emb

    def test_returns_list_of_floats(self):
        emb = self._make_embedder_with_mock_model()
        result = emb.embed("hello")
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_correct_dimension(self):
        emb = self._make_embedder_with_mock_model()
        result = emb.embed("hello")
        assert len(result) == DIMS

    def test_normalized(self):
        emb = self._make_embedder_with_mock_model()
        mock_model = emb._model
        import numpy as np
        vec = np.random.randn(DIMS).astype("float32")
        vec = vec / np.linalg.norm(vec)
        mock_model.encode.return_value = vec
        result = emb.embed("hello")
        norm = sum(x**2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 0.01


class TestEmbedderEmbedBatch:
    def test_returns_list_of_lists(self):
        emb = Embedder(mode="cpu")
        mock_model = MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.random.randn(3, DIMS).astype("float32")
        mock_model.get_sentence_embedding_dimension.return_value = DIMS
        emb._model = mock_model
        results = emb.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)
        assert all(len(r) == DIMS for r in results)


class TestEmbedderModelDim:
    def test_model_dim_property(self):
        emb = Embedder(mode="cpu")
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = DIMS
        emb._model = mock_model
        assert emb.model_dim == DIMS
