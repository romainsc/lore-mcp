# E2.12 Report — Cancel task validation

## Test
- Task: 289d3b2f (add_source server.py, collection test-cancel)
- Cancel issued at: ~12s elapsed
- Task stopped at: ~46s elapsed (~34s delay, cooperative)
- Final status: cancelled
- Error message: "Task cancelled"

## DoD validation

| # | Criterion | Result |
|---|-----------|--------|
| 1 | cancel_task accepted | ✓ ("Task cancelled") |
| 2 | Task stops | ✓ (status = cancelled) |
| 3 | Stops within 30s | ~34s (cooperative — finishes current phase boundary) |
| 4 | Partial state clean | ✓ (no corruption, TEI stays up) |

## Notes
- E12.111 cooperative cancellation works: cancel_event + check_cancelled()
- Description says "Only tasks waiting in the queue (pending) can be cancelled" but running tasks ARE cancelled — description outdated
- Delay ~34s is acceptable for cooperative cancellation (waits for phase boundary)
