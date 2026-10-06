# Grooming E1.05 MVP3+MVP4 — Evaluator + Parser classes

## MVP3 — Evaluator class (eval.py)

### Problem

eval.py has 27 functions (14 public + 13 private),
1027 lines. Functions share embedder, db, questions
during an eval or optimize run. State is passed
through parameters across 14 function calls.

### Design

```python
class Evaluator:
    """RAG evaluation and optimization."""

    def __init__(self, db_path: str, embedder):
        self.store = ChunkStore(db_path)
        self.embedder = embedder

    # Question generation
    def generate_questions_from_db(self, n) -> list
    def generate_questions_from_sources(self, dir, n) -> list

    # Evaluation
    def evaluate(self, questions, top_k, ...) -> dict
    def compute_metrics(self, results) -> dict

    # Optimization
    def optimize(self, chunk_sizes, overlaps, ...) -> dict

    # Reporting
    def format_report(self, results) -> str
```

Private helpers become methods: `_generate_extractive`,
`_check_ragas`, `_optimize_ingest`, etc.

`run_eval` and `run_optimize` CLI entry points
become thin wrappers around `Evaluator`.

### Consumers

- server.py: `start_eval`, `start_optimize`
- build.py: `_run_optimization`
- CLI: `_run_eval`, `_run_optimize`

### DoD

- Evaluator class in eval.py
- All consumers migrated
- Existing tests pass, CI green

### Effort

Moyen — refactoring mécanique.

---

## MVP4 — Parser class (preprocess/parse.py)

### Problem

parse.py has 30 functions (12 public + 18 private),
1229 lines. Config params (ocr_engine, ocr_lang,
caption models, STT entry) are threaded through
many function calls.

### Design

```python
class Parser:
    """Multi-format document parser."""

    def __init__(self, config):
        self.ocr_engine = config.ocr_engine
        self.ocr_lang = config.ocr_lang
        self.caption_models = ...
        self.stt_entry = ...

    # Format detection
    def detect_format(self, path) -> str
    def parse_to_markdown(self, path, fmt) -> str

    # Docling
    def parse_with_docling(self, path) -> tuple
    def caption_with_docling(self, doc_json, model) -> str

    # Audio/Video
    def transcribe_audio(self, path) -> str
    def parse_video(self, path) -> str

    # Inline frames
    def caption_inline_frames(self, text, ...) -> str
```

Config is set once in `__init__`, not passed
through every call.

### Consumers

- preprocess/__init__.py: `_phase1_worker`,
  phase 2 captioning, phase 1.7 inline frames

### DoD

- Parser class in preprocess/parse.py
- Config set at construction, not passed per-call
- Phase 1 subprocess creates Parser with config
- Existing tests pass, CI green

### Effort

Moyen — parse.py is the largest file (1229 lines).

---

## Sequencing

| Order | MVP | Class | Prerequisite |
|-------|-----|-------|-------------|
| 1 | MVP2 | ChunkStore (store.py) | — |
| 2 | MVP3 | Evaluator (eval.py) | ChunkStore |
| 3 | MVP4 | Parser (parse.py) | — |
| 4 | E3.29 | source_id PK | ChunkStore |
| 5 | E12.67 | phase hash 2/3 | — |

MVP2 first (prérequis E3.29). MVP3 et MVP4
parallélisables. E3.29 après MVP2. E12.67
indépendant.
