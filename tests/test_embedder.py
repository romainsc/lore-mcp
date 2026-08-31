"""Tests for lore_mcp.embedder. See docs/architecture.md for design context."""

from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from lore_mcp.embedder import Embedder, assess_gpu, assess_cpu


DIMS = 1024
MODEL = "BAAI/bge-m3"


class TestAssessGpu:
    """Validate GPU capability assessment documented in architecture.md:
    VRAM detection, FP32/FP16 decision, actionable messages.
    """

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
    def test_not_enough_vram_actionable_message(self, mock_torch):
        """architecture.md: actionable message when VRAM insufficient."""
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.mem_get_info.return_value = (500 * 1024**2, 2 * 1024**3)
        mock_torch.cuda.get_device_capability.return_value = (7, 5)
        mock_torch.cuda.get_device_name.return_value = "Test GPU"
        result = assess_gpu()
        assert result["available"] is False
        assert "vram" in result["message"].lower() or "free" in result["message"].lower()

    @patch("lore_mcp.embedder.torch", None)
    def test_no_torch(self):
        result = assess_gpu()
        assert result["available"] is False

    @patch("lore_mcp.embedder.torch")
    def test_old_gpu_no_fp16(self, mock_torch):
        """Compute capability < 7 does not support FP16."""
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.mem_get_info.return_value = (int(1.8 * 1024**3), 4 * 1024**3)
        mock_torch.cuda.get_device_capability.return_value = (6, 1)
        mock_torch.cuda.get_device_name.return_value = "Old GPU"
        result = assess_gpu()
        assert result["available"] is False


class TestAssessCpu:
    """Validate CPU capability assessment documented in architecture.md."""

    def test_returns_availability(self):
        result = assess_cpu()
        assert "available" in result
        assert "ram_available_gb" in result

    def test_reports_ram(self):
        result = assess_cpu()
        assert result["ram_available_gb"] > 0

    @patch("lore_mcp.embedder._get_available_ram_gb", return_value=2.0)
    def test_insufficient_ram(self, _):
        result = assess_cpu()
        assert result["available"] is False


class TestEmbedderInit:
    def test_default_mode_is_builtin(self):
        emb = Embedder()
        assert emb.mode == "builtin"

    def test_default_model(self):
        emb = Embedder()
        assert emb.model_name == MODEL

    def test_custom_model(self):
        emb = Embedder(model_name="custom/model")
        assert emb.model_name == "custom/model"

    def test_api_mode_without_url_raises(self):
        with pytest.raises(ValueError, match="LORE_API_URL"):
            Embedder(mode="api")

    def test_api_mode_with_url(self):
        emb = Embedder(mode="api", api_url="http://localhost:8000/v1/embeddings")
        assert emb.mode == "api"

    def test_api_model_defaults_to_model_name(self):
        emb = Embedder(mode="api", api_url="http://localhost/v1/embeddings")
        assert emb.api_model == MODEL

    def test_api_model_override(self):
        emb = Embedder(
            mode="api",
            api_url="http://localhost/v1/embeddings",
            api_model="custom-api-model",
        )
        assert emb.api_model == "custom-api-model"


class TestEmbedderLazyLoading:
    """Validate lazy loading documented in architecture.md:
    model not loaded at init, only on first embed().
    """

    def test_model_not_loaded_at_init(self):
        emb = Embedder(mode="builtin:cpu")
        assert emb._model is None

    def test_model_loaded_on_first_embed(self):
        emb = Embedder(mode="builtin:cpu")
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(DIMS).astype("float32")
        mock_model.get_embedding_dimension.return_value = DIMS
        emb._model = mock_model
        emb.embed("test")
        mock_model.encode.assert_called_once()


class TestEmbedderFallbackChain:
    """Validate the GPU → CPU fallback documented in architecture.md."""

    @patch("lore_mcp.embedder.assess_gpu")
    def test_auto_mode_selects_gpu_when_available(self, mock_assess):
        mock_assess.return_value = {
            "available": True,
            "recommended_dtype": "float32",
        }
        emb = Embedder(mode="builtin")
        device, dtype = emb._select_device_dtype()
        assert device == "cuda"

    @patch("lore_mcp.embedder.assess_gpu")
    def test_auto_mode_falls_back_to_cpu(self, mock_assess):
        mock_assess.return_value = {"available": False, "message": "no GPU"}
        emb = Embedder(mode="builtin")
        device, dtype = emb._select_device_dtype()
        assert device == "cpu"

    @patch("lore_mcp.embedder.assess_gpu")
    def test_auto_mode_selects_fp16_when_recommended(self, mock_assess):
        mock_assess.return_value = {
            "available": True,
            "recommended_dtype": "float16",
        }
        emb = Embedder(mode="builtin")
        device, dtype = emb._select_device_dtype()
        assert device == "cuda"
        import torch
        assert dtype == torch.float16

    def test_cpu_mode_selects_cpu(self):
        emb = Embedder(mode="builtin:cpu")
        device, dtype = emb._select_device_dtype()
        assert device == "cpu"
        assert dtype is None

    @patch("lore_mcp.embedder.assess_gpu")
    def test_gpu_mode_raises_when_unavailable(self, mock_assess):
        mock_assess.return_value = {
            "available": False,
            "message": "VRAM insufficient",
        }
        emb = Embedder(mode="builtin:gpu")
        with pytest.raises(RuntimeError):
            emb._select_device_dtype()


class TestEmbedderEmbed:
    def _make_embedder_with_mock_model(self):
        emb = Embedder(mode="builtin:cpu")
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(DIMS).astype("float32")
        mock_model.get_embedding_dimension.return_value = DIMS
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
        vec = np.random.randn(DIMS).astype("float32")
        vec = vec / np.linalg.norm(vec)
        emb._model.encode.return_value = vec
        result = emb.embed("hello")
        norm = sum(x**2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_calls_encode_with_normalize(self):
        """architecture.md: normalize_embeddings=True is always passed."""
        emb = self._make_embedder_with_mock_model()
        emb.embed("test")
        emb._model.encode.assert_called_with("test", normalize_embeddings=True)


class TestEmbedderEmbedBatch:
    def test_returns_list_of_lists(self):
        emb = Embedder(mode="builtin:cpu")
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(3, DIMS).astype("float32")
        mock_model.get_embedding_dimension.return_value = DIMS
        emb._model = mock_model
        results = emb.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)
        assert all(len(r) == DIMS for r in results)

    def test_calls_encode_with_normalize(self):
        emb = Embedder(mode="builtin:cpu")
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(2, DIMS).astype("float32")
        emb._model = mock_model
        emb.embed_batch(["a", "b"])
        mock_model.encode.assert_called_with(["a", "b"], normalize_embeddings=True)


class TestEmbedderModelDim:
    def test_model_dim_property(self):
        emb = Embedder(mode="builtin:cpu")
        mock_model = MagicMock()
        mock_model.get_embedding_dimension.return_value = DIMS
        emb._model = mock_model
        assert emb.model_dim == DIMS


class TestEmbedderAssess:
    """Validate the assess() method documented in architecture.md."""

    @patch("lore_mcp.embedder.assess_gpu")
    @patch("lore_mcp.embedder.assess_cpu")
    def test_returns_all_backends(self, mock_cpu, mock_gpu):
        mock_gpu.return_value = {"available": False, "message": "no GPU"}
        mock_cpu.return_value = {"available": True, "ram_available_gb": 16.0, "message": "OK"}
        emb = Embedder(mode="builtin")
        result = emb.assess()
        assert "gpu" in result
        assert "cpu" in result
        assert "api" in result

    @patch("lore_mcp.embedder._probe_api", return_value=True)
    @patch("lore_mcp.embedder.assess_gpu")
    @patch("lore_mcp.embedder.assess_cpu")
    def test_probes_api_when_url_set(self, mock_cpu, mock_gpu, mock_probe):
        mock_gpu.return_value = {"available": False, "message": "no GPU"}
        mock_cpu.return_value = {"available": True, "ram_available_gb": 16.0, "message": "OK"}
        emb = Embedder(mode="builtin", api_url="http://localhost:8000/v1/embeddings")
        result = emb.assess()
        assert result["api"]["available"] is True
