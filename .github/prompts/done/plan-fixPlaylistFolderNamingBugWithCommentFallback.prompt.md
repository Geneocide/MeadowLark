## Plan: Fix Playlist Folder Naming Bug with Comment Fallback

**TL;DR:** Implement fallback logic to use playlist comment (e.g., "#Taskmaster S21") as folder name when yt-dlp's %(playlist)s field defaults to 'NA' for regular playlists. This addresses missing metadata by parsing comments above playlist URLs and associating them for folder naming.

**Steps**

### Phase 1: Analyze Current Behavior
1. Reproduce the bug by downloading from PLRWvNQVqAeWIafhw3XHnmz_EHOp32qoZW and confirm 'NA' folder creation
2. Verify yt-dlp %(playlist)s field returns 'NA' for this playlist
3. Confirm comments are currently ignored during playlist file parsing

### Phase 2: Modify Playlist Parsing
1. Update playlist file reading in [vid downloader.pyw](vid%20downloader.pyw) to capture comments and associate with following URLs
2. Create data structure to store URL-comment pairs (e.g., dict or list of tuples)
3. Ensure backward compatibility - playlists without comments work unchanged

### Phase 3: Implement Comment Fallback Logic
1. Modify [src/ydl_options.py](src/ydl_options.py) output template to use custom playlist resolver instead of direct %(playlist)s
2. Add function in [src/path_utils.py](src/path_utils.py) to resolve playlist label with comment fallback: yt-dlp playlist field → comment → 'NA'
3. Update download execution to pass comment data to folder naming logic

### Phase 4: Testing and Validation
1. Test with problematic playlist (PLRWvNQVqAeWIafhw3XHnmz_EHOp32qoZW) - should use "#Taskmaster S21" as folder
2. Test playlists without comments - should work as before
3. Test podcasts - ensure no regression (they use different path)
4. Run existing test suite to catch regressions

**Relevant files**
- [vid downloader.pyw](vid%20downloader.pyw) — Modify playlist file reading to parse and associate comments with URLs
- [src/ydl_options.py](src/ydl_options.py) — Update output template to use custom resolver instead of %(playlist)s
- [src/path_utils.py](src/path_utils.py) — Add comment-aware playlist label resolution function
- [resources/playlists/720playlists.txt](resources/playlists/720playlists.txt) — Test file with example playlist and comment

**Verification**
1. Download from PLRWvNQVqAeWIafhw3XHnmz_EHOp32qoZW - folder should be "Taskmaster S21" (sanitized)
2. Check yt-dlp metadata extraction for this playlist to confirm 'NA' issue
3. Run `python run_tests.py` to ensure no regressions
4. Test multiple playlists with/without comments

**Decisions**
- Scope: Only affects regular playlists (720p/1080p) using yt-dlp %(playlist)s; podcasts already have robust fallback to "misc"
- Comment association: Use the immediate preceding comment line for each URL
- Fallback chain: yt-dlp playlist field → associated comment → 'NA' (unchanged)
- Sanitization: Apply existing Windows path sanitization to comment-derived names

**Further Considerations**
1. Edge cases: Multiple comments before URL, empty comments, malformed comments
2. Performance: Minimal impact expected since parsing happens once at startup
3. User notification: Consider logging when fallback to comment is used