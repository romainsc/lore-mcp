# Grooming E3.41 — Fix get_config: missing parse fields

## Context

E3.40 implemented `get_config` MCP tool. The
parse section only exposes `ocr_engine`,
`ocr_lang`, `caption_primary`, `stt_model`.
Several LoreConfig parse fields are missing
from the output.

## Bug

`_build_config_yaml()` in server.py (line 562)
builds the parse section with only 4 fields.
LoreConfig has 10 parse-related fields:

| Field | In get_config | Status |
|-------|:---:|--------|
| `ocr_engine` | yes | OK |
| `ocr_lang` | yes | OK |
| `caption_primary` | yes | OK |
| `stt_model` | yes | OK |
| `caption_additional` | **no** | Missing |
| `caption_models` | **no** | Missing (backward compat) |
| `caption_selection` | **no** | Missing |
| `caption_judge` | **no** | Missing |
| `video_frame_strategy` | **no** | Missing |
| `video_frame_interval` | **no** | Missing |

## Fix

Add the missing fields to `_build_config_yaml()`,
same pattern as existing ones (only include when
non-default):

```python
if config.caption_additional:
    parse_section["caption_additional"] = list(config.caption_additional)
if config.caption_selection != "first_nonempty":
    parse_section["caption_selection"] = config.caption_selection
if config.caption_judge:
    parse_section["caption_judge"] = config.caption_judge
if config.video_frame_strategy != "scene":
    parse_section["video_frame_strategy"] = config.video_frame_strategy
if config.video_frame_interval != 30:
    parse_section["video_frame_interval"] = config.video_frame_interval
```

`caption_models` (backward compat alias for
`caption_additional`) is not exposed — the
canonical field is `caption_additional`.

## DoD

- All parse config fields visible in get_config
  output (when non-default)
- Test: configure all parse fields, verify
  they appear in YAML output
- CI green

## MVP

Single fix — add fields to `_build_config_yaml`.

## Dependencies

None.
