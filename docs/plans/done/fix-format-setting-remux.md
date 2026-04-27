# Fix: Video Format Setting Not Applied on Download

## Context

The format selection feature saves the user's container preference (`VID_DL_VIDEO_FORMAT`) and passes it to yt-dlp as `merge_output_format` and `remux_video`. The `merge_output_format` key is correct and works for merged (DASH) streams. The `remux_video` key is **wrong** — yt-dlp's Python API uses `remuxvideo` (no underscore between "remux" and "video", matching the CLI `dest='remuxvideo'`). The bad key is silently ignored, so pre-muxed single-stream fallback downloads always stay as `.mp4`.

---

## Plan A: Key Fix Only (implement first)

**Goal:** Fix the silent no-op: rename `remux_video` → `remuxvideo` in every place it appears.

### Files to change

| File | Line(s) | Change |
|------|---------|--------|
| `src/ydl_options.py` | 87, 101, 132 | `"remux_video": vfmt` → `"remuxvideo": vfmt` |
| `meadowlark.pyw` | 491, 506, 538 | `"remux_video": vfmt` → `"remuxvideo": vfmt` |
| `src/download_executor.py` | 113 | `"remux_video"` → `"remuxvideo"` |

### Tests to update

`tests/test_format_settings.py` and `tests/test_download_executor_formats.py` — grep for `remux_video` assertions and update them to `remuxvideo`.

### Verification

1. `pytest tests/test_format_settings.py tests/test_download_executor_formats.py`
2. `ruff check src/ydl_options.py meadowlark.pyw src/download_executor.py`
3. Manual: set video format to mkv, drag a YouTube URL to 720p zone, confirm output file is `.mkv`

---

## Plan B: Remove Duplicate `_get_source_options` (after Plan A is solid)

**Goal:** Eliminate the duplicate implementation in `meadowlark.pyw` so tests cover the live code path. Currently `tests/test_format_settings.py` tests `src/ydl_options.py::get_source_options`, but downloads use `meadowlark.pyw::_get_source_options` — a divergence-prone copy.

### Key difference to resolve first

`meadowlark.pyw::_get_source_options` reads runtime-configurable directories:
```python
video_dir   = Path(get_setting("VID_DL_VIDEO_STORAGE_DIR") or str(VIDEO_STORAGE_DIR))
podcast_dir = Path(get_setting("VID_DL_PODCAST_MISC_OUTPUT_DIR") or str(PODCAST_MISC_OUTPUT_DIR))
```

`ydl_options.py::get_source_options` uses frozen config constants directly. To unify, `ydl_options.get_source_options` must be updated to call `get_setting` for those two keys (it already imports `get_setting`).

### Steps

1. **`src/ydl_options.py`**: Replace `VIDEO_STORAGE_DIR` / `PODCAST_MISC_OUTPUT_DIR` literals inside `get_source_options` with `Path(get_setting("VID_DL_VIDEO_STORAGE_DIR") or str(VIDEO_STORAGE_DIR))` — same pattern already used for `vfmt`/`afmt`.

2. **`meadowlark.pyw`**: Delete `_get_source_options`. In `get_options`, replace:
   ```python
   source_props = self._get_source_options(source)
   ```
   with:
   ```python
   source_props = utils.get_source_options(source)
   ```
   The `match_filter` for playlists is already added separately in `get_options` / `request_detected`, so no functional regression.

3. **Tests**: `tests/test_format_settings.py` already tests `get_source_options` from `ydl_options.py`, so coverage now automatically hits the live code path. Verify no test references `_get_source_options`.

### Verification

1. `pytest tests/test_format_settings.py tests/test_download_executor_formats.py`
2. `ruff check src/ydl_options.py meadowlark.pyw`
3. Manual: drag to 720p with mkv set, confirm `.mkv` output
