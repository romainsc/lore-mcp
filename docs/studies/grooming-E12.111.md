# Grooming E12.111 — cancel_task must stop running tasks

## Existing mechanism

E12.59 implemented graceful shutdown via:
- `_shutdown_requested` global flag (service.py:30)
- `_signal_handler` sets flag on SIGINT/SIGTERM
- `run_with_interrupt()` checks flag every 0.5s
- `call_llm_batch()` checks flag between calls
- `KeyboardInterrupt` raised → existing cleanup
  runs (stop_service, free VRAM)

This mechanism is **global** (whole process).
cancel_task needs a **per-task** equivalent.

## Fix

### Per-task cancel event

Add `cancel_event: threading.Event` to TaskInfo.
`cancel()` sets the event for running tasks.

```python
@dataclass
class TaskInfo:
    ...
    cancel_event: threading.Event = field(
        default_factory=threading.Event)
```

### Unified check function

One function checks both global shutdown and
per-task cancellation:

```python
def check_cancelled():
    """Raise if shutdown requested or task cancelled."""
    if _shutdown_requested:
        raise KeyboardInterrupt("Shutdown requested")
    info = getattr(threading.current_thread(),
                   "_task_info", None)
    if info and info.cancel_event.is_set():
        raise KeyboardInterrupt("Task cancelled")
```

Replace all `if _shutdown_requested: ...` checks
in llm.py and service.py with
`check_cancelled()`.

### Check points in pipeline

Insert `check_cancelled()` at:
1. `preprocess_sources`: before each phase
   (1, 1.5, 1.6, 1.7, 2, 3, 4) — 7 points
2. `run_build`: before preprocess, optimize,
   index, metadata — 4 points
3. `call_llm_batch`: already checks
   `_shutdown_requested` — replace with
   `check_cancelled()`

### cancel() updated

```python
def cancel(self, task_id):
    info = self._tasks.get(task_id)
    if not info:
        return False
    if info.status == "pending":
        info.status = "cancelled"
        info.completed_at = time.time()
        return True
    if info.status == "running":
        info.cancel_event.set()
        return True
    return False
```

The running task will pick up the event at the
next check point and raise KeyboardInterrupt.
The existing exception handler in `_worker`
catches it and sets status to "failed".
Alternatively, catch `KeyboardInterrupt`
specifically and set status to "cancelled".

## DoD

- cancel_task stops running tasks at next
  check point (<10s typical)
- Cancelled task status = "cancelled"
- Services cleaned up
- Test: start task, cancel, verify status
- CI green

## MVP

Single MVP — TaskInfo.cancel_event +
check_cancelled() + check points + cancel()
update.

## Risks

Subprocess _phase1_worker: cancel event won't
reach it. Cancellation takes effect between
phases in the parent process. Acceptable for MVP.
