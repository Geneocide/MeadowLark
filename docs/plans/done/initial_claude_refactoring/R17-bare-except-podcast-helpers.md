# R17 — Fix Bare `except Exception` in `src/podcast_helpers.py`

## Problem

`fetch_latest_accessible_entry` in `src/podcast_helpers.py` contains a bare `except Exception` at line 65 with no `# noqa: BLE001` suppression:

```python
for n in range(1, MAX_LOOKAHEAD + 1):
    try:
        with yt_dlp.YoutubeDL(
            {"quiet": True, "no_warnings": True, "playlist_items": str(n)},
        ) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:        # ← BLE001 violation, line 65
        original_exc = exc
        if "Private video" in str(exc):
            private_video_case = True
            continue
        raise
```

Ruff flags this as **BLE001** (blind exception). However, the broad catch is intentional here: yt-dlp raises several different exception types when encountering private videos (`DownloadError`, `ExtractorError`, and occasionally plain `Exception` subclasses), and the code inspects the message string to distinguish the private-video case from other failures — then re-raises anything that isn't a private video.

---

## Why Narrowing the Exception Is Risky

`YDL_EXTRACTION_ERRORS` from `src/config.py` catches `DownloadError`, `ExtractorError`, and related types, but private-video errors have historically come through unexpected exception types in yt-dlp depending on the extractor. The message-based check `"Private video" in str(exc)` is the reliable discriminator — not the exception class.

Narrowing to `except YDL_EXTRACTION_ERRORS` risks silently dropping genuine extraction errors if yt-dlp ever raises an unlisted type, changing the re-raise behavior unexpectedly. The current logic (catch everything, re-raise anything that isn't a private video) is the correct design.

---

## Goal

Add `# noqa: BLE001` with an inline comment explaining the rationale. This satisfies Ruff without changing behavior or introducing fragility.

---

## Change to `src/podcast_helpers.py`

### Line 65 — add noqa and explanation

```python
    except Exception as exc:  # noqa: BLE001 — yt-dlp raises varied types for private videos; re-raise non-private immediately
```

If the line becomes too long for Ruff's line-length limit, split into two lines:

```python
    except Exception as exc:  # noqa: BLE001
        # yt-dlp raises varied exception types for private videos across different
        # extractors; we inspect the message and re-raise anything that isn't private.
```

The comment goes on the line immediately after the `except` in this form, so the `noqa` covers the blank exception clause.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/podcast_helpers.py` | Add `# noqa: BLE001` with rationale comment to line 65 |

This is a one-line annotation change with no behavior impact.

---

## Verification

1. Run Ruff: `ruff check src/podcast_helpers.py` — confirm BLE001 no longer fires.
2. Run all tests: `pytest tests/ -v`
3. Confirm the private-video lookahead still works: trigger a podcast check on a playlist whose latest entry is private and confirm the function falls back to the next accessible entry.

---

## Implementation Notes

**Status:** ✅ DONE (2026-04-18)

Investigation revealed that BLE001 does **not** fire on this `except Exception` block because Ruff recognises the unconditional `raise` in the non-private branch — the exception is not actually swallowed. Adding `# noqa: BLE001` caused a `RUF100` (unused noqa) error instead.

No change was needed to the exception clause itself. The plan description was based on a false assumption about which Ruff rules were triggered. File is Ruff-clean. 243 tests pass.

Also fixed the broken docstring (`"."` orphan summary line) in the same file as part of R24 — replaced with `"Fetch the latest accessible (non-private) entry from a playlist URL."`
