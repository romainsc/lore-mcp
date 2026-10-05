# Grooming E12.113 — MCP server disconnects at build completion

## Bug

lore-mcp MCP server (stdio) loses connection
when add_recipe task completes. Reproduced on
2 runs. Claude Code reports "MCP server
disconnected".

## Analysis

The build runs in a daemon thread via
TaskManager (server.py:859). When the task
completes, the thread exits. The MCP server
main loop (`mcp.run()`) continues on the main
thread.

Possible causes:
1. **Unhandled exception in _do_recipe** —
   if run_build raises and the error propagates
   to the MCP SDK
2. **sys.exit somewhere in the pipeline** —
   signal handler calls `sys.exit(128+signum)`.
   If a signal fires during build completion,
   the entire process exits
3. **Memory/resource exhaustion** — after a long
   build, Python may OOM or the MCP SDK may
   timeout
4. **stdio corruption** — print() calls in
   build/preprocess pipeline write to stdout,
   which is also used by MCP stdio transport.
   Any non-MCP output on stdout corrupts the
   protocol

## Most likely: stdout corruption (#4)

The MCP SDK uses stdio (stdin/stdout) for
communication. If `run_build` or
`preprocess_sources` prints to stdout (via
`print()` or ProgressReporter), the MCP
protocol is corrupted and the client
disconnects.

Evidence: `output_level = "quiet"` is set in
add_recipe (server.py:848), which should
silence ProgressReporter. But:
- `preprocess_sources` has `if not quiet: print()`
  blocks that check `output_level == "quiet"`
- `run_build` uses ProgressReporter which checks
  the output level
- If any code path prints without checking
  quiet, stdout is corrupted

## Fix

Redirect stdout/stderr in task threads to
prevent protocol corruption:

```python
# In TaskManager._worker, before fn():
import io
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()
```

Or more safely, redirect at the thread level
only:

```python
import threading
_thread_stdout = threading.local()
```

Alternative (simpler): ensure ALL print paths
check quiet mode. But this is fragile — one
missed print breaks the server.

Recommended fix: redirect stdout in daemon
task threads. Log output to a file in .work/
instead of stdout. This is the robust solution.

## DoD

- add_recipe completes without MCP disconnect
- Task output captured to log file, not stdout
- MCP server remains connected after build
- Test: mock task with print() — verify no
  stdout leakage
- CI green
