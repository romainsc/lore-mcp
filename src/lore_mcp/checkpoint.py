"""Pipeline checkpoint for resumable runs. See docs/studies/grooming-E12.63.md."""

import hashlib
import json
import os
from pathlib import Path


def _state_dir() -> Path:
    """Return XDG_STATE_HOME/lore-mcp/."""
    base = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    d = Path(base) / "lore-mcp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _collection_hash(manifest_path: str, config_path: str = "") -> str:
    """Hash manifest + config content to identify a pipeline run."""
    h = hashlib.sha256()
    if manifest_path and Path(manifest_path).exists():
        h.update(Path(manifest_path).read_bytes())
    if config_path and Path(config_path).exists():
        h.update(Path(config_path).read_bytes())
    return h.hexdigest()[:16]


def phase_hash(manifest_path: str, config=None, phase: str = "") -> str:
    """Hash only the dependencies relevant to a specific phase.

    Phase 1 (parse): manifest sources + ocr_engine + ocr_lang
    Phase 1.6 (stt): manifest sources + stt_model
    Phase 2 (caption): manifest sources + caption models
    Phase 3 (enrich): enrich techniques + LLM model
    """
    h = hashlib.sha256()
    if manifest_path and Path(manifest_path).exists():
        h.update(Path(manifest_path).read_bytes())
    if config is None:
        return h.hexdigest()[:16]

    if phase in ("parse", "phase1"):
        h.update(getattr(config, "ocr_engine", "").encode())
        for lang in getattr(config, "ocr_lang", []):
            h.update(lang.encode())
    elif phase in ("stt", "phase1_stt"):
        h.update(getattr(config, "stt_model", "").encode())
    elif phase in ("caption", "phase2"):
        h.update(getattr(config, "caption_primary", "").encode())
        for m in getattr(config, "caption_additional", []):
            h.update(m.encode())
    elif phase in ("enrich", "phase3"):
        for t in getattr(config, "enrich_techniques", []):
            h.update(t.encode())
        for m in getattr(config, "enrich_models", []):
            h.update(m.encode())

    return h.hexdigest()[:16]


class Checkpoint:
    """Track pipeline progress for resumable runs."""

    def __init__(self, manifest_path: str, config_path: str = "", force: bool = False):
        self._hash = _collection_hash(manifest_path, config_path)
        self._dir = _state_dir() / self._hash
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "checkpoint.json"
        self._force = force
        self._data = self._load()

    def _load(self) -> dict:
        if self._force or not self._file.exists():
            return {"hash": self._hash, "phases": {}}
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"hash": self._hash, "phases": {}}

    def _save(self):
        self._file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def state_dir(self) -> Path:
        return self._dir

    def is_completed(self, phase: str, source: str) -> bool:
        if self._force:
            return False
        return source in self._data.get("phases", {}).get(phase, {}).get("completed", [])

    def mark_completed(self, phase: str, source: str):
        phases = self._data.setdefault("phases", {})
        p = phases.setdefault(phase, {"completed": [], "status": "in_progress"})
        if source not in p["completed"]:
            p["completed"].append(source)
        self._save()

    def mark_phase_done(self, phase: str):
        phases = self._data.setdefault("phases", {})
        p = phases.setdefault(phase, {"completed": [], "status": "done"})
        p["status"] = "done"
        self._save()

    def is_phase_done(self, phase: str) -> bool:
        if self._force:
            return False
        return self._data.get("phases", {}).get(phase, {}).get("status") == "done"

    def cleanup(self):
        """Remove state directory after successful completion."""
        import shutil
        if self._dir.exists():
            shutil.rmtree(self._dir)

    def summary(self) -> dict:
        """Return a summary of checkpoint state."""
        phases = self._data.get("phases", {})
        return {
            "hash": self._hash,
            "dir": str(self._dir),
            "phases": {
                name: {"completed": len(p.get("completed", [])), "status": p.get("status", "?")}
                for name, p in phases.items()
            },
        }


def list_states() -> list[dict]:
    """List all pipeline state directories with metadata."""
    state = _state_dir()
    results = []
    for d in sorted(state.iterdir()):
        if not d.is_dir():
            continue
        cp_file = d / "checkpoint.json"
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        info = {"hash": d.name, "path": str(d), "size_mb": round(size / 1048576, 1)}
        if cp_file.exists():
            try:
                data = json.loads(cp_file.read_text())
                phases = data.get("phases", {})
                info["phases"] = len(phases)
                info["sources"] = sum(
                    len(p.get("completed", [])) for p in phases.values()
                )
            except Exception:
                pass
        results.append(info)
    return results


def purge_state_by_hash(hash_prefix: str) -> bool:
    """Delete a specific pipeline state by hash prefix."""
    import shutil
    state = _state_dir()
    for d in state.iterdir():
        if d.is_dir() and d.name.startswith(hash_prefix):
            shutil.rmtree(d)
            return True
    return False


def purge_states(max_age_days: int = 7, purge_all: bool = False):
    """Delete old or all pipeline state directories."""
    import shutil
    import time
    state = _state_dir()
    now = time.time()
    removed = 0
    for d in sorted(state.iterdir()):
        if not d.is_dir():
            continue
        if purge_all:
            shutil.rmtree(d)
            removed += 1
        else:
            age = now - d.stat().st_mtime
            if age > max_age_days * 86400:
                shutil.rmtree(d)
                removed += 1
    return removed
