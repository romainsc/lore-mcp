"""Embedding engine with GPU/API/CPU fallback. See docs/architecture.md."""

import logging
from pathlib import Path

try:
    import torch
except ImportError:
    torch = None

logger = logging.getLogger(__name__)

FP32_VRAM_GB = 2.8
FP16_VRAM_GB = 1.5
CPU_RAM_MIN_GB = 4.0

DEFAULT_MODEL = "BAAI/bge-m3"


def assess_gpu() -> dict:
    """Evaluate GPU capabilities for model loading."""
    if torch is None or not torch.cuda.is_available():
        return {"available": False, "message": "CUDA not available"}

    free, total = torch.cuda.mem_get_info(0)
    free_gb = free / (1024**3)
    total_gb = total / (1024**3)
    major, _ = torch.cuda.get_device_capability(0)
    gpu_name = torch.cuda.get_device_name(0)
    supports_fp16 = major >= 7

    if free_gb >= FP32_VRAM_GB:
        return {
            "available": True,
            "gpu_name": gpu_name,
            "vram_free_gb": round(free_gb, 1),
            "vram_total_gb": round(total_gb, 1),
            "recommended_dtype": "float32",
            "message": f"{gpu_name}: {free_gb:.1f}/{total_gb:.1f} GB free, FP32 OK",
        }
    if free_gb >= FP16_VRAM_GB and supports_fp16:
        return {
            "available": True,
            "gpu_name": gpu_name,
            "vram_free_gb": round(free_gb, 1),
            "vram_total_gb": round(total_gb, 1),
            "recommended_dtype": "float16",
            "message": f"{gpu_name}: {free_gb:.1f}/{total_gb:.1f} GB free, FP16 mode",
        }

    msg = (
        f"{gpu_name}: {free_gb:.1f}/{total_gb:.1f} GB VRAM free, "
        f"need {FP16_VRAM_GB} GB minimum. "
        f"Try freeing VRAM (close GPU-heavy applications)."
    )
    return {"available": False, "vram_free_gb": round(free_gb, 1), "message": msg}


def assess_cpu() -> dict:
    """Evaluate CPU capabilities for model loading."""
    ram_gb = _get_available_ram_gb()
    if ram_gb >= CPU_RAM_MIN_GB:
        return {
            "available": True,
            "ram_available_gb": round(ram_gb, 1),
            "message": f"{ram_gb:.1f} GB RAM available, CPU mode OK",
        }
    return {
        "available": False,
        "ram_available_gb": round(ram_gb, 1),
        "message": f"{ram_gb:.1f} GB RAM available, need {CPU_RAM_MIN_GB} GB minimum",
    }


def _get_available_ram_gb() -> float:
    """Read available RAM in GB from /proc/meminfo or psutil."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024**2)
    except OSError:
        pass
    try:
        import psutil
        return psutil.virtual_memory().available / (1024**3)
    except ImportError:
        return 0.0


def _probe_api(url: str, model: str, timeout: float = 5.0) -> bool:
    """Check if a remote embedding API is reachable."""
    try:
        import httpx
        resp = httpx.post(
            url,
            json={"model": model, "input": ["test"]},
            timeout=httpx.Timeout(timeout, connect=3.0),
        )
        return resp.status_code == 200
    except Exception:
        return False


class Embedder:
    """Embedding engine with automatic GPU/API/CPU fallback.

    See docs/architecture.md for the fallback chain and capability
    assessment logic.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        mode: str = "auto",
        api_url: str | None = None,
        api_model: str | None = None,
    ):
        if mode == "api" and not api_url:
            raise ValueError("LORE_API_URL is required when mode is 'api'")
        self.model_name = model_name
        self.mode = mode
        self.api_url = api_url
        self.api_model = api_model or model_name
        self._model = None
        self._device = None
        self._dtype = None

    @property
    def model_dim(self) -> int:
        """Return the embedding dimension of the loaded model."""
        self._ensure_loaded()
        return self._model.get_embedding_dimension()

    def assess(self) -> dict:
        """Evaluate available backends and select the best one."""
        gpu = assess_gpu()
        cpu = assess_cpu()
        api = {"available": False, "message": "No API URL configured"}
        if self.api_url:
            reachable = _probe_api(self.api_url, self.api_model)
            api = {
                "available": reachable,
                "message": f"{self.api_url}: {'OK' if reachable else 'unreachable'}",
            }
        return {"gpu": gpu, "api": api, "cpu": cpu}

    def embed(self, text: str) -> list[float]:
        """Embed a single text. Returns a list of floats."""
        self._ensure_loaded()
        if self.mode == "api":
            return self._embed_api([text])[0]
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Returns a list of float lists."""
        self._ensure_loaded()
        if self.mode == "api":
            return self._embed_api(texts)
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return vecs.tolist()

    def _ensure_loaded(self) -> None:
        """Lazily load the model on first use."""
        if self._model is not None:
            return
        if self.mode == "api":
            return
        self._load_local_model()

    def _load_local_model(self) -> None:
        """Load sentence-transformers model with appropriate device/dtype."""
        from sentence_transformers import SentenceTransformer

        device, dtype = self._select_device_dtype()
        model_kwargs = {}
        if dtype is not None:
            model_kwargs["torch_dtype"] = dtype

        logger.info("Loading %s on %s (dtype=%s)", self.model_name, device, dtype)
        self._model = SentenceTransformer(
            self.model_name, device=device, model_kwargs=model_kwargs
        )
        self._device = device
        self._dtype = dtype

    def _select_device_dtype(self) -> tuple:
        """Pick device and dtype based on mode and capabilities."""
        if self.mode == "gpu":
            return "cuda", self._gpu_dtype()
        if self.mode == "cpu":
            return "cpu", None
        # auto: try GPU first, then CPU
        gpu = assess_gpu()
        if gpu["available"]:
            dtype_str = gpu["recommended_dtype"]
            dt = torch.float16 if dtype_str == "float16" else None
            return "cuda", dt
        return "cpu", None

    def _gpu_dtype(self):
        """Determine dtype for forced GPU mode."""
        gpu = assess_gpu()
        if not gpu["available"]:
            raise RuntimeError(f"GPU mode requested but: {gpu['message']}")
        if gpu["recommended_dtype"] == "float16":
            return torch.float16
        return None

    def _embed_api(self, texts: list[str]) -> list[list[float]]:
        """Embed via a remote OpenAI-compatible API."""
        import httpx
        resp = httpx.post(
            self.api_url,
            json={"model": self.api_model, "input": texts},
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return [d["embedding"] for d in data]
