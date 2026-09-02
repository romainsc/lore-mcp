"""Output management: 5 levels from quiet to debug. See docs/architecture.md."""

import json
import logging
import time

QUIET = "quiet"
PROGRESS = "progress"
DEFAULT = "default"
VERBOSE = "verbose"
DEBUG = "debug"

LEVELS = [QUIET, PROGRESS, DEFAULT, VERBOSE, DEBUG]


def _fmt_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"



def configure_logging(level: str) -> None:
    """Configure logging level without overwriting existing format (Rich)."""
    root = logging.getLogger()
    if level == DEBUG:
        root.setLevel(logging.WARNING)
        logging.getLogger("lore_mcp").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.INFO)
        for name in ("httpcore", "sentence_transformers",
                     "huggingface_hub", "numexpr", "transformers"):
            logging.getLogger(name).setLevel(logging.WARNING)
    elif level == QUIET:
        root.setLevel(logging.ERROR)
    else:
        root.setLevel(logging.WARNING)
        for name in ("httpx", "httpcore", "sentence_transformers",
                     "huggingface_hub", "numexpr", "transformers"):
            logging.getLogger(name).setLevel(logging.WARNING)


def output_level_from_args(args) -> str:
    """Determine output level from CLI args."""
    if getattr(args, "quiet", False):
        return QUIET
    if getattr(args, "progress", False):
        return PROGRESS
    if getattr(args, "debug", False):
        return DEBUG
    if getattr(args, "verbose", False):
        return VERBOSE
    return DEFAULT


class ProgressReporter:
    """Structured output adapted to the current level."""

    def __init__(self, collection: str = "", models: list[str] | None = None,
                 total_configs: int = 0, level: str = DEFAULT,
                 phases: list[str] | None = None):
        self.collection = collection
        self.models = models or []
        self.total_configs = total_configs
        self.level = level
        self._start = time.time()
        self._phases = phases or []
        self._current_phase = 0
        self._phase_start = self._start

    def begin_phase(self, name: str = "") -> None:
        self._current_phase += 1
        self._phase_start = time.time()

    def _silent(self) -> bool:
        return self.level == QUIET

    def _is_progress(self) -> bool:
        return self.level == PROGRESS

    def _is_verbose(self) -> bool:
        return self.level in (VERBOSE, DEBUG)

    # --- Header ---

    def print_header(self) -> None:
        if self._silent():
            return
        if self._is_progress():
            models_str = ", ".join(self.models)
            print(f"lore-mcp build {self.collection} ({self.total_configs} configs, models: {models_str})")
            return
        models_str = ", ".join(self.models)
        print(f"╔{'═' * 58}╗")
        print(f"║  lore-mcp build — {self.collection:<39}║")
        print(f"║  Models: {models_str:<48}║")
        print(f"║  Configs: {self.total_configs:<47}║")
        print(f"╚{'═' * 58}╝")

    # --- Sections ---

    def print_section(self, title: str) -> None:
        if self._silent() or self._is_progress():
            return
        padding = 58 - len(title) - 2
        print(f"\n── {title} {'─' * max(padding, 3)}")

    def print_step(self, label: str, elapsed: float = 0.0) -> None:
        if self._silent() or self._is_progress():
            return
        if elapsed:
            print(f"  {label}: {elapsed:.1f}s")
        else:
            print(f"  {label}")

    def print_check(self, label: str) -> None:
        if self._silent():
            return
        if self._is_progress():
            return
        print(f"  ✓ {label}")

    def print_milestone(self, config_num: int = 0, msg: str = "",
                        detail: str = "") -> None:
        """Progress: structured line with global + phase progress. Verbose: full detail."""
        if self._silent():
            return
        if self._is_progress() and config_num and self.total_configs:
            total_elapsed = time.time() - self._start
            phase_elapsed = time.time() - self._phase_start

            total_phases = len(self._phases) if self._phases else 1
            phase_name = self._phases[self._current_phase - 1] if self._phases and self._current_phase <= total_phases else "Optimizing"

            phase_pct = config_num * 100 // self.total_configs
            phase_eta = ""
            if config_num > 0:
                phase_remaining = phase_elapsed / config_num * (self.total_configs - config_num)
                phase_eta = f" ETA {_fmt_duration(phase_remaining)}"

            done_phases = self._current_phase - 1
            global_progress = (done_phases + config_num / self.total_configs) / total_phases
            global_pct = int(global_progress * 100)
            global_eta = ""
            if global_progress > 0:
                global_remaining = total_elapsed / global_progress * (1 - global_progress)
                global_eta = f" ETA {_fmt_duration(global_remaining)}"

            detail_str = f" {detail}" if detail else ""
            line = (
                f"\r  {global_pct}%{global_eta}"
                f" | {self._current_phase}/{total_phases} {phase_name}"
                f" [{config_num}/{self.total_configs}] {phase_pct}%{phase_eta}"
                f"{detail_str}"
            )
            print(f"{line:<80}", end="", flush=True)
            return
        if self._is_verbose():
            print(f"  {msg}")

    # --- Table ---

    def print_table_header(self) -> None:
        if self._silent() or self._is_progress():
            return
        print(f"  {'':4}| {'#':>4} | {'Model':<20}| {'Chunk':<10}| {'top_k':>5} | {'avg':>8} |")
        print(f"  {'':4}|{'─' * 6}|{'─' * 21}|{'─' * 11}|{'─' * 7}|{'─' * 10}|")

    def print_row(self, num: int, model: str, chunk_size: int,
                  chunk_overlap: int, top_k: int, avg_score: float,
                  is_best: bool = False) -> None:
        if self._silent():
            return
        if self._is_progress():
            elapsed = time.time() - self._start
            print(f"\r  Optimizing [{num}/{self.total_configs}] ({elapsed:.0f}s)", end="", flush=True)
            return
        star = " ★  " if is_best else "    "
        chunk = f"{chunk_size}/{chunk_overlap}"
        print(f"  {star}| {num:>4} | {model:<20}| {chunk:<10}| {top_k:>5} | {avg_score:>8.4f} |")

    def print_results_table(self, results: list[dict]) -> None:
        if self._silent():
            return
        if not results:
            return
        best_idx = max(range(len(results)), key=lambda i: results[i]["avg_score"])

        if self._is_progress():
            best = results[best_idx]
            print(f"\n  Best: {best['model_name']} "
                  f"chunk={best['chunk_size']}/{best['chunk_overlap']} "
                  f"top_k={best['top_k']} avg={best['avg_score']:.4f}")
            return

        self.print_section("Optimization results")
        self.print_table_header()
        for i, r in enumerate(results):
            self.print_row(
                num=i + 1,
                model=r["model_name"],
                chunk_size=r["chunk_size"],
                chunk_overlap=r["chunk_overlap"],
                top_k=r["top_k"],
                avg_score=r["avg_score"],
                is_best=(i == best_idx),
            )

    # --- Verbose detail ---

    def print_file(self, filename: str, chunks: int) -> None:
        if not self._is_verbose():
            return
        print(f"    {filename}: {chunks} chunks")

    def print_questions(self, questions: list[dict]) -> None:
        if not self._is_verbose():
            return
        print()
        print(f"  | {'#':>3} | {'Question':<50} | {'Source':<30} | {'Ground truth (truncated)':<40} |")
        print(f"  |{'-' * 5}|{'-' * 52}|{'-' * 32}|{'-' * 42}|")
        for i, q in enumerate(questions, 1):
            question = q["question"][:48]
            source = q.get("source_file", "")[:28]
            gt_raw = q.get("ground_truth", "")
            gt_first = gt_raw.split("\n")[0].strip()[:30]
            gt_words = len(gt_raw.split())
            gt_display = f"{gt_first} ({gt_words}w)"[:38]
            print(f"  | {i:>3} | {question:<50} | {source:<30} | {gt_display:<40} |")
        print(f"  (full questions and ground truth available in --output JSON report)")
        print()

    # --- Summary ---

    def print_summary(self, files: int = 0, chunks: int = 0, configs_tested: int = 0,
                      elapsed: float = 0.0, report_path: str = "") -> None:
        if self._silent():
            return
        if self._is_progress():
            print(f"  Done. {files} files, {chunks} chunks ({_fmt_duration(elapsed)})")
            return

        self.print_section("Summary")
        print()
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        time_str = f"{minutes}m {seconds:.0f}s" if minutes else f"{seconds:.1f}s"
        print(f"  | {'Metric':<16}| {'Value':<15}|")
        print(f"  |{'─' * 17}|{'─' * 16}|")
        print(f"  | {'Collection':<16}| {self.collection:<15}|")
        print(f"  | {'Files':<16}| {files:<15}|")
        print(f"  | {'Chunks':<16}| {chunks:<15}|")
        if configs_tested:
            print(f"  | {'Configs tested':<16}| {configs_tested:<15}|")
        print(f"  | {'Total time':<16}| {time_str:<15}|")
        if report_path:
            print(f"\n  Report: {report_path}")

    def report_step(self, label: str, elapsed: float) -> None:
        """Alias for print_step with timing."""
        self.print_step(label, elapsed)

    def report_config(self, config_num: int, model: str,
                      chunk_size: int, chunk_overlap: int,
                      top_k: int, avg_score: float) -> None:
        """Alias for print_row (non-best)."""
        self.print_row(config_num, model, chunk_size, chunk_overlap,
                       top_k, avg_score, is_best=False)

    def report_summary(self, best_model: str = "", best_score: float = 0.0,
                       best_chunk_size: int = 0, best_chunk_overlap: int = 0,
                       best_top_k: int = 0, elapsed: float = 0.0) -> None:
        """Print best config summary line."""
        if self._silent():
            return
        print(f"\n  Best: model={best_model} chunk={best_chunk_size}/{best_chunk_overlap} "
              f"top_k={best_top_k} avg={best_score:.4f} ({elapsed:.1f}s)")
