TL;DR: In the podcast filtering logic _filter_audio_playlist_urls(), check if video titles contain the literal string "(Update)". If matched, skip the download, add to tfarchive.txt (via skip_downloading()), and log a special message with the video title, ID, and timestamp. This reuses the existing private video detection pattern but triggers on title content instead of a hardcoded "Private video" prefix.

Steps

Modify _filter_audio_playlist_urls() in [vid downloader.pyw](vid downloader.pyw) — After the existing _fetch_latest_accessible_entry() call (which handles private videos), add a check for "(Update)" in the title. When detected:

Call self.skip_downloading(video_id, title) to add to tfarchive.txt
Continue to next entry instead of adding to downloadable episodes list
The skip_downloading() method signature is already set up for this
Update or create log entry — After skipping, emit a log message via self.qlogger.message_changed.emit() with format: "Video skipped (Update): [title] (ID: {video_id}) — {timestamp}"

Pattern matches existing logging in _filter_audio_playlist_urls()
Use datetime.now().strftime("%Y-%m-%d %H:%M:%S") for timestamp
This will appear in both history_log.txt (via HistoryLogger) and UI
Verify tfarchive.txt entry — The skip_downloading() method already writes youtube {video_id}\n format, so no changes needed there