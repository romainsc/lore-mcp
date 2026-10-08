# Grooming E12.149 — Service start command fails silently

## Problem

`start_service` (service.py:96) uses `Popen` with
`stderr=DEVNULL`. If the start script path is wrong
or the command fails, no error is raised — the
pipeline waits the full timeout (120-300s) before
`_wait_for_health` raises a generic TimeoutError.

## Root cause

`Popen` launches and forgets — no return code check,
no stderr capture.

## Fix

1. Capture stderr (`stderr=subprocess.PIPE`)
2. After 2s sleep, `poll()` the process
3. If terminated with non-zero exit: raise
   `RuntimeError` with command + stderr
4. Normal case (server stays alive): `poll()`
   returns None, continue to `_wait_for_health`

## DoD

1. ✅ Fast failure on bad start command (< 3s)
2. ✅ Actionable error message (command + stderr)
3. ✅ Normal server start path unchanged
4. ✅ Tests pass (14/14)
5. ⬜ CI green
