# R14 — Split `DownloadExecutor.execute()` into Focused Helpers

## Problem

`execute()` (`src/download_executor.py:154–251`) is 98 lines and mixes three unrelated concerns in sequence:

| Concern | Lines | What it does |
|---|---|---|
| Download | 170–173 | Opens YoutubeDL context, clears cache, runs download |
| Post-download rename | 175–208 | Reads `qmeta`/`outtmpl`, finds base dir, calls `rename_playlist_folders_from_comments` |
| Error handling & fallbacks | 210–251 | Catches exceptions, extracts metadata, tries 720p and SponsorBlock fallbacks |

The rename logic (concern 2) is especially tangled — it handles `outtmpl` being either a `str` or a `dict`, extracts a base directory from it with a fragile string split, and is embedded in the success path of the try block, making the control flow hard to follow.

---

## Goal

Extract two private helpers — `_extract_base_output_dir` and `_rename_na_folder_if_needed` — so that `execute()` reads as a clean orchestrator. No behavior changes.

---

## New Method: `_extract_base_output_dir`

Handles the `outtmpl` normalization and directory extraction (currently lines 181–201):

```python
def _extract_base_output_dir(self, options: dict) -> str | None:
    """Extract the base output directory from the outtmpl option, or None if not determinable."""
    outtmpl = options.get("outtmpl", "")
    outtmpl_str: str | None = None

    if isinstance(outtmpl, str):
        outtmpl_str = outtmpl
    elif isinstance(outtmpl, dict):
        outtmpl_str = outtmpl.get("default")
        if not isinstance(outtmpl_str, str) or not outtmpl_str:
            for value in outtmpl.values():
                if isinstance(value, str) and value:
                    outtmpl_str = value
                    break

    if not outtmpl_str:
        return None

    # outtmpl is like "E:/vid storage/%(playlist)s/..." — take all but last segment
    parts = outtmpl_str.split("/")
    return "/".join(parts[:-1]) or None if len(parts) >= 2 else None  # noqa: PLR2004
```

---

## New Method: `_rename_na_folder_if_needed`

Handles the conditional rename (currently lines 175–207):

```python
def _rename_na_folder_if_needed(self, options: dict, urls: list) -> None:
    """Rename 'NA' playlist folders using comment metadata after a successful download."""
    meta = options.get("qmeta") or {}
    playlist_comments = meta.get("playlist_comments")
    if not playlist_comments:
        return
    base_output_dir = self._extract_base_output_dir(options)
    if not base_output_dir:
        return
    rename_playlist_folders_from_comments(
        base_output_dir,
        urls,
        playlist_comments,
        direct_playlist_id=meta.get("playlist_id"),
    )
```

---

## Revised `execute()`

```python
def execute(self, urls: list, options: dict) -> tuple[bool, str]:
    """
    Execute download with fallback strategies.

    Attempts fallbacks for 720p (if 1080p unavailable) and without
    SponsorBlock (if API down) before reporting final failure.

    Returns (success: bool, error_message: str).
    """
    try:
        self._download_with_cache_clear(options, urls)
        self._rename_na_folder_if_needed(options, urls)
        return True, ""
    except (
        DownloadError,
        ExtractorError,
        MaxDownloadsReached,
        OSError,
        ValueError,
    ) as e:
        title = self._extract_title(urls)
        error_str = str(e)
        meta = options.get("qmeta") or {}
        site = meta.get("site", "unknown")
        dtype = meta.get("type", meta.get("source", "unknown"))

        if dtype == "1080":
            success, error_str = self._try_720_fallback(urls, options, title, site, error_str)
            if success:
                return True, ""

        success, error_str = self._try_without_sponsorblock(
            urls, options, title, site, dtype, error_str
        )
        if success:
            return True, ""

        return False, f"Error downloading '{title}' (site: {site}, type: {dtype}): {e!s}"
```

---

## Implementation Notes

Implemented 2026-04-18. 287 tests pass, 1 skipped (pre-existing chmod/Windows skip).

Two latent bugs fixed during QA boundary review:
1. **Bare `/` outtmpl** returning `""` instead of `None` — added `or None` after the join.
2. **Empty-string `default` in dict outtmpl** silently blocking valid fallback keys — loop guard now checks `isinstance(value, str) and value`.

File Summary:

| Action | File | Detail |
|---|---|---|
| **Modified** | `src/download_executor.py` | Added 2 helpers (~30 lines); `execute()` reduced from ~98 lines to ~25 lines |
| **Updated** | `tests/test_download_executor.py` | 25 new tests for helpers; 3 bug-documenting tests updated to assert corrected behavior |
