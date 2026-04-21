# R09 — Unify Fallback Retry Logic in `DownloadExecutor`

## Problem

`DownloadExecutor` has two fallback methods with near-identical structure:

| Method | Lines | Trigger condition |
|---|---|---|
| `_try_720_fallback` | 63–109 | `"Requested format is not available"` in error |
| `_try_without_sponsorblock` | 112–152 | `"Unable to communicate with SponsorBlock API"` in error |

**Shared skeleton (identical in both):**
```python
if <trigger_not_met> or options.get("<tried_flag>"):
    return False, error_str
self._emit_message("<message>")
fallback = <modified_options>
fallback["<tried_flag>"] = True
try:
    with YoutubeDL(fallback) as ydl:
        ydl.cache.remove()
        ydl.download(urls)
    return True, error_str  # noqa: TRY300
except YDL_EXTRACTION_ERRORS as e2:
    utils.log_exception(e2, "<context>")
    return False, str(e2)
```

**What differs between the two:**

| Aspect | `_try_720_fallback` | `_try_without_sponsorblock` |
|---|---|---|
| Trigger string | `"Requested format is not available"` | `"Unable to communicate with SponsorBlock API"` |
| Tried flag key | `"_tried_720_fallback"` | `"_tried_without_sponsorblock"` |
| Emit message | `"Requested 1080 format not available for '{title}'; retrying at 720..."` | `"SponsorBlock API unavailable; retrying download without SponsorBlock..."` |
| Options modification | Copy + set `format`, `merge_output_format`, `qmeta.type` | `utils.remove_sponsorblock_postprocessor(options)` |
| Exception log context | `"720p fallback attempt failed"` | `"SponsorBlock removal retry failed"` |
| Extra parameter | — | `dtype: str` (unused in body) |

The options modification is different enough that it cannot be a simple parameter — it must be a callable.

---

## Goal

Extract a generic `_try_fallback` method that accepts the varying parts as arguments. Both existing methods become thin wrappers that build their specific arguments and delegate.

---

## New Method: `_try_fallback`

```python
def _try_fallback(
    self,
    urls: list,
    options: dict,
    tried_flag: str,
    trigger_phrase: str,
    error_str: str,
    message: str,
    options_modifier: Callable[[dict], dict],
    log_context: str,
) -> tuple[bool, str]:
    """
    Generic fallback download attempt.

    Returns (True, original_error_str) on success, (False, new_error_str) on failure.
    Does nothing and returns (False, error_str) if the trigger phrase is absent or the
    fallback has already been attempted.
    """
    if trigger_phrase not in error_str or options.get(tried_flag):
        return False, error_str
    self._emit_message(message)
    fallback = options_modifier(options)
    fallback[tried_flag] = True
    try:
        with YoutubeDL(fallback) as ydl:
            ydl.cache.remove()
            ydl.download(urls)
        return True, error_str  # noqa: TRY300
    except YDL_EXTRACTION_ERRORS as e2:
        utils.log_exception(e2, log_context)
        return False, str(e2)
```

---

## Revised `_try_720_fallback`

```python
def _try_720_fallback(
    self,
    urls: list,
    options: dict,
    title: str,
    site: str,
    error_str: str,
) -> tuple[bool, str]:
    """Try downloading at 720p if 1080p format unavailable."""
    def _modify(opts: dict) -> dict:
        fallback = opts.copy()
        fallback["format"] = (
            "bestvideo*[height=720][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo*[height=720]+bestaudio/"
            "best[height=720]/best"
        )
        fallback.setdefault("merge_output_format", "mp4")
        fq = dict(fallback.get("qmeta", {}))
        fq["type"] = "720"
        fallback["qmeta"] = fq
        return fallback

    return self._try_fallback(
        urls=urls,
        options=options,
        tried_flag="_tried_720_fallback",
        trigger_phrase="Requested format is not available",
        error_str=error_str,
        message=f"Requested 1080 format not available for '{title}'; retrying at 720...",
        options_modifier=_modify,
        log_context="720p fallback attempt failed",
    )
```

---

## Revised `_try_without_sponsorblock`

```python
def _try_without_sponsorblock(  # noqa: PLR0913
    self,
    urls: list,
    options: dict,
    title: str,
    site: str,
    dtype: str,
    error_str: str,
) -> tuple[bool, str]:
    """Try downloading without SponsorBlock if API unavailable."""
    return self._try_fallback(
        urls=urls,
        options=options,
        tried_flag="_tried_without_sponsorblock",
        trigger_phrase="Unable to communicate with SponsorBlock API",
        error_str=error_str,
        message="SponsorBlock API unavailable; retrying download without SponsorBlock...",
        options_modifier=utils.remove_sponsorblock_postprocessor,
        log_context="SponsorBlock removal retry failed",
    )
```

Note: `utils.remove_sponsorblock_postprocessor` already has the right signature `(options: dict) -> dict` so it can be passed directly as `options_modifier`.

The `PLR0913` suppression stays because the public signature still has 7 parameters — this is a deliberate API choice since callers pass all of them from `execute()`.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/download_executor.py` | Add `_try_fallback` (~20 lines); simplify two methods to ~15 lines each |

Net: ~90 lines → ~55 lines. All existing public signatures and callers in `execute()` are unchanged.

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/download_executor.py`
3. Trigger a 1080p download of a video that only has 720p available and confirm the fallback fires and succeeds.
4. Simulate a SponsorBlock API error (or check test coverage) and confirm the SponsorBlock fallback fires correctly.

---

## Implementation Notes (2026-04-18)

**Done.** 243 tests pass. No new Ruff violations introduced.

- Added `_try_fallback` (~15 lines) with `# noqa: PLR0913` (9 params — intentional, each varies per fallback).
- `_try_720_fallback`: replaced inline logic with a nested `_modify()` closure + delegate to `_try_fallback`. Signature unchanged.
- `_try_without_sponsorblock`: passes `utils.remove_sponsorblock_postprocessor` directly as `options_modifier`. Signature unchanged; `# noqa: PLR0913` retained (7 params).
- Pre-existing Ruff violations in file (ARG002 on passthrough params, C901/PLR2004/TRY300 in `execute`) not introduced by this refactor.
- Net: ~90 lines → ~55 lines in the two fallback methods.
