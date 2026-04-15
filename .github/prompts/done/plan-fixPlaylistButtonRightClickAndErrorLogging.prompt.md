## Plan: Fix Playlist Button Right-Click and Error Logging

We've identified that the playlist button right-click functionality uses the correct config-defined paths (resources/playlists/*.txt), but the files don't exist in the workspace. Meanwhile, left-click functionality works by loading from hardcoded Z: drive paths in playlist_utils.py, suggesting the files exist at those locations (possibly a mapped drive).

The error "Playlist file not found" is printed to console instead of logged to error_log.txt.

**Steps**
1. (Completed) Update `get_playlist_file_for_source()` in `src/playlist_utils.py` to use config constants (`PLAYLISTS_FILE`, `PLAYLISTS_720_FILE`, `PLAYLISTS_AUDIO_FILE`) instead of hardcoded Z: drive paths.
2. (Already completed by human) Create the `resources/playlists/` directory if it doesn't exist.
3. (Already completed by human) Copy the existing playlist .txt files from the Z: locations (or wherever they currently exist) to the new config paths (`resources/playlists/playlists.txt`, `resources/playlists/720playlists.txt`, `resources/playlists/audio playlists.txt`).
4. (Completed) Replace the `print()` statement in `PlaylistButton.mousePressEvent()` with proper error logging using `utils.log_exception()` for the FileNotFoundError.
5. Test right-click on all playlist buttons to ensure files open correctly.
6. Test left-click still works after path updates.
7. Verify errors are now logged to `error_log.txt`.

**Relevant files**
- `src/playlist_utils.py` — Update path mapping function
- `src/config.py` — Already has correct paths
- `UIClasses.py` — Update error handling in PlaylistButton
- `vid downloader.pyw` — Uses the updated function
- `resources/playlists/` — Directory to create and populate with files

**Verification**
1. Run the application and right-click each playlist button; confirm the appropriate .txt file opens.
2. Check `error_log.txt` for any new error entries when files are missing.
3. Left-click playlist buttons and confirm downloads initiate as before.
4. Ensure no runtime errors occur from path changes.

**Decisions**
- Update legacy hardcoded paths to use centralized config for consistency.
- Assume existing files at Z: paths need to be moved to workspace-relative paths.
- Use `utils.log_exception()` for error logging to match app patterns.