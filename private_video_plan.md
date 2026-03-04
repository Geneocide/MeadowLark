Plan: Ignore “Private video” Errors in YT‑Podcast Checks

TL;DR
When the podcast‑status code hits a private/latest episode it currently bubbles an exception and marks the whole playlist as errored.
We’ll add logic to recognise those “Private video…” errors, skip the offending entry and pretend the previous accessible video is the newest.
No error flag will be set; the status code will be calculated from the prior video.
A small module‑level helper will encapsulate the retry logic and make it testable, and a couple of unit tests will exercise the new behaviour.

📌 What to change
New helper – add _fetch_latest_accessible_entry(url: str) at module scope (just above MyWindow or near _filter_audio_playlist_urls).

Try a yt_dlp.YoutubeDL(..., "playlistend":1) extraction.
If it succeeds but the returned item’s title starts with “Private video”, or the call raises an exception whose text contains “Private video”, treat that as a private‑latest case.
In that case do a second extraction (no playlistend, ignoreerrors=True), filter the resulting entries backwards until a non‑private entry is found, and return that one.
Return a (entries, skipped: bool) tuple where entries is a one‑item list suitable for the existing loop and skipped signals that we ignored a private item.
If the playlist has no accessible entries, re‑raise the original exception.
Modify _filter_audio_playlist_urls

Replace the early ydl.extract_info call with a call to the helper; receive entries & skip flag.
If skipped is True, append a message such as
f"Latest episode for podcast {url} is private – using previous accessible video"
and do not set had_error.
Leave the rest of the method untouched; the returned entries list drives the existing timestamp/age/SponsorBlock logic.
Docstrings/comments

Update _filter_audio_playlist_urls docstring to mention private‑video handling.
Comment the new helper explaining its purpose and the “Private video” string check.
Tests

Create tests/test_private_video_handling.py.
Monkey‑patch yt_dlp.YoutubeDL with a dummy context manager that:
On first call with playlistend=1 raises the private‑video exception.
On subsequent calls returns a crafted info dict simulating a playlist whose last item is the previous accessible video.
Write two tests:
Helper returns the second entry and skipped is True.
_filter_audio_playlist_urls invoked with that monkey‑patch yields had_error == False and the status entry’s latest_url equals the previous‑video URL.
Optionally, a third test ensuring that if no accessible entries exist the error propagates.
Add a minimal QApplication setup if needed, or test the helper directly so GUI components aren’t required.