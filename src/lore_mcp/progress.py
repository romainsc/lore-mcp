"""Structured progress output for build/optimize. See docs/architecture.md."""


class ProgressReporter:
    """Structured progress output with Markdown tables."""

    def __init__(self, collection: str = "", models: list[str] | None = None,
                 total_configs: int = 0):
        self.collection = collection
        self.models = models or []
        self.total_configs = total_configs

    def print_header(self) -> None:
        models_str = ", ".join(self.models)
        n_models = len(self.models)
        print(f"╔{'═' * 58}╗")
        print(f"║  lore-mcp build — {self.collection:<39}║")
        print(f"║  Models: {models_str:<48}║")
        print(f"║  Configs: {self.total_configs:<47}║")
        print(f"╚{'═' * 58}╝")

    def print_section(self, title: str) -> None:
        padding = 58 - len(title) - 2
        print(f"\n── {title} {'─' * max(padding, 3)}")

    def print_step(self, label: str, elapsed: float) -> None:
        print(f"  {label}: {elapsed:.1f}s")

    def print_check(self, label: str) -> None:
        print(f"  ✓ {label}")

    def print_table_header(self) -> None:
        print(f"  {'':4}| {'#':>4} | {'Model':<20}| {'Chunk':<10}| {'top_k':>5} | {'avg':>8} |")
        print(f"  {'':4}|{'─' * 6}|{'─' * 21}|{'─' * 11}|{'─' * 7}|{'─' * 10}|")

    def print_row(self, num: int, model: str, chunk_size: int,
                  chunk_overlap: int, top_k: int, avg_score: float,
                  is_best: bool = False) -> None:
        star = " ★  " if is_best else "    "
        chunk = f"{chunk_size}/{chunk_overlap}"
        print(f"  {star}| {num:>4} | {model:<20}| {chunk:<10}| {top_k:>5} | {avg_score:>8.4f} |")

    def print_results_table(self, results: list[dict]) -> None:
        if not results:
            return
        best_idx = max(range(len(results)), key=lambda i: results[i]["avg_score"])
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

    def print_summary(self, files: int, chunks: int, configs_tested: int,
                      elapsed: float, report_path: str) -> None:
        self.print_section("Summary")
        print()
        print(f"  | {'Metric':<16}| {'Value':<15}|")
        print(f"  |{'─' * 17}|{'─' * 16}|")
        print(f"  | {'Collection':<16}| {self.collection:<15}|")
        print(f"  | {'Files':<16}| {files:<15}|")
        print(f"  | {'Chunks':<16}| {chunks:<15}|")
        print(f"  | {'Configs tested':<16}| {configs_tested:<15}|")
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        time_str = f"{minutes}m {seconds:.0f}s" if minutes else f"{seconds:.1f}s"
        print(f"  | {'Total time':<16}| {time_str:<15}|")
        print(f"\n  Report: {report_path}")
